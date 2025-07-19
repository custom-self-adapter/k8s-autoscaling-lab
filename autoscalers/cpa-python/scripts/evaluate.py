import json
import sys
import math
import adapt_quality
from adapter_logger import AdapterLogger


def main():
    logger = AdapterLogger("evaluate")
    logger.logger.debug("Init evaluate")

    spec = json.loads(sys.stdin.read())
    # logger.logger.info(json.dumps(spec['metrics'], indent=2))
    metrics = json.loads(spec['metrics'][0]['value'])
    minReplicas = metrics['minReplicas']
    maxReplicas = metrics['maxReplicas']
    currentReplicas = metrics['current_replicas']
    logger.logger.debug(json.dumps(metrics, indent=2))

    latency_per_replica = metrics['ingress_latency'] / metrics['current_replicas']
    logger.logger.debug(f"latency per replica: {latency_per_replica}")

    target_latency = float(metrics['target_latency'].rstrip('m')) * 1000

    # Using HPA algorithm
    evaluation = math.ceil( metrics['current_replicas'] * ( metrics['ingress_latency'] / target_latency ))
    logger.logger.debug(f"Calculated {evaluation} replicas")

    if evaluation > minReplicas and evaluation < maxReplicas:
        logger.logger.debug(f"Scaling to {evaluation} replicas")
        output_replicas(evaluation)
        return

    if evaluation <= minReplicas:
        namespace = spec['resource']['metadata']['namespace']
        name = spec['resource']['metadata']['name']
        container = 'znn'
        logger.logger.debug("Adapting quality up")
        adapt_quality.up(container, name, namespace)
        output_replicas(evaluation)
        return

    if evaluation >= maxReplicas:
        namespace = spec['resource']['metadata']['namespace']
        name = spec['resource']['metadata']['name']
        container = 'znn'
        logger.logger.debug("Adapting quality down")
        adapt_quality.down(container, name, namespace)
        output_replicas(evaluation)
        return


def output_replicas(replicas: int):
    sys.stdout.write(json.dumps(
        {
            "targetReplicas": replicas
        }
    ))


if __name__ == "__main__":
    main()
