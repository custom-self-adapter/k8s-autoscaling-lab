"""Replica scaling strategy.

Reads desired replica count from spec.evaluation.parameters.replicas (int),
patches the Deployment, and outputs {"replicas": <final_value>}.
"""

import json
import sys

from adapt_base import build_context


def main(spec_raw: str) -> None:
    ctx = build_context(spec_raw, logger_name="adapt_repl")
    if ctx is None:
        return
    
    ctx.logger.info("Starting adapt_replicas script")

    params = ctx.spec.get("evaluation", {}).get("parameters", {})
    replicas = params.get("replicas")

    if not isinstance(replicas, int):
        ctx.logger.error("Parameters must include integer 'replicas'")
        return None

    ctx.logger.info(f"Scaling to {replicas} replicas")
    ctx.deployment.spec.replicas = replicas
    try:
        ctx.apps.patch_namespaced_deployment(
            name=ctx.res_name, namespace=ctx.res_ns, body=ctx.deployment
        )
        sys.stdout.write(json.dumps({"replicas": replicas}))
    except Exception as e:
        ctx.logger.error(f"Failed to patch Deployment {ctx.res_ns}/{ctx.res_name}: {e}")
        sys.stdout.write(json.dumps({"result": "error"}))


if __name__ == "__main__":
    main(sys.stdin.read())
