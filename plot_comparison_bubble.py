import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from plot_helper import apply_standard_renames, filter_http_success, select_series

PODS_SERIES = "znn_pods_per_tag"
CPU_LIMITS_SERIES = "kube_pod_cpu_limits"
RESP_TIME_SERIES = "loc_response_time"
STATUS_CODE_COL = "loc_status_code"
LOC_RESP_SIZE_COL = "loc_response_size"
SLO_MILLISECONDS = 1000

FILE_PATTERN = re.compile(
    r"(?P<run>\d{2})_(?P<order>\d+)_(?P<scenario>.+)\.csv$"
)

SCENARIO_LABELS = {
    "base_1": "1x0.15",
    "base_5": "5x0.15",
    "base_1000": "1x1",
    "hpa_std": "HPA Std",
    "hpa_fast": "HPA Fast",
    "csa_h": "CSA H",
    "csa_hq_25": "CSA HQ 25",
    "csa_hq_50": "CSA HQ 50",
    "vpa": "VPA",
    "csa_v": "CSA V",
    "csa_vq": "CSA VQ",
}


@dataclass(frozen=True)
class MetricSpec:
    key: str
    title: str
    percent_axis: bool = False


METRICS = [
    MetricSpec("pods_mean", "Media de Pods (ZNN)"),
    MetricSpec("cpu_limits_mean", "Media de kube_pod_cpu_limits"),
    MetricSpec("response_size_mean", "Tamanho medio das respostas (LOC)"),
    MetricSpec("response_time_mean", "Tempo medio das respostas (ms) (LOC)"),
    MetricSpec("success_rate", "Respostas 200 (%) (LOC)", percent_axis=True),
    MetricSpec(
        "slo_breach_rate",
        "Requisicoes acima do SLO (%) (LOC)",
        percent_axis=True,
    ),
    MetricSpec(
        "slo_breach_success_rate",
        "Requisicoes acima do SLO, apenas sucesso (%) (LOC)",
        percent_axis=True,
    ),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Gera um grafico de bolhas por cenario a partir dos CSVs nomeados "
            "como <run>_<sequencial>_<cenario>.csv."
        )
    )
    parser.add_argument(
        "--results-dir",
        default="tests/results",
        help="Diretorio com os CSVs de resultados.",
    )
    parser.add_argument(
        "--output",
        default="tests/results/compare_bubble.png",
        help="Arquivo PNG de saida.",
    )
    parser.add_argument(
        "--summary-csv",
        default="tests/results/compare_bubble_summary.csv",
        help="Arquivo CSV com os agregados por cenario e metrica.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Abre a figura interativamente alem de salvar o arquivo.",
    )
    return parser


def scenario_label(scenario: str) -> str:
    return SCENARIO_LABELS.get(scenario, scenario.replace("_", " ").title())


