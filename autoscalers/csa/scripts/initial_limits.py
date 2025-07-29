import os
import json
from kubernetes import config, client
from adapter_logger import AdapterLogger


logger = AdapterLogger("initial_limits")
config.load_incluster_config()
coreV1 = client.CoreV1Api()
appsV1 = client.AppsV1Api()


def get_self_pod():
    # Tries to idenfity running CSA from environment
    csa_name = os.getenv("CSA_NAME")
    csa_namespace = os.getenv("CSA_NAMESPACE")
    if not csa_name or not csa_namespace:
        logger.logger.error("CSA_NAME or CSA_NAMESPACE not defined!")
        return None

    pod = coreV1.read_namespaced_pod(
        name=csa_name,
        namespace=csa_namespace
    )
    if not pod:
        logger.logger.error(f"Pod {csa_namespace}/{csa_name} not found!")
        return None
    
    return pod


def store_limits(deployment_name, namespace, container_name):
    """Reads the limits on the named container and stores it in
    an annotation in the CSA pod running this script.
    This annotation will in turn be reflected on the CSA object status
    by the Custom Self-Adapter Operator.
    """

    stored_limits = get_limits()
    if stored_limits is not None:
        return

    deployment = appsV1.read_namespaced_deployment(
        name=deployment_name,
        namespace=namespace
    )

    container = next(filter(lambda x: x.name == container_name, deployment.spec.template.spec.containers))
    if not container:
        logger.logger.error(f"Container {container_name} not found!")
        return None
    
    self_pod = get_self_pod()
    if not self_pod:
        return None

    limits = container.resources.limits
    annotations = self_pod.metadata.annotations
    annotations["csa.custom-self-adapter.net/initialData"] = json.dumps({
        "limits": limits
    })

    coreV1.patch_namespaced_pod(
        name=self_pod.metadata.name,
        namespace=self_pod.metadata.namespace,
        body=self_pod
    )


def get_limits():
    csa_name = os.getenv("CSA_NAME")
    csa_namespace = os.getenv("CSA_NAMESPACE")
    if not csa_name or not csa_namespace:
        logger.logger.error("CSA_NAME or CSA_NAMESPACE not defined!")
        return None
    
    customApi = client.CustomObjectsApi()
    csa = customApi.get_namespaced_custom_object_status(
        "custom-self-adapter.net", "v1", csa_namespace, "customselfadapters", csa_name
    )
    return csa['status']['initialData'] if 'initialData' in csa['status'] else None
