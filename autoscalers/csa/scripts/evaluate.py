import json
import math
import sys
import yaml

from adapter_logger import AdapterLogger
from adapt_tag import PARAM_TAG_UP


STRATEGY_REPLICAS = "adapt_replicas"
STRATEGY_TAG = "adapt_tag"


logger = AdapterLogger("evaluate").logger
logger.info("Evaluate loading...")


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

    current_value = metrics['current_value']
    target_value = float(metrics['target_value'].rstrip('m')) * 1000
    rate = current_value / target_value

    plan(resource, rate, min_replicas, max_replicas)


def plan(resource, rate, min_replicas, max_replicas):
    logger.info(f"plan for rate {rate}")

    current_replicas = resource['spec']['replicas']
    # HPA Logic to scale replicas

    if rate >= 1:
        logger.info(f"rate above 1: {math.ceil(rate)}")
        desired_replicas = current_replicas * math.ceil(rate)
        logger.info(f"desired_replicas {desired_replicas}")

        # Respects max_replicas
        if desired_replicas > max_replicas:
            desired_replicas = max_replicas

        if desired_replicas > current_replicas:
            write_evaluation(STRATEGY_REPLICAS, {
                'replicas': desired_replicas
            })
        else:
            write_evaluation(STRATEGY_TAG, {
                PARAM_TAG_UP: False
            })
    else:
        logger.info(f"rate bellow 1: {rate}")
        desired_replicas = math.ceil(current_replicas * rate)
        logger.info(f"desired_replicas {desired_replicas}")
        
        # Respect min_replicas
        if desired_replicas < min_replicas:
            desired_replicas = min_replicas

        if desired_replicas < current_replicas:
            write_evaluation(STRATEGY_REPLICAS, {
                'replicas': desired_replicas
            })
        else:
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
