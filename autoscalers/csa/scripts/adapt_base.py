"""Common runtime for adaptation scripts reading spec from stdin and patching a Deployment.

This module centralizes:
- JSON parsing from stdin
- Logging setup
- Kubernetes client bootstrap
- Deployment fetch and rollout guard
- Patch execution and standardized JSON output

Child scripts provide a `strategy(ctx) -> StrategyResult | None`.
If `None` is returned, the run is a no-op.
"""

import json
from logging import Logger
import sys
from dataclasses import dataclass
from typing import Any, Callable

from kubernetes import client, config
from kubernetes.client.models import (
    V1Container,
    V1Deployment,
    V1DeploymentSpec,
    V1Pod,
    V1PodSpec,
    V1PodTemplate,
)

from adapter_logger import AdapterLogger


@dataclass
class AdaptContext:
    """Execution context passed to strategies."""

    spec: dict[str, Any]
    logger: Logger
    core: client.CoreV1Api
    apps: client.AppsV1Api
    res_name: str
    res_ns: str
    deployment: Any


@dataclass
class StrategyResult:
    """Desired operation and optional details.

    `op` must be one of:
      - "deployment_patch": mutate `ctx.deployment` and the base will PATCH the Deployment.
      - "pod_resize": provide `pod_name` and `resize_body` and the base will PATCH the Pod resize subresource.

    `details` is merged into the standardized output to stdout.
    """

    op: str
    details: dict[str, Any] | None = None
    pod_name: str | None = None
    resize_body: dict[str, Any] | None = None


def rollout_in_progress(deployment: Any) -> bool:
    """Return True if a new ReplicaSet is still being rolled out, else False."""
    observed = deployment.status.observed_generation or 0
    desired = deployment.metadata.generation
    spec_replicas = deployment.spec.replicas or 0
    updated_replicas = deployment.status.updated_replicas or 0
    available_replicas = deployment.status.available_replicas or 0
    rollout_complete = (
        observed >= desired
        and updated_replicas == spec_replicas
        and available_replicas == spec_replicas
    )
    return not rollout_complete


def get_container_with_name(
    deployment: V1Deployment, container_name: str
) -> Any | None:
    """Return the container object with the given name or None if not found."""
    spec: V1DeploymentSpec = deployment.spec
    tpl: V1PodTemplate = spec.template
    podspec: V1PodSpec = tpl.spec
    containers: list[V1Container] = podspec.containers
    for c in containers:
        if getattr(c, "name", None) == container_name:
            return c
    return None


def is_pod_ready(pod: V1Pod) -> bool:
    """Return True if pod has Ready condition True."""
    conds = pod.status.condidions
    for c in conds:
        if c.type == "Ready" and c.status == "True":
            return True
    return False


def one_pod_name_for_deployment(
    core: client.CoreV1Api, deployment: V1Deployment, namespace: str
) -> str | None:
    """Return a single pod name belonging to the deployment, preferring Ready pods."""
    sel = deployment.spec.selector.match_labels or {}
    label_selector = ",".join(f"{k}={v}" for k, v in sel.items()) if sel else None
    pods = core.list_namespaced_pod(
        namespace=namespace, label_selector=label_selector
    ).items
    if not pods:
        return None
    ready = [p for p in pods if is_pod_ready(p)]
    chosen = ready[0] if ready else pods[0]
    return chosen.metadata.name if chosen.metadata else None


