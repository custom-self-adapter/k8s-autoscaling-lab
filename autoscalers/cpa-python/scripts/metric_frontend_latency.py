import sys
import json
import yaml
from adapter_logger import AdapterLogger


def load_config(configfile = '/config.yaml'):
    with open(configfile) as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as e:
            sys.stderr.write(e)
            return None


def main():
    logger = AdapterLogger("metric_frontend_latency")

    spec = json.loads(sys.stdin.read())
    config = load_config()
    
    kmetrics = spec["kubernetesMetrics"][0]
    current_replicas = kmetrics['current_replicas']
    target_value = kmetrics['spec']['external']['target']['value'] # "2500m"
    current_value = kmetrics['external']['current']['value'] # 10000000 ou 10000m

    metrics_result = json.dumps(
        {
            "current_replicas": current_replicas,
            "target_latency": target_value,
            "ingress_latency": current_value,
            "minReplicas": config['minReplicas'],
            "maxReplicas": config['maxReplicas']
        }
    )
    
    sys.stdout.write(metrics_result)
    

if __name__ == "__main__":
    main()