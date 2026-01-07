#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_item_title(attributes: dict) -> str | None:
    quality = attributes.get("quality")
    replicas = attributes.get("replicas")
    if quality and replicas is not None:
        label = "Replica" if replicas == 1 else "Replicas"
        return f"{replicas} {label} Quality {quality}"
    max_surge = attributes.get("maxSurgePct")
    max_unavailable = attributes.get("maxUnavailablePct")
    if max_surge is not None and max_unavailable is not None:
        return (
            f"Deployment with maxSurge {max_surge}% and "
            f"maxUnavailable {max_unavailable}%"
        )
    return None


def build_image_name(attributes: dict) -> str:
    scenario = attributes.get("scenario")
    if scenario == "baseline":
        return f"0_baseline_{attributes['replicas']}_{attributes['quality']}.png"
    if scenario == "hpa":
        behavior = attributes.get("behavior", "default")
        quality = attributes.get("quality")
        if behavior == "fast_scale_down":
            return f"1_hpa_fast_{quality}.png"
        return f"1_hpa_{quality}.png"
    if scenario == "csa":
        mode = attributes.get("mode")
        if mode == "horizontal":
            return "2_csa_h.png"
        if mode == "horizontal_quality":
            max_surge = attributes.get("maxSurgePct")
            return f"3_csa_hq_surge{max_surge}.png"
    return f"{attributes.get('scenario', 'output')}.png"


def build_image_title(attributes: dict) -> str | None:
    if attributes.get("scenario") != "baseline":
        return None
    replicas = attributes.get("replicas")
    quality = attributes.get("quality")
    label = "Replica" if replicas == 1 else "Replicas"
    suffix = f" @{quality}" if quality and quality != "800k" else ""
    return f"Baseline {replicas} {label}{suffix}"


def write_markdown(data: dict, output_md: Path) -> None:
    lines = [f"# {data['title']}", ""]

    for section in data.get("sections", []):
        lines.append(f"## {section['title']}")
        note = section.get("note")
        if note:
            lines.append(note)
        items = section.get("items", [])
        for item in items:
            attributes = item.get("attributes", {})
            title = build_item_title(attributes)
            if title:
                lines.append(f"### {title}")
            csv_name = item["csv"]
            if not csv_name.endswith(".csv"):
                csv_name = f"{csv_name}.csv"
            alt = f"tests/results/{csv_name}"
            image = build_image_name(attributes)
            image_title = build_image_title(attributes)
            if image_title:
                lines.append(f'![{alt}]({image} "{image_title}")')
            else:
                lines.append(f"![{alt}]({image})")
            lines.append("")

    output_md.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def iter_tasks(data: dict):
    for section in data.get("sections", []):
        for item in section.get("items", []):
            attributes = item.get("attributes", {})
            csv_name = item["csv"]
            if not csv_name.endswith(".csv"):
                csv_name = f"{csv_name}.csv"
            yield csv_name, build_image_name(attributes)


def main() -> int:
    root_dir = Path(__file__).resolve().parent
    input_json = root_dir / "tests/results/exemplars.json"
    output_md = root_dir / "tests/results/exemplars.md"

    if not input_json.is_file():
        print(f"Missing input file: {input_json}", file=sys.stderr)
        return 1

    data = load_json(input_json)
    write_markdown(data, output_md)

    plot_script = root_dir / "plot_graphs.py"
    for csv_name, png_name in iter_tasks(data):
        subprocess.run(
            [
                sys.executable,
                str(plot_script),
                str(root_dir / "tests/results" / csv_name),
                str(root_dir / "tests/results" / png_name),
            ],
            check=True,
        )

    print(f"Wrote {output_md}")
    return 0


if __name__ == "__main__":
    main()
