from kubernetes import config, client
from adapt_quality import rollout_in_progress
from adapter_logger import AdapterLogger


def adapt(container_name: str, deploy_name: str, namespace: str, up: bool):
    logger = AdapterLogger("scale_cpu")
    logger.logger.info("Starting scale_cpu")

    config.load_incluster_config()
    appsV1 = client.AppsV1Api()

    deployment = appsV1.read_namespaced_deployment(
        name=deploy_name,
        namespace=namespace
    )

    if rollout_in_progress(deployment):
        logger.logger.info("Rollout in progress. Do nothing.")
        return

    container = next(filter(lambda x: x.name == container_name, deployment.spec.template.spec.containers))

    if not container:
        logger.logger.error(f"Container {container_name} not found in {namespace}/{deploy_name}")
        return

    logger.logger.info(f"direction: {'up' if up else 'down'}")

    current_cpu_requests = container.resources.requests["cpu"]
    current_cpu_limits = container.resources.limits["cpu"]
    current_cpu_requests = current_cpu_requests[0:current_cpu_requests.index("m")]
    current_cpu_limits = current_cpu_limits[0:current_cpu_limits.index("m")]

    if up:
        cpu_change = 1.25
    else:
        cpu_change = 0.5

    # determines a floor for cpu requests and limits
    new_cpu_requests = max(int(float(current_cpu_requests) * cpu_change), 50)
    new_cpu_requests = f"{new_cpu_requests}m"
    new_cpu_limits = max(int(float(current_cpu_limits) * cpu_change), 100)
    new_cpu_limits = f"{new_cpu_limits}m"
    container.resources.requests["cpu"] = new_cpu_requests
    container.resources.limits["cpu"] = new_cpu_limits

    logger.logger.info(f"Scaling CPU limits {current_cpu_limits} * {cpu_change} to {new_cpu_limits}")

    appsV1.patch_namespaced_deployment(
        name=deploy_name,
        namespace=namespace,
        body=deployment
    )


def up(container_name: str, deploy_name: str, namespace: str):
    adapt(container_name, deploy_name, namespace, up=True)


def down(container_name: str, deploy_name: str, namespace: str):
    adapt(container_name, deploy_name, namespace, up=False)
