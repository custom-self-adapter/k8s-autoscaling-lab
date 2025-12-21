import os
import json
from kubernetes import config, client
from adapter_logger import AdapterLogger
from adapt_base import get_container_with_name


CSA_NAME = "CSA_NAME"
CSA_NAMESPACE = "CSA_NAMESPACE"
ANNOTATION_TAG = "csa.custom-self-adapter.net/initialData"


logger = AdapterLogger("initial_data").logger
config.load_incluster_config()
coreV1 = client.CoreV1Api()
appsV1 = client.AppsV1Api()


def get_self_pod():
    # Tries to idenfity running CSA from environment
    csa_name = os.getenv("CSA_NAME")
    csa_namespace = os.getenv("CSA_NAMESPACE")
    if not csa_name or not csa_namespace:
        logger.error("CSA_NAME or CSA_NAMESPACE not defined!")
        return None

    pod = coreV1.read_namespaced_pod(
        name=csa_name,
        namespace=csa_namespace
    )
    if not pod:
        logger.error(f"Pod {csa_namespace}/{csa_name} not found!")
        return None
    return pod


def get_managed_pod(deployment_name, namespace, container_name):
    deployment = appsV1.read_namespaced_deployment(
        name=deployment_name,
        namespace=namespace
    )

    container = get_container_with_name(deployment, container_name)
    if not container:
        logger.error(f"Container {container_name} not found!")
        return None

    return container


def get_csa_status():
    csa_name = os.getenv(CSA_NAME)
    csa_namespace = os.getenv(CSA_NAMESPACE)
    if not csa_name or not csa_namespace:
        logger.error("CSA_NAME or CSA_NAMESPACE not defined!")
        return None

    customApi = client.CustomObjectsApi()
    csa_status = customApi.get_namespaced_custom_object_status(
        "custom-self-adapter.net", "v1", csa_namespace, "customselfadapters", csa_name
    )
    return csa_status


def set_self_annotation(key, value):
    self_pod = get_self_pod()
    if not self_pod:
        return None

    annotations = self_pod.metadata.annotations
    if annotations is None:
        annotations = {}
    annotations[key] = value

    coreV1.patch_namespaced_pod(
        name=self_pod.metadata.name,
        namespace=self_pod.metadata.namespace,
        body=self_pod
    )


def store_tag(tag):
    stored_tag = get_stored_tag()
    if stored_tag is not None:
        return

    set_self_annotation(ANNOTATION_TAG, json.dumps({
        'tag': tag
    }))


def get_stored_tag():
    csa_status = get_csa_status()
    if csa_status is None:
        return None
    if csa_status is not None and ANNOTATION_TAG not in csa_status:
        return None
    return csa_status[ANNOTATION_TAG]['tag']


def store_cpu_limit(cpu_limit):
    stored_cpu_limit = get_stored_cpu_limit()
    if stored_cpu_limit is not None:
        return
    
    set_self_annotation(ANNOTATION_TAG, json.dumps({
        'cpu_limit': cpu_limit
    }))


def get_stored_cpu_limit():
    csa_status = get_csa_status()
    if csa_status is None:
        return None
    if csa_status is not None and ANNOTATION_TAG not in csa_status:
        return None
    return csa_status[ANNOTATION_TAG]['cpu_limit']
