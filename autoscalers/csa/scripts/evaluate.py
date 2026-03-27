import json
import math
import sys

from adapt_base import AdaptContext, load_config
from adapt_cpu import PARAM_CPU_MULTIPLIER
from adapt_tag import PARAM_TAG_UP, PARAM_UPDATE_CPU
from adapter_logger import AdapterLogger
from initial_data import get_stored_cpu_limit, store_cpu_limit
from kubernetes.utils.quantity import parse_quantity

STRATEGY_REPLICAS = "adapt_replicas"
STRATEGY_TAG = "adapt_tag"
STRATEGY_CPU = "adapt_cpu"


def main(spec_raw: str):
    ctx = AdaptContext(spec_raw, "evaluate")
    ctx.logger.info("Starting evaluate script")

    config = load_config()
    if config is None:
        # Error was already written to stderr
        ctx.logger.error("config is None")
        return
    ctx.logger.info("  loaded config")

    spec = json.loads(spec_raw)
    metrics = json.loads(spec["metrics"][0]["value"])
    ctx.logger.info("  loaded spec data")

    enabled_strategies = config.get("enabled_strategies", (STRATEGY_REPLICAS))
    min_replicas = config.get("minReplicas", 1)
    max_replicas = config.get("maxReplicas", 10)
    max_cpu: int = config.get("maxCPU", 1000)
    ctx.logger.info("  parsed config data")

    current_value = int(parse_quantity(metrics["current_value"]))
    target_value = int(parse_quantity(metrics["target_value"])) * 1000
    rate = current_value / target_value
    ctx.logger.info(f"rate {current_value} / {target_value} = {rate}")

    ctx.logger.info(f"plan for rate {rate}; stragegies {enabled_strategies}")

    current_replicas = ctx.resource["spec"]["replicas"]
    current_mcpu = ctx.get_current_mcpu()
    if not current_mcpu:
        ctx.logger.error("Current CPU limit not found or unparsable")
        return
    initial_cpu_data = get_stored_cpu_limit() or 0
    if not initial_cpu_data:
        spec_mcpu = ctx.get_spec_mcpu()
        store_cpu_limit(spec_mcpu)
    initial_mcpu = int(initial_cpu_data)

    # HPA Logic to scale replicas
    desired_replicas = math.ceil(current_replicas * rate)

    if rate >= 0.95:
        if STRATEGY_REPLICAS in enabled_strategies and current_replicas < max_replicas:
            desired_replicas = min(desired_replicas, max_replicas)
            write_evaluation(ctx, STRATEGY_REPLICAS, {"replicas": desired_replicas})
            return
        if STRATEGY_CPU in enabled_strategies and current_mcpu < max_cpu:
            write_evaluation(ctx, STRATEGY_CPU, {PARAM_CPU_MULTIPLIER: rate})
            return
        if STRATEGY_TAG in enabled_strategies:
            write_evaluation(
                ctx,
                STRATEGY_TAG,
                {
                    PARAM_TAG_UP: False,
                    PARAM_UPDATE_CPU: STRATEGY_CPU in enabled_strategies,
                },
            )
            return

    if rate < 0.90:
        if STRATEGY_REPLICAS in enabled_strategies and current_replicas > min_replicas:
            desired_replicas = max(desired_replicas, min_replicas)
            write_evaluation(ctx, STRATEGY_REPLICAS, {"replicas": desired_replicas})
            return
        if STRATEGY_CPU in enabled_strategies and current_mcpu > initial_mcpu:
            write_evaluation(ctx, STRATEGY_CPU, {PARAM_CPU_MULTIPLIER: rate})
            return
        if STRATEGY_TAG in enabled_strategies:
            write_evaluation(ctx, STRATEGY_TAG, {PARAM_TAG_UP: True})
            return

    ctx.logger.info("No adaptation selected")


def write_evaluation(ctx: AdaptContext, strategy, params):
    evaluation = {"strategy": strategy, "parameters": params}
    ctx.logger.info(json.dumps(evaluation))
    sys.stdout.write(json.dumps(evaluation))


if __name__ == "__main__":
    AdapterLogger("eval_main").logger.info("evaluate main")
    main(sys.stdin.read())
