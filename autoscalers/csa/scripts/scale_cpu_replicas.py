import json
import sys

from kubernetes import config, client
from adapter_logger import AdapterLogger
import initial_limits


container_name = 'znn'


def rollout_in_progress(deployment) -> bool:
    """
    Return True  ➜ a new ReplicaSet is still being rolled out
           False ➜ the Deployment is fully rolled out
    """

    # The Deployment controller first sets .status.observedGeneration
    # to match .metadata.generation, *then* updates the replica counts.
    gen_synced = (deployment.status.observed_generation or 0) >= deployment.metadata.generation
    spec_replicas    = deployment.spec.replicas or 0
    updated_replicas = deployment.status.updated_replicas    or 0
    available_repls  = deployment.status.available_replicas  or 0

    rollout_complete = (
        gen_synced and
        updated_replicas == spec_replicas and
        available_repls  == spec_replicas
    )

    return not rollout_complete


def main(spec_raw):
    logger = AdapterLogger("scale_cpu_resplicas")
    logger.logger.info("Starting scale_cpu_replicas")

    spec = json.loads(spec_raw)
    resource = spec['resource']

    config.load_incluster_config()
    appsV1 = client.AppsV1Api()

    initial_limits.store_limits(resource['metadata']['name'], resource['metadata']['namespace'], container_name)

    deployment = appsV1.read_namespaced_deployment(
        name=resource['metadata']['name'],
        namespace=resource['metadata']['namespace']
    )

    if rollout_in_progress(deployment):
        logger.logger.info("Rollout in progress. Do nothing.")
        return

    container = next(filter(lambda x: x.name == container_name, deployment.spec.template.spec.containers))

    if not container:
        logger.logger.error(f"Container {container_name} not found in {resource['metadata']['namespace']}/{resource['metadata']['name']}")
        return

    parameters = spec['evaluation']['parameters']
    logger.logger.info(parameters.keys())
    replicas_change = parameters['replicas'] if 'replicas' in parameters else 0
    cpu_change = parameters['cpu'] if 'cpu' in parameters else 1
    direction = parameters['direction'] if 'direction' in parameters else None

    if not direction:
        logger.logger.error("Evaluation must contain 'direction' key with value 'up' or 'down'")
        return

    logger.logger.info(f"direction: {direction}")
    logger.logger.info(f"replicas_change: {replicas_change}")
    logger.logger.info(f"cpu_change: {cpu_change}")

    current_cpu_limits = container.resources.limits["cpu"]
    current_cpu_limits = current_cpu_limits[0:current_cpu_limits.index("m")]
    initial = json.loads(initial_limits.get_limits())
    initial_cpu_limits = initial['limits']['cpu']
    initial_cpu_limits = initial_cpu_limits[0:initial_cpu_limits.index("m")]

    logger.logger.info(f"initial cpu: {initial_cpu_limits}")
    logger.logger.info(f"current cpu: {current_cpu_limits}")

    if direction == 'up':
        deployment.spec.replicas = deployment.spec.replicas + replicas_change
        cpu_change = 1 + cpu_change
        new_cpu_limits = max(int(float(current_cpu_limits) * cpu_change), int(current_cpu_limits))
        logger.logger.info(f"calculated : {new_cpu_limits}")

    if direction == 'down':
        if deployment.spec.replicas > 1:
            deployment.spec.replicas = deployment.spec.replicas - replicas_change
        if cpu_change != 1:
            cpu_change = 1 - cpu_change
        new_cpu_limits = min(int(float(current_cpu_limits) * cpu_change), int(current_cpu_limits))
        new_cpu_limits = max(new_cpu_limits, int(initial_cpu_limits))
        logger.logger.info(f"calculated : {new_cpu_limits}")

    new_cpu_limits = f"{new_cpu_limits}m"
    container.resources.limits["cpu"] = new_cpu_limits

    logger.logger.info(f"Will patch with replicas {deployment.spec.replicas} and cpu {container.resources.limits['cpu']}")

    patched_deployment = appsV1.patch_namespaced_deployment(
        name=resource['metadata']['name'],
        namespace=resource['metadata']['namespace'],
        body=deployment
    )

    sys.stdout.write(json.dumps({
        "replicas": patched_deployment.spec.replicas
    }))


if __name__ == '__main__':
    main(sys.stdin.read())
