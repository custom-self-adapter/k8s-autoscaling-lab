"""Image tag adaptation strategy.

Reads boolean spec.evaluation.parameters['tag_up'].
If True, selects the next tag in TAGS; if False, the previous one.
Outputs {"replicas": <int>, "tag": "<new_tag>"} when a change occurs.
"""

import sys
import re
from typing import Any

import initial_data
from adapt_base import run, AdaptContext, StrategyResult, get_container_with_name

TAGS = ["20k", "100k", "200k", "400k", "600k", "800k"]
PARAM_TAG_UP = "tag_up"


def get_image_parts(image: str) -> dict[str, str | None] | None:
    """Parse an image reference into parts or return None if unparseable."""
    pattern = (
        r"^(?P<repository>[\w.\-_]+((?::\d+|)(?=/[a-z0-9._-]+/[a-z0-9._-]+))|)"
        r"(?:/|)(?P<image>[a-z0-9.\-_]+(?:/[a-z0-9.\-_]+|))"
        r"(:(?P<tag>[\w.\-_]{1,127})|)$"
    )
    m = re.match(pattern, image)
    return m.groupdict() if m else None


def replace_image_tag(image: str, tag: str) -> str:
    """Return the same image reference with a new tag."""
    parts = get_image_parts(image)
    if parts is None:
        return image
    repo = parts["repository"] or ""
    img = parts["image"] or ""
    prefix = f"{repo}/" if repo else ""
    return f"{prefix}{img}:{tag}"


def get_adjacent_tag(tag: str, up: bool) -> str | None:
    """Return the next/previous tag in TAGS or None if none exists."""
    try:
        i = TAGS.index(tag)
    except ValueError:
        return None
    j = i + (1 if up else -1)
    return TAGS[j] if 0 <= j < len(TAGS) else None


def strategy(ctx: AdaptContext) -> StrategyResult | None:
    """Adapt the container image tag one step up or down within the closed TAGS set."""
    params = ctx.spec.get("evaluation", {}).get("parameters", {})
    if PARAM_TAG_UP not in params:
        ctx.logger.error(f"Parameters must include '{PARAM_TAG_UP}' (bool)")
        return None

    container = get_container_with_name(ctx.deployment, "znn")
    if container is None:
        ctx.logger.error("Container 'znn' not found in deployment")
        return None

    parts = get_image_parts(container.image)
    if parts is None or not parts.get("tag"):
        ctx.logger.fatal(f"Could not identify tag in current container image: {container.image}")
        return None

    current_tag = parts.get("tag")
    initial_data.store_tag(current_tag)

    if params[PARAM_TAG_UP]:
        initial_tag = initial_data.get_stored_tag()
        if initial_tag in TAGS and current_tag == initial_tag:
            ctx.logger.info(f"{current_tag} is the initial tag, not adapting above it")
            return None

    new_tag = get_adjacent_tag(current_tag, params[PARAM_TAG_UP])
    if new_tag is None:
        ctx.logger.info(
            f"No change possible for tag {current_tag} direction {'up' if params[PARAM_TAG_UP] else 'down'}"
        )
        return None

    container.image = replace_image_tag(container.image, new_tag)
    ctx.logger.info(f"Adapting tag to {container.image}")

    def build_output(patched: Any) -> dict[str, Any]:
        patched_container = get_container_with_name(patched, "znn")
        patched_parts = get_image_parts(patched_container.image) if patched_container else None
        return {
            "tag": (patched_parts or {}).get("tag"),
        }

    return StrategyResult(should_patch=True, build_output=build_output)


def main(spec_raw: str) -> None:
    run(spec_raw, logger_name="adapt_tag", strategy=strategy)


if __name__ == "__main__":
    main(sys.stdin.read())
