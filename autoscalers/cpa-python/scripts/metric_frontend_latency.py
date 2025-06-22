import sys
import json
from adapter_logger import AdapterLogger


def main():
    logger = AdapterLogger("metric_frontend_latency")

    spec = json.loads(sys.stdin.read())
    
    kmetrics = spec["kubernetesMetrics"][0]
    current_replicas = kmetrics['current_replicas']
    target_value = kmetrics['spec']['external']['target']['value'] # "2500m"
    current_value = kmetrics['external']['current']['value'] # 10000000 ou 10000m

    metrics_result = json.dumps(
        {
            "current_replicas": current_replicas,
            "target_latency": target_value,
            "ingress_latency": current_value
        }
    )

    logger.logger.debug(metrics_result)
    sys.stdout.write(metrics_result)
    

if __name__ == "__main__":
    main()