def discover_result_files(results_dir: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(results_dir.glob("*.csv")):
        match = FILE_PATTERN.fullmatch(path.name)
        if not match:
            continue
        rows.append(
            {
                "file": path,
                "run": match.group("run"),
                "order": int(match.group("order")),
                "scenario": match.group("scenario"),
                "label": scenario_label(match.group("scenario")),
            }
        )
    if not rows:
        raise SystemExit(
            f"Nenhum CSV no padrao <run>_<sequencial>_<cenario>.csv foi encontrado em {results_dir}"
        )
    return pd.DataFrame(rows).sort_values(["order", "run", "scenario"])


def safe_numeric_mean(series: pd.Series) -> float:
    if series is None:
        return math.nan
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    return float(numeric.mean()) if not numeric.empty else math.nan


def compute_run_metrics(file_info: pd.Series) -> dict:
    df = pd.read_csv(file_info["file"])
    df = apply_standard_renames(df)

    pods = df[df["series"] == PODS_SERIES]
    cpu_limits = select_series(df, CPU_LIMITS_SERIES)
    resp_time = select_series(
        df,
        RESP_TIME_SERIES,
        extra_cols=[STATUS_CODE_COL, LOC_RESP_SIZE_COL],
    )

    status_source = (
        resp_time[STATUS_CODE_COL]
        if STATUS_CODE_COL in resp_time.columns
        else pd.Series(dtype=float)
    )
    status_codes = pd.to_numeric(status_source, errors="coerce")
    response_values = pd.to_numeric(resp_time["value"], errors="coerce")

    success_mask = status_codes == 200
    success_rate = float(success_mask.mean() * 100) if len(success_mask) else math.nan

    slo_breach_mask = response_values > SLO_MILLISECONDS
    slo_breach_rate = (
        float(slo_breach_mask.mean() * 100) if len(slo_breach_mask) else math.nan
    )

    resp_time_success = filter_http_success(resp_time, STATUS_CODE_COL)
    success_response_values = pd.to_numeric(
        resp_time_success["value"]
        if "value" in resp_time_success.columns
        else pd.Series(dtype=float),
        errors="coerce",
    )
    slo_breach_success_mask = success_response_values > SLO_MILLISECONDS
    slo_breach_success_rate = (
        float(slo_breach_success_mask.mean() * 100)
        if len(slo_breach_success_mask)
        else math.nan
    )

    return {
        "run": file_info["run"],
        "order": int(file_info["order"]),
        "scenario": file_info["scenario"],
        "label": file_info["label"],
        "file": str(file_info["file"]),
        "pods_mean": safe_numeric_mean(pods["value"]),
        "cpu_limits_mean": safe_numeric_mean(cpu_limits.get("value")),
        "response_size_mean": safe_numeric_mean(resp_time_success.get(LOC_RESP_SIZE_COL)),
        "response_time_mean": safe_numeric_mean(resp_time_success.get("value")),
        "success_rate": success_rate,
        "slo_breach_rate": slo_breach_rate,
        "slo_breach_success_rate": slo_breach_success_rate,
    }


def summarize_runs(run_df: pd.DataFrame) -> pd.DataFrame:
    summary_rows = []
    scenario_cols = ["order", "scenario", "label"]
    for scenario_info, scenario_runs in run_df.groupby(scenario_cols, sort=True):
        order, scenario, label = scenario_info
        for metric in METRICS:
            values = pd.to_numeric(scenario_runs[metric.key], errors="coerce").dropna()
            if values.empty:
                continue
            summary_rows.append(
                {
                    "order": order,
                    "scenario": scenario,
                    "label": label,
                    "metric": metric.key,
                    "metric_title": metric.title,
                    "runs": int(values.count()),
                    "mean": float(values.mean()),
                    "min": float(values.min()),
                    "max": float(values.max()),
                    "median": float(values.median()),
                    "std": float(values.std(ddof=0)),
                    "q25": float(values.quantile(0.25)),
                    "q75": float(values.quantile(0.75)),
                }
            )
    if not summary_rows:
        raise SystemExit(
            "Nao foi possivel calcular agregados a partir dos arquivos encontrados."
        )
    return pd.DataFrame(summary_rows).sort_values(["metric", "order", "scenario"])


def scale_bubble_sizes(
    values: pd.Series,
    min_size: float = 300.0,
    max_size: float = 2600.0,
    lower: float | None = None,
    upper: float | None = None,
) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    finite = numeric[np.isfinite(numeric)]
    if finite.empty:
        return pd.Series(np.full(len(numeric), min_size), index=numeric.index)

    lower = float(finite.min()) if lower is None else float(lower)
    upper = float(finite.max()) if upper is None else float(upper)
    if upper < lower:
        lower, upper = upper, lower
    if math.isclose(lower, upper):
        mid = (min_size + max_size) / 2.0
        return pd.Series(np.full(len(numeric), mid), index=numeric.index)

    scaled = min_size + (numeric - lower) * (max_size - min_size) / (upper - lower)
    return scaled.clip(lower=min_size, upper=max_size).fillna(min_size)


def padded_axis_upper(values: pd.Series, minimum: float, multiplier: float = 1.15) -> float:
    numeric = pd.to_numeric(values, errors="coerce")
    finite = numeric[np.isfinite(numeric)]
    if finite.empty:
        return minimum
    return max(minimum, float(finite.max()) * multiplier)


def format_response_size(value: float) -> str:
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.1f} MiB"
    if value >= 1024:
        return f"{value / 1024:.1f} KiB"
    return f"{value:.0f} B"


def bubble_radius_points(area_points2: float) -> float:
    return math.sqrt(max(area_points2, 0.0) / math.pi)


def bbox_intersects_circle(bbox, center_x: float, center_y: float, radius: float) -> bool:
    closest_x = min(max(center_x, bbox.x0), bbox.x1)
    closest_y = min(max(center_y, bbox.y0), bbox.y1)
    dx = center_x - closest_x
    dy = center_y - closest_y
    return (dx * dx + dy * dy) < (radius * radius)


