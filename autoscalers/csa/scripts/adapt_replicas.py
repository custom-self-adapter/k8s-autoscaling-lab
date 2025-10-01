"""Replica scaling strategy.

Reads desired replica count from spec.evaluation.parameters.replicas (int),
patches the Deployment, and outputs {"replicas": <final_value>}.
"""

import sys
from typing import Any

from adapt_base import run, AdaptContext, StrategyResult


def strategy(ctx: AdaptContext) -> StrategyResult | None:
    """Scale the Deployment to the requested number of replicas or no-op on invalid params."""
    params: dict[str, Any] = ctx.spec.get("evaluation", {}).get("parameters", {})
    replicas = params.get("replicas")

    if not isinstance(replicas, int):
        ctx.logger.error("Parameters must include integer 'replicas'")
        return None

    ctx.logger.info(f"Scaling to {replicas} replicas")
    ctx.deployment.spec.replicas = replicas

    def build_output(patched) -> dict[str, Any]:
        return {"replicas": patched.spec.replicas}

    return StrategyResult(should_patch=True, build_output=build_output)


def main(spec_raw: str) -> None:
    run(spec_raw, logger_name="adapt_repl", strategy=strategy)


if __name__ == "__main__":
    main(sys.stdin.read())
