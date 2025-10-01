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
import sys
from dataclasses import dataclass
from typing import Any, Callable

from kubernetes import client, config

from adapter_logger import AdapterLogger


@dataclass
class AdaptContext:
    """Execution context passed to strategies."""
    spec: dict[str, Any]
    logger: Any
    apps: client.AppsV1Api
    res_name: str
    res_ns: str
    deployment: Any


@dataclass
class StrategyResult:
    """Return value for strategies.

    `should_patch` indicates whether a patch must be performed.
    `build_output` receives the patched Deployment and must return a JSON-serializable dict.
    """
    should_patch: bool
    build_output: Callable[[Any], dict[str, Any]]


def rollout_in_progress(deployment: Any) -> bool:
    """Return True if a new ReplicaSet is still being rolled out, else False."""
    observed = (deployment.status.observed_generation or 0)
    desired = deployment.metadata.generation
    spec_replicas = deployment.spec.replicas or 0
    updated_replicas = deployment.status.updated_replicas or 0
    available_replicas = deployment.status.available_replicas or 0
    gen_synced = observed >= desired
    rollout_complete = gen_synced and updated_replicas == spec_replicas and available_replicas == spec_replicas
    return not rollout_complete


def get_container_with_name(deployment: Any, container_name: str) -> Any | None:
    """Return the container object with the given name or None if not found."""
    containers = getattr(getattr(deployment.spec.template.spec, "containers", []), "__iter__", lambda: [])()
    for c in containers:
        if getattr(c, "name", None) == container_name:
            return c
    return None


def _build_context(spec_raw: str, logger_name: str) -> AdaptContext | None:
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
        logger.error("Spec must include resource.metadata.name and resource.metadata.namespace")
        return None

    try:
        config.load_incluster_config()
    except Exception as e:
        logger.error(f"Failed to load in-cluster config: {e}")
        return None

    apps = client.AppsV1Api()

    try:
        deployment = apps.read_namespaced_deployment(name=res_name, namespace=res_ns)
    except Exception as e:
        logger.error(f"Failed to read Deployment {res_ns}/{res_name}: {e}")
        return None
    if deployment is None:
        logger.error(f"Deployment {res_ns}/{res_name} not found")
        return None

    if rollout_in_progress(deployment):
        logger.info("Rollout in progress, skipping")
        return None

    return AdaptContext(
        spec=spec,
        logger=logger,
        apps=apps,
        res_name=res_name,
        res_ns=res_ns,
        deployment=deployment,
    )


def run(spec_raw: str, logger_name: str, strategy: Callable[[AdaptContext], StrategyResult | None]) -> None:
    """Run the common flow and delegate mutation + output to the provided strategy."""
    ctx = _build_context(spec_raw, logger_name)
    if ctx is None:
        return
    
    ctx.logger.info(f"Starting adapt for {logger_name}")

    result = strategy(ctx)
    if result is None:
        sys.stdout.write(json.dumps({}))
        return

    patched = ctx.deployment
    if result.should_patch:
        try:
            patched = ctx.apps.patch_namespaced_deployment(
                name=ctx.res_name,
                namespace=ctx.res_ns,
                body=ctx.deployment,
            )
        except Exception as e:
            ctx.logger.error(f"Failed to patch Deployment {ctx.res_ns}/{ctx.res_name}: {e}")
            return

    out = result.build_output(patched)
    sys.stdout.write(json.dumps(out))


__all__ = [
    "AdaptContext",
    "StrategyResult",
    "run",
    "rollout_in_progress",
    "get_container_with_name",
]
