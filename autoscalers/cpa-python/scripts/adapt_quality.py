import re
import json
from kubernetes import config, client
from adapter_logger import AdapterLogger


valid_qualities = ['20k', '200k', '400k', '800k']


def rollout_in_progress(api: client.AppsV1Api, name: str, namespace: str = "default") -> bool:
    """
    Return True  ➜ a new ReplicaSet is still being rolled out
           False ➜ the Deployment is fully rolled out
    """
    d = api.read_namespaced_deployment_status(name, namespace)

    # The Deployment controller first sets .status.observedGeneration
    # to match .metadata.generation, *then* updates the replica counts.
    gen_synced = (d.status.observed_generation or 0) >= d.metadata.generation
    spec_replicas    = d.spec.replicas or 0
    updated_replicas = d.status.updated_replicas    or 0
    available_repls  = d.status.available_replicas  or 0

    rollout_complete = (
        gen_synced and
        updated_replicas == spec_replicas and
        available_repls  == spec_replicas
    )

    return not rollout_complete


def down(resource: dict):
    logger = AdapterLogger("adapt_quality")

    namespace = resource['metadata']['namespace']
    name = resource['metadata']['name']

    config.load_incluster_config()
    appsV1 = client.AppsV1Api()

    if rollout_in_progress(appsV1, name, namespace):
        logger.logger.info("Rollout in progress. Do nothing.")
        return

    containers = resource['spec']['template']['spec']['containers']
    container_znn = [c for c in containers if c['name'] == 'znn'][0]

    deployment = appsV1.read_namespaced_deployment(
        name,
        namespace)
    
    current_quality = container_znn['image'].split(":")[1]
    cur_quality_idx = valid_qualities.index(current_quality)
    target_quality_idx = 0 if cur_quality_idx == 0 else cur_quality_idx -1
    logger.logger.debug(f"Next lower quality: {valid_qualities[target_quality_idx]}")

    for container in deployment.spec.template.spec.containers:
        if container.name == 'znn':
            image_name = container.image.split(':')[0]
            container_image = f"{image_name}:{valid_qualities[target_quality_idx]}"
            logger.logger.debug(f"Patching image to {container_image}")
            patch = {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "znn",
                                    "image": container_image
                                }
                            ]
                        }
                    }
                }
            }
            appsV1.patch_namespaced_deployment(
                name=name,
                namespace=namespace,
                body=patch
            )

    