def label_directions(
    point_xy: tuple[float, float], center_xy: tuple[float, float], index: int
) -> list[tuple[int, int]]:
    dx = point_xy[0] - center_xy[0]
    dy = point_xy[1] - center_xy[1]

    x_dir = 1 if dx >= 0 else -1
    y_dir = 1 if dy >= 0 else -1

    if abs(dx) < 30:
        x_dir = 1 if index % 2 == 0 else -1
    if abs(dy) < 30:
        y_dir = 1 if (index // 2) % 2 == 0 else -1

    candidates = [
        (x_dir, y_dir),
        (x_dir, 0),
        (0, y_dir),
        (x_dir, -y_dir),
        (-x_dir, y_dir),
        (0, -y_dir),
        (-x_dir, 0),
        (-x_dir, -y_dir),
    ]

    unique_candidates: list[tuple[int, int]] = []
    for candidate in candidates:
        if candidate != (0, 0) and candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return unique_candidates


def add_smart_labels(
    fig: plt.Figure,
    ax: plt.Axes,
    plot_df: pd.DataFrame,
    bubble_sizes: pd.Series,
    fontsize: int = 9,
) -> None:
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    dpi_scale = fig.dpi / 72.0
    display_points = ax.transData.transform(
        plot_df[["resource_usage", "slo_breach_success_rate"]].to_numpy()
    )
    plot_center = display_points.mean(axis=0)

    bubble_obstacles = []
    for idx, (x_disp, y_disp) in enumerate(display_points):
        radius_px = bubble_radius_points(float(bubble_sizes.iloc[idx])) * dpi_scale
        bubble_obstacles.append((x_disp, y_disp, radius_px + 6.0))

    occupied_bboxes = []
    placement_order = sorted(
        range(len(plot_df)),
        key=lambda idx: float(bubble_sizes.iloc[idx]),
        reverse=True,
    )

    for placement_rank, point_idx in enumerate(placement_order):
        row = plot_df.iloc[point_idx]
        x_disp, y_disp = display_points[point_idx]
        radius_pts = bubble_radius_points(float(bubble_sizes.iloc[point_idx]))
        base_offset = max(12.0, radius_pts + 6.0)
        directions = label_directions(
            (float(x_disp), float(y_disp)),
            (float(plot_center[0]), float(plot_center[1])),
            placement_rank,
        )

        placed_annotation = None
        fallback_annotation = None
        for scale in (1.0, 1.35, 1.7, 2.1, 2.5):
            for dx_dir, dy_dir in directions:
                dx_pts = dx_dir * base_offset * scale
                dy_pts = dy_dir * base_offset * scale
                annotation = ax.annotate(
                    row["label"],
                    xy=(row["resource_usage"], row["slo_breach_success_rate"]),
                    xytext=(dx_pts, dy_pts),
                    textcoords="offset points",
                    ha="left" if dx_dir > 0 else "right" if dx_dir < 0 else "center",
                    va="bottom" if dy_dir > 0 else "top" if dy_dir < 0 else "center",
                    fontsize=fontsize,
                    bbox={
                        "boxstyle": "round,pad=0.2",
                        "facecolor": "white",
                        "edgecolor": "none",
                        "alpha": 0.75,
                    },
                    arrowprops={
                        "arrowstyle": "-",
                        "color": "#555555",
                        "lw": 0.8,
                        "alpha": 0.6,
                        "shrinkA": 3,
                        "shrinkB": 6,
                    },
                    zorder=4,
                )
                bbox = annotation.get_window_extent(renderer=renderer).expanded(1.03, 1.12)
                collides_with_label = any(bbox.overlaps(existing) for existing in occupied_bboxes)
                collides_with_bubble = any(
                    bbox_intersects_circle(bbox, bubble_x, bubble_y, bubble_radius)
                    for bubble_x, bubble_y, bubble_radius in bubble_obstacles
                    if bubble_x != x_disp or bubble_y != y_disp
                )
                if not collides_with_label and not collides_with_bubble:
                    occupied_bboxes.append(bbox)
                    placed_annotation = annotation
                    break
                if fallback_annotation is None:
                    fallback_annotation = annotation
                else:
                    annotation.remove()
            if placed_annotation is not None:
                break

        if placed_annotation is None and fallback_annotation is not None:
            occupied_bboxes.append(
                fallback_annotation.get_window_extent(renderer=renderer).expanded(1.03, 1.12)
            )
        elif placed_annotation is None:
            ax.annotate(
                row["label"],
                xy=(row["resource_usage"], row["slo_breach_success_rate"]),
                xytext=(0, base_offset),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=fontsize,
                bbox={
                    "boxstyle": "round,pad=0.2",
                    "facecolor": "white",
                    "edgecolor": "none",
                    "alpha": 0.75,
                },
                arrowprops={
                    "arrowstyle": "-",
                    "color": "#555555",
                    "lw": 0.8,
                    "alpha": 0.6,
                },
                zorder=4,
            )


def build_plot(
    summary_df: pd.DataFrame, run_df: pd.DataFrame, output_path: Path
) -> None:
    required_metrics = [
        "pods_mean",
        "cpu_limits_mean",
        "slo_breach_success_rate",
        "response_size_mean",
    ]
    plot_summary = (
        summary_df[summary_df["metric"].isin(required_metrics)]
        .pivot_table(
            index=["order", "scenario", "label"],
            columns="metric",
            values="mean",
            aggfunc="first",
        )
        .reset_index()
    )
    run_counts = (
        run_df.groupby(["order", "scenario", "label"], as_index=False)
        .size()
        .rename(columns={"size": "run_count"})
    )
    plot_df = (
        run_counts.merge(plot_summary, on=["order", "scenario", "label"], how="left")
        .sort_values(["order", "scenario"])
        .dropna(subset=required_metrics)
        .reset_index(drop=True)
    )
    if plot_df.empty:
        raise SystemExit("Nao ha dados suficientes para gerar o grafico de bolhas.")

    plot_df["resource_usage"] = (
        pd.to_numeric(plot_df["pods_mean"], errors="coerce")
        * pd.to_numeric(plot_df["cpu_limits_mean"], errors="coerce")
    )
    plot_df["slo_breach_success_rate"] = pd.to_numeric(
        plot_df["slo_breach_success_rate"], errors="coerce"
    )
    plot_df["response_size_mean"] = pd.to_numeric(
        plot_df["response_size_mean"], errors="coerce"
    )
    plot_df = (
        plot_df.replace([np.inf, -np.inf], np.nan)
        .dropna(subset=["resource_usage", "slo_breach_success_rate", "response_size_mean"])
        .reset_index(drop=True)
    )
    if plot_df.empty:
        raise SystemExit("Nao ha dados validos para gerar o grafico de bolhas.")

    plt.style.use("bmh")
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "legend.fontsize": 9,
            "savefig.dpi": 300,
        }
    )

    size_metric = plot_df["response_size_mean"]
    size_lower = float(size_metric.min())
    size_upper = float(size_metric.max())
    bubble_sizes = scale_bubble_sizes(
        size_metric,
        lower=size_lower,
        upper=size_upper,
    )
    cmap = plt.get_cmap("tab10")
    colors = [cmap(i % cmap.N) for i in range(len(plot_df))]

    fig, ax = plt.subplots(figsize=(13, 8), layout="constrained")
    ax.scatter(
        plot_df["resource_usage"],
        plot_df["slo_breach_success_rate"],
        s=bubble_sizes,
        c=colors,
        alpha=0.75,
        edgecolors="#222222",
        linewidths=1.1,
    )

    add_smart_labels(fig, ax, plot_df, bubble_sizes, fontsize=9)

    ax.set_xlabel("Uso medio de recursos (pods x kube_pod_cpu_limits)")
    ax.set_ylabel("Requisicoes acima do SLO, apenas sucesso (%)")
    ax.grid(True, linestyle="--", alpha=0.45)

    ax.set_xlim(0, padded_axis_upper(plot_df["resource_usage"], minimum=1.0))
    ax.set_ylim(0, padded_axis_upper(plot_df["slo_breach_success_rate"], minimum=0.1))

    reference_values = np.unique(
        np.round(
            [
                float(plot_df["response_size_mean"].min()),
                float(plot_df["response_size_mean"].median()),
                float(plot_df["response_size_mean"].max()),
            ],
            1,
        )
    )
    size_handles = []
    for value in reference_values:
        marker_size = float(
            scale_bubble_sizes(
                pd.Series([value], dtype=float),
                lower=size_lower,
                upper=size_upper,
            ).iloc[0]
        )
        size_handles.append(
            Line2D(
                [],
                [],
                marker="o",
                linestyle="",
                markerfacecolor="#999999",
                markeredgecolor="#222222",
                alpha=0.45,
                markersize=math.sqrt(marker_size),
                label=format_response_size(float(value)),
            )
        )
    ax.legend(
        handles=size_handles,
        title="Tamanho medio da resposta",
        loc="upper right",
        frameon=True,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")


def main() -> None:
    args = build_parser().parse_args()
    results_dir = Path(args.results_dir)
    output_path = Path(args.output)
    summary_path = Path(args.summary_csv)

    discovered = discover_result_files(results_dir)
    run_rows = [compute_run_metrics(row) for _, row in discovered.iterrows()]
    run_df = pd.DataFrame(run_rows).sort_values(["order", "run", "scenario"])
    summary_df = summarize_runs(run_df)

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(summary_path, index=False)
    build_plot(summary_df, run_df, output_path)

    print(f"Arquivos analisados: {len(run_df)}")
    print(f"Grafico salvo em: {output_path}")
    print(f"Resumo salvo em: {summary_path}")

    if args.show:
        plt.show()


if __name__ == "__main__":
    main()
