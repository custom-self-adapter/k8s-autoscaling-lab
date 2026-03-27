import json
import sys

import initial_data
from adapt_base import (
    AdaptContext,
    format_mcpu,
    load_config,
)

PARAM_CPU_MULTIPLIER = "cpu_multiplier"
DEFAULT_CONTAINER_NAME = "znn"


def main(spec_raw: str) -> None:
    try:
        ctx = AdaptContext(spec_raw, logger_name="adapt_cpu")
    except ValueError:
        return

    params = ctx.spec.get("evaluation", {}).get("parameters", {})
    multiplier = params.get(PARAM_CPU_MULTIPLIER)
    ctx.logger.info(f"adapt_cpu for rate {multiplier}")

    if not isinstance(multiplier, (float, int)):
        ctx.logger.error(
            f"Parameter '{PARAM_CPU_MULTIPLIER}' must be a number; it's {multiplier}"
        )
        sys.stdout.write(json.dumps({"result": "error"}))
        return

    if ctx.rollout_in_progress():
        ctx.logger.info("Rollout in progress, skipping deployment patch")
        sys.stdout.write(json.dumps({"result": "skip"}))
        return

    config = load_config()
    if config is None:
        ctx.logger.error("Could not parse config")
        sys.stdout.write(json.dumps({"result": "error"}))
        return
    max_cpu = config.get("maxCPU", 1000)

    initial_mcpu_data = initial_data.get_stored_cpu_limit()
    ctx.logger.info(f"Read initial_mcpu_data {initial_mcpu_data}.")
    if not initial_mcpu_data:
        spec_mcpu = ctx.get_spec_mcpu()
        ctx.logger.info(f"Read spec_mcpu {spec_mcpu}")
        if not spec_mcpu:
            ctx.logger.error("No limits found in the containers specs!")
            sys.stdout.write(json.dumps({"result": "error"}))
            return None
        ctx.logger.info(f"Storing initial cpu limit {spec_mcpu}")
        initial_data.store_cpu_limit(spec_mcpu)
        initial_mcpu_data = spec_mcpu

    pod_list = ctx.get_running_pods()
    if not pod_list:
        ctx.logger.error(
            f"Could not find pods for deployment {ctx.res_name} in namespace {ctx.res_ns}"
        )
        sys.stdout.write(json.dumps({"result": "error"}))
        return

    current_mcpu = ctx.get_current_mcpu()
    if not current_mcpu:
        ctx.logger.error("Current CPU limit not found or unparsable")
        sys.stdout.write(json.dumps({"result": "error"}))
        return None

    initial_mcpu = int(initial_mcpu_data)

    new_mcpu = int(round(int(current_mcpu) * float(multiplier)))
    ctx.logger.info(f"Calculated new_mcpu {new_mcpu}")
    if new_mcpu > max_cpu:
        new_mcpu = min(new_mcpu, max_cpu)
        ctx.logger.info(f"new_mcpu capped to {new_mcpu}")
    if new_mcpu < initial_mcpu:
        new_mcpu = max(new_mcpu, initial_mcpu)
        ctx.logger.info(f"new_mcpu capped to {new_mcpu}")

    resize_body = {
        "spec": {
            "containers": [
                {
                    "name": container_name,
                    "resources": {"limits": {"cpu": format_mcpu(new_mcpu)}},
                }
                for container_name in ["znn", "nginx"]
            ]
        }
    }

    for pod in pod_list:
        try:
            _ = ctx.core.patch_namespaced_pod_resize(
                name=pod.metadata.name, namespace=ctx.res_ns, body=resize_body
            )
        except Exception as e:
            ctx.logger.error(f"Failed to resize pod {ctx.res_ns}/{pod}: {e}")
            sys.stdout.write(json.dumps({"result": "error"}))
            return

    ctx.logger.info(f"Scaled cpu to {new_mcpu}")
    sys.stdout.write(json.dumps({"cpu": new_mcpu}))


if __name__ == "__main__":
    main(sys.stdin.read())
