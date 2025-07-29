import json
import sys
import math
import adapt_cpu
from adapter_logger import AdapterLogger

# This evaluate script does it's job on evaluating a replicas scale, writing
# the result with the output_replicas function.
# It also calls adapt_cpu to adapt the cpu resources from the managed resource,
# expanding CPA functionality.

def main(logger, spec_raw):

    spec = json.loads(spec_raw)
    metrics = json.loads(spec['metrics'][0]['value'])
    min_replicas = metrics['minReplicas']
    max_replicas = metrics['maxReplicas']
    current_replicas = metrics['current_replicas']

    # latency_per_replica = metrics['ingress_latency'] / metrics['current_replicas']

    ingress_latency = float(metrics['ingress_latency'])
    target_latency = float(metrics['target_latency'].rstrip('m')) * 1000

    rate = ingress_latency / target_latency
    logger.logger.info(f"ingress_latency: {ingress_latency}")
    logger.logger.info(f"target_latency: {target_latency}")
    logger.logger.info(f"latency rate: {rate}")
    namespace = spec['resource']['metadata']['namespace']
    name = spec['resource']['metadata']['name']
    container = 'znn'

    if rate >= 0.95:
        logger.logger.info("analyzed POOR")
        if current_replicas < max_replicas and current_replicas < math.ceil(rate):
            logger.logger.info(f"scaling to {math.ceil(rate)} replicas")
            output_replicas(math.ceil(rate))
        else:
            logger.logger.info(f"scaling to {current_replicas + 1} replicas")
            output_replicas(current_replicas + 1)
        logger.logger.info("Will now call adapt_cpu")
        adapt_cpu.up(container, name, namespace)
        return

    if rate < 0.90:
        logger.logger.info("analyzed EXCEEDED")
        if current_replicas > min_replicas and current_replicas > math.ceil(rate):
            logger.logger.info(f"scaling to {math.floor(rate)} replicas")
            output_replicas(math.ceil(rate))
        else:
            output_replicas(current_replicas)
        logger.logger.info("Will now call adapt_cpu")
        adapt_cpu.down(container, name, namespace)
        return

    output_replicas(current_replicas)


def output_replicas(replicas: int):
    sys.stdout.write(json.dumps(
        {
            "targetReplicas": replicas
        }
    ))


if __name__ == "__main__":
    logger = AdapterLogger("evaluate")
    logger.logger.info("Init evaluate")
    spec_raw = sys.stdin.read()
    logger.logger.info("calling main()")
    main(logger, spec_raw)
