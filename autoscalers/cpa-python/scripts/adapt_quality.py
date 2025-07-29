import re
import json
from kubernetes import config, client
from adapter_logger import AdapterLogger


valid_qualities = ['20k', '100k', '200k', '400k', '600k', '800k']


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


def select_higher_quality(image_tag: str) -> str:
    current_quality_idx = valid_qualities.index(image_tag)
    max_index = len(valid_qualities) - 1
    target_quality_idx = max_index if current_quality_idx == max_index else current_quality_idx + 1
    return valid_qualities[target_quality_idx]


def select_lower_quality(image_tag: str) -> str:
    current_quality_idx = valid_qualities.index(image_tag)
    target_quality_idx = 0 if current_quality_idx == 0 else current_quality_idx - 1
    return valid_qualities[target_quality_idx]


def adapt(container_name: str, deploy_name: str, namespace: str, up: bool):
    logger = AdapterLogger("adapt_quality")

    config.load_incluster_config()
    appsV1 = client.AppsV1Api()

    # Get the target deployment and container
    deployment = appsV1.read_namespaced_deployment(deploy_name, namespace)

    # Stops if there's already a rollout in progress
    if rollout_in_progress(deployment):
        logger.logger.info("Rollout in progress. Do nothing.")
        return

    container = next(filter(lambda x: x.name == container_name, deployment.spec.template.spec.containers))

    # Stops if container not found
    if not container:
        logger.logger.error(f"Container {container_name} not found in {namespace}/{deploy_name}")
        return

    # Gets the tag used, uses it to select a new tag
    image_name, image_tag = container.image.split(':')
    if up:
        target_quality = select_higher_quality(image_tag)
    else:
        target_quality = select_lower_quality(image_tag)

    container_image = f"{image_name}:{target_quality}"

    #Patches the deployment with the new tag
    patch = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": container_name,
                            "image": container_image
                        }
                    ]
                }
            }
        }
    }
    appsV1.patch_namespaced_deployment(name=deploy_name, namespace=namespace, body=patch)


def up(container_name: str, deploy_name: str, namespace: str):
    adapt(container_name, deploy_name, namespace, up=True)


def down(container_name: str, deploy_name: str, namespace: str):
    adapt(container_name, deploy_name, namespace, up=False)
