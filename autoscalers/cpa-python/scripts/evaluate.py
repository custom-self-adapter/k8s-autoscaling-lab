import json
import sys
import math
import adapt_quality
from adapter_logger import AdapterLogger


max_replicas = 10


def main():
    logger = AdapterLogger("metric_frontend_latency")
    logger.logger.debug("Init evaluate")

    spec = json.loads(sys.stdin.read())
    metrics = json.loads(spec['metrics'][0]['value'])
    logger.logger.debug(json.dumps(metrics, indent=2))

    latency_per_replica = metrics['ingress_latency'] / metrics['current_replicas']
    logger.logger.debug(f"latency per replica: {latency_per_replica}")

    if metrics['ingress_latency'] == 0:
        # no access to resource, scale all the way down
        logger.logger.debug(f"ingress latency is zero")
        output_replicas(1)
        return
    
    target_latency = float(metrics['target_latency'].rstrip('m')) * 1000

    # Using HPA algorithm
    evaluation = math.ceil( metrics['current_replicas'] * ( metrics['ingress_latency'] / target_latency ))
    logger.logger.debug(f"Calculated {evaluation} replicas")
    
    if evaluation <= max_replicas:
        output_replicas(evaluation)
    else:
        # Plan B, change image tag to reduce quality
        resource = spec['resource']
        adapt_quality.down(resource)
        output_replicas(metrics['current_replicas'])
        

def output_replicas(replicas: int):
    sys.stdout.write(json.dumps(
        {
            "targetReplicas": replicas
        }
    ))


if __name__ == "__main__":
    main()
