import json
import math
import sys

import yaml

from adapter_logger import AdapterLogger


def load_config(configfile = '/config.yaml') -> dict | None:
    with open(configfile) as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as e:
            sys.stderr.write(f"failed to parse config file: {e}")
            return None


def main(spec_raw: str):
    logger = AdapterLogger("evaluate")
    logger.logger.info("Starting evaluate script")

    config = load_config()

    spec = json.loads(spec_raw)

    metrics = json.loads(spec['metrics'][0]['value'])
    logger.logger.info(json.dumps(metrics, indent=2))
    resource = spec['resource']

    min_replicas = config['minReplicas'] if config is not None and 'minReplicas' in config else 0
    max_replicas = config['maxReplicas'] if config is not None and 'maxReplicas' in config else 0

    current_latency = metrics['current_latency']
    target_latency = float(metrics['target_latency'].rstrip('m')) * 1000
    rate = current_latency / target_latency

    # if current_latency == 0:
    #     return

    plan(resource, rate, min_replicas, max_replicas)


def plan(resource, rate, min_replicas, max_replicas):
    current_replicas = resource['spec']['replicas']

    logger = AdapterLogger("plan")
    logger.logger.info(f"got rate {rate}")

    if rate >= 0.95:
        logger.logger.info("analyzed POOR")
        write_evaluation('scale_cpu_replicas', {
            'direction': 'up',
            'replicas': math.floor(rate) if current_replicas < max_replicas else 0,
            'cpu': 0.2
        })
        return
    if rate < 0.90:
        logger.logger.info("analyzed EXCEEDED")
        if current_replicas > min_replicas:
            write_evaluation('scale_cpu_replicas', {
                'direction': 'down',
                'replicas': 1
            })
        else:
            write_evaluation('scale_cpu_replicas', {
                'direction': 'down',
                'cpu': 0.2
            })
        return
    logger.logger.info("analyzed SUFFICIENT")
    write_evaluation('scale_cpu_replicas',  {
        'direction': 'down'
        # No parameters = no adapting will be performed
    })


def write_evaluation(strategy, params):
    sys.stdout.write(json.dumps({
        "strategy": strategy,
        "parameters": params
    }))


if __name__ == "__main__":
    main(sys.stdin.read())