def parse_cpu_to_mcpu(cpu: str) -> int | None:
    """Parse a CPU quantity into millicores."""
    if not isinstance(cpu, str) or not cpu:
        return None
    s = cpu.strip()
    if s.endswith("m"):
        try:
            return int(s[:-1])
        except ValueError:
            return None
    if s.endswith("n"):
        try:
            nanos = int(s[:-1])
            return max(1, nanos // 1_000_000)
        except ValueError:
            return None
    try:
        return max(1, int(round(float(s) * 1000.0)))
    except ValueError:
        return None


def format_mcpu(mcpu: int) -> str:
    """Format millicores as a CPU quantity string."""
    return f"{int(mcpu)}m"


def build_context(spec_raw: str, logger_name: str) -> AdaptContext | None:
    """Create and validate the execution context or return None on any guard failure."""
    logger = AdapterLogger(logger_name).logger
    try:
        spec = json.loads(spec_raw)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON on stdin: {e}")
        return None

    resource = spec.get("resource", {})
    meta = resource.get("metadata", {})
    res_name = meta.get("name")
    res_ns = meta.get("namespace")
    if not res_name or not res_ns:
        logger.error(
            "Spec must include resource.metadata.name and resource.metadata.namespace"
        )
        return None

    try:
        config.load_incluster_config()
    except Exception as e:
        logger.error(f"Failed to load in-cluster config: {e}")
        return None

    core = client.CoreV1Api()
    apps = client.AppsV1Api()

    try:
        deployment = apps.read_namespaced_deployment(name=res_name, namespace=res_ns)
    except Exception as e:
        logger.error(f"Failed to read Deployment {res_ns}/{res_name}: {e}")
        return None
    if deployment is None:
        logger.error(f"Deployment {res_ns}/{res_name} not found")
        return None

    return AdaptContext(
        spec=spec,
        logger=logger,
        core=core,
        apps=apps,
        res_name=res_name,
        res_ns=res_ns,
        deployment=deployment,
    )


def run(
    spec_raw: str,
    logger_name: str,
    strategy: Callable[[AdaptContext], StrategyResult | None],
) -> None:
    """Run the common flow and delegate mutation + output to the provided strategy."""
    ctx = build_context(spec_raw, logger_name)
    if ctx is None:
        return

    ctx.logger.info(f"Starting adapt for {logger_name}")

    result = strategy(ctx)
    if result is None:
        sys.stdout.write(json.dumps({}))
        return

    ctx.logger.info(json.dumps(result.details))
    ctx.logger.info(ctx.deployment.spec.replicas)

    out: dict[str, Any] = {
        "op": result.op,
        "resource": {"name": ctx.res_name, "namespace": ctx.res_ns},
    }

    if result.op == "deployment_patch":
        if rollout_in_progress(ctx.deployment):
            ctx.logger.info("Rollout in progress, skipping deployment patch")
            sys.stdout.write(json.dumps({"result": "skip"}))
            return
        try:
            patched = ctx.apps.patch_namespaced_deployment(
                name=ctx.res_name, namespace=ctx.res_ns, body=ctx.deployment
            )
            out.setdefault("details", {})
            out["details"]["replicas"] = getattr(
                getattr(patched, "spec", None), "replicas", None
            )
            sys.stdout.write(json.dumps({**out, **(result.details or {})}))
        except Exception as e:
            ctx.logger.error(
                f"Failed to patch Deployment {ctx.res_ns}/{ctx.res_name}: {e}"
            )
            sys.stdout.write(json.dumps({"result": "error"}))
            return

    elif result.op == "pod_resize":
        if not result.pod_name or not result.resize_body:
            ctx.logger.error(
                "Missing pod_name or resize_body, for pod_resize operation"
            )
            sys.stdout.write(json.dumps({"result": "skip"}))
            return
        try:
            _ = ctx.core.patch_namespaced_pod_resize(
                name=result.pod_name, namespace=ctx.res_ns, body=result.resize_body
            )
            out["resource"]["pod"] = result.pod_name
            sys.stdout.write(json.dumps({**out, **(result.details or {})}))
        except Exception as e:
            ctx.logger.error(
                f"Failed to resize Pod {ctx.res_ns}/{result.pod_name}: {e}"
            )
            sys.stdout.write(json.dumps({"result": "error"}))
            return

    else:
        ctx.logger.error(f"Unknown operation '{result.op}'")
        sys.stdout.write(json.dumps({"result": "skip"}))
        return


__all__ = [
    "AdaptContext",
    "StrategyResult",
    "run",
    "rollout_in_progress",
    "get_container_with_name",
    "one_pod_name_for_deployment",
    "parse_cpu_to_mcpu",
    "format_mcpu",
]
