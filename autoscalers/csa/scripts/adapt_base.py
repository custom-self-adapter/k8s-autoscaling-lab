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
from logging import Logger
from typing import Any

import yaml
from adapter_logger import AdapterLogger
from kubernetes import client, config
from kubernetes.client.models import (
    V1Deployment,
    V1Pod,
)


class AdaptContext:
    """Execution context passed to strategies."""

    spec: dict[str, Any]
    resource: dict[str, Any]
    logger: Logger
    core: client.CoreV1Api
    apps: client.AppsV1Api
    res_name: str
    res_ns: str
    deployment: V1Deployment

    def __init__(self, spec_raw: str, logger_name: str) -> None:
        self.logger = AdapterLogger(logger_name).logger
        try:
            self.spec = json.loads(spec_raw)
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON on stdin: {e}")
            raise ValueError from e

        self.resource = self.spec.get("resource", {})
        meta = self.resource.get("metadata", {})
        self.res_name = meta.get("name")
        self.res_ns = meta.get("namespace")
        if not self.res_name or not self.res_ns:
            self.logger.error(
                "Spec must include resource.metadata.name and resource.metadata.namespace"
            )
            raise ValueError

        try:
            config.load_incluster_config()
        except Exception as e:
            self.logger.error(f"Failed to load in-cluster config: {e}")
            raise ValueError from e

        self.core = client.CoreV1Api()
        self.apps = client.AppsV1Api()

        try:
            deployment = self.apps.read_namespaced_deployment(
                name=self.res_name, namespace=self.res_ns
            )
            if deployment and isinstance(deployment, V1Deployment):
                self.deployment = deployment
        except Exception as e:
            self.logger.error(
                f"Failed to read Deployment {self.res_ns}/{self.res_name}: {e}"
            )
            raise ValueError from e
        if self.deployment is None:
            self.logger.error(f"Deployment {self.res_ns}/{self.res_name} not found")
            raise ValueError

    def rollout_in_progress(self) -> bool:
        """Return True if a new ReplicaSet is still being rolled out, else False."""
        observed = self.deployment.status.observed_generation or 0
        desired = self.deployment.metadata.generation
        spec_replicas = self.deployment.spec.replicas or 0
        updated_replicas = self.deployment.status.updated_replicas or 0
        available_replicas = self.deployment.status.available_replicas or 0
        rollout_complete = (
            observed >= desired
            and updated_replicas == spec_replicas
            and available_replicas == spec_replicas
        )
        return not rollout_complete

    def get_running_pods(self) -> list[V1Pod]:
        selector = self.deployment.spec.selector.match_labels or {}
        label_selector = (
            ",".join(f"{k}={v}" for k, v in selector.items()) if selector else None
        )
        pods = self.core.list_namespaced_pod(
            namespace=self.res_ns, label_selector=label_selector
        ).items
        return pods if pods else []

    def get_container_spec(self, container_name: str) -> Any | None:
        for c in self.deployment.spec.template.spec.containers:
            if getattr(c, "name", None) == container_name:
                return c
        return None

    def get_spec_mcpu(self):
        containers = self.deployment.spec.template.spec.containers
        for container in containers:
            if container and container.resources:
                spec_cpu = (container.resources.limits or {}).get("cpu")
                return parse_cpu_to_mcpu(spec_cpu) if spec_cpu else 0

    def get_current_mcpu(self):
        pod_list = self.get_running_pods()
        if not pod_list:
            return None
        current_mcpus: list[int] = []
        for pod in pod_list:
            first_container = (pod.spec.containers or [None])[0]
            if first_container and first_container.resources:
                current_cpu = (first_container.resources.limits or {}).get("cpu")
                current_mcpu = parse_cpu_to_mcpu(current_cpu) if current_cpu else 0
                current_mcpus.append(current_mcpu if current_mcpu else 0)
        return max(current_mcpus)


def load_config(configfile="/config.yaml") -> dict | None:
    with open(configfile) as file:
        try:
            config = yaml.safe_load(file)
            if config is None:
                sys.stderr.write("config file was empty")
                return None
            return config
        except yaml.YAMLError as e:
            sys.stderr.write(f"failed to parse config file: {e}")
            return None


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


__all__ = [
    "AdaptContext",
    "rollout_in_progress",
    "parse_cpu_to_mcpu",
    "format_mcpu",
]
