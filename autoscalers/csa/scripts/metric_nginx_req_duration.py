import json
import sys

from adapter_logger import AdapterLogger


def main(spec_raw: str):
    logger = AdapterLogger("metric").logger

    spec = json.loads(spec_raw)

    logger.info("Starting metric script")
    kmetrics = spec["kubernetesMetrics"][0]
    current_replicas = spec['resource']['spec']['replicas']
    target_value = kmetrics['spec']['external']['target']['value']
    current_value = kmetrics['external']['current']['value'] # 10000000 ou 10000m

    metrics_result = json.dumps(
        {
            "current_replicas": current_replicas,
            "target_value": target_value,
            "current_value": current_value
        }
    )

    sys.stdout.write(metrics_result)


if __name__ == "__main__":
    main(sys.stdin.read())
