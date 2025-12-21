import json
import math
import sys
import yaml

from kubernetes.utils.quantity import parse_quantity

from adapter_logger import AdapterLogger
from adapt_tag import PARAM_TAG_UP


STRATEGY_REPLICAS = "adapt_replicas"
STRATEGY_TAG = "adapt_tag"


logger = AdapterLogger("evaluate").logger


def load_config(configfile = '/config.yaml') -> dict | None:
    with open(configfile) as file:
        try:
            config = yaml.safe_load(file)
            if config is None:
                sys.stderr.write("config file was empty")
                return None
            return config
        except yaml.YAMLError as e:
            sys.stderr.write(f"failed to parse config file: {e}")
            return None


def main(spec_raw: str):
    logger.info("Starting evaluate script")

    config = load_config()
    if config is None:
        # Error was already written to stderr
        logger.error("config is None")
        return

    spec = json.loads(spec_raw)

    metrics = json.loads(spec['metrics'][0]['value'])
    logger.info(json.dumps(metrics))
    resource = spec['resource']

    min_replicas = config['minReplicas'] if 'minReplicas' in config else 0
    max_replicas = config['maxReplicas'] if 'maxReplicas' in config else 0

    current_value = int(parse_quantity(metrics['current_value']))
    target_value = int(parse_quantity(metrics['target_value'])) * 1000
    logger.info(f"{current_value} / {target_value}")
    rate = current_value / target_value

    plan(resource, rate, min_replicas, max_replicas)


def plan(resource, rate, min_replicas, max_replicas):
    logger.info(f"plan for rate {rate}")

    current_replicas = resource['spec']['replicas']
    # HPA Logic to scale replicas
    desired_replicas = math.ceil(current_replicas * rate)
    logger.info(f"calculated desired_replicas {desired_replicas}")

    if rate >= 1:
        if current_replicas != max_replicas:
            # Respects max_replicas
            desired_replicas = min(desired_replicas, max_replicas)
            write_evaluation(STRATEGY_REPLICAS, {
                'replicas': desired_replicas
            })
        else:
            # write_evaluation(STRATEGY_REPLICAS, {
            #     'replicas': current_replicas
            # })
            write_evaluation(STRATEGY_TAG, {
                PARAM_TAG_UP: False
            })
    else:
        if current_replicas != min_replicas:
            # Respect min_replicas
            desired_replicas = max(desired_replicas, min_replicas)
            write_evaluation(STRATEGY_REPLICAS, {
                'replicas': desired_replicas
            })
        else:
            # write_evaluation(STRATEGY_REPLICAS, {
            #     'replicas': current_replicas
            # })
            write_evaluation(STRATEGY_TAG, {
                PARAM_TAG_UP: True
            })


def write_evaluation(strategy, params):
    evaluation = {
        "strategy": strategy,
        "parameters": params
    }
    logger.info(json.dumps(evaluation))
    sys.stdout.write(json.dumps(evaluation))


if __name__ == "__main__":
    main(sys.stdin.read())
