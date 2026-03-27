import json
import os

from adapter_logger import AdapterLogger
from kubernetes import client, config

CSA_NAME = "CSA_NAME"
CSA_NAMESPACE = "CSA_NAMESPACE"
ANNOTATION_TAG = "csa.custom-self-adapter.net/initialData"
INITIAL_DATA_STATUS = "initialData"


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

    pod = coreV1.read_namespaced_pod(name=csa_name, namespace=csa_namespace)
    if not pod:
        logger.error(f"Pod {csa_namespace}/{csa_name} not found!")
        return None
    return pod


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
    return csa_status.get("status")


def set_self_annotation(key: str, value: dict[str, str]):
    self_pod = get_self_pod()
    if not self_pod:
        logger.error("Could not find CSA pod")
        return None

    csa_status: dict[str, str] = get_csa_status()
    logger.info(csa_status)
    logger.info(value)
    if csa_status and INITIAL_DATA_STATUS in csa_status:
        # Merge new value with existing one
        initial_data = json.loads(csa_status[INITIAL_DATA_STATUS])
        value = initial_data | value
        logger.info(value)
    
    annotations = self_pod.metadata.annotations
    if annotations is None:
        annotations = {}
    annotations[key] = json.dumps(value)

    coreV1.patch_namespaced_pod(
        name=self_pod.metadata.name,
        namespace=self_pod.metadata.namespace,
        body=self_pod,
    )


def get_stored_data(param: str) -> str:
    csa_status = get_csa_status()
    if csa_status is None:
        logger.info("csa_status is None")
        return ""
    if INITIAL_DATA_STATUS not in csa_status:
        logger.info(f"{INITIAL_DATA_STATUS} not found in csa_status")
        return ""
    status_value = json.loads(csa_status.get(INITIAL_DATA_STATUS, ""))
    return status_value.get(param, "")


def store_data(param: str, data: str):
    stored_data = get_stored_data(param)
    if stored_data is not None and stored_data != "":
        # Avoid overwriting a initialData
        return
    set_self_annotation(ANNOTATION_TAG, {param: data})


def store_tag(tag):
    store_data("tag", tag)


def get_stored_tag():
    return get_stored_data("tag")


def store_cpu_limit(cpu_limit):
    store_data("cpu_limit", cpu_limit)


def get_stored_cpu_limit():
    return get_stored_data("cpu_limit")
