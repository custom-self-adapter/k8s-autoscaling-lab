import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.lines import Line2D

from plot_helper import (
    MetricSpec,
    compute_run_metrics,
    discover_result_files,
    summarize_runs,
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


def format_response_size_legend(value: float) -> str:
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.2f} MiB"
    if value >= 1024:
        return f"{value / 1024:.2f} KiB"
    return f"{value:.0f} B"


def select_legend_size_values(values: pd.Series, count: int = 2) -> list[float]:
    numeric = pd.to_numeric(values, errors="coerce")
    finite = np.sort(np.unique(numeric[np.isfinite(numeric)]))
    if finite.size == 0:
        return []
    if finite.size == 1 or count <= 1:
        return [float(finite[0])]
    return [float(finite[0]), float(finite[-1])]


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

    sns.set_theme(style="whitegrid")

    size_metric = plot_df["response_size_mean"]
    size_lower = float(size_metric.min())
    size_upper = float(size_metric.max())
    bubble_sizes = scale_bubble_sizes(
        size_metric,
        lower=size_lower,
        upper=size_upper,
    )
    hue_order = plot_df["label"].tolist()
    palette_colors = sns.color_palette("tab20", n_colors=len(plot_df))

    fig, ax = plt.subplots(figsize=(13, 8), layout="constrained")
    sns.scatterplot(
        data=plot_df,
        x="resource_usage",
        y="slo_breach_success_rate",
        hue="label",
        hue_order=hue_order,
        palette=palette_colors,
        s=bubble_sizes.to_numpy(dtype=float),
        alpha=0.8,
        edgecolor="#222222",
        linewidth=1.0,
        legend=False,
        ax=ax,
    )

    ax.set_xlabel("Uso medio de recursos (pods x kube_pod_cpu_limits)")
    ax.set_ylabel("Requisicoes acima do SLO, apenas sucesso (%)")

    ax.set_xlim(0, padded_axis_upper(plot_df["resource_usage"], minimum=1.0))
    ax.set_ylim(0, padded_axis_upper(plot_df["slo_breach_success_rate"], minimum=0.1))

    reference_values = select_legend_size_values(plot_df["response_size_mean"], count=2)
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
                label=format_response_size_legend(float(value)),
            )
        )
    scenario_handles = [
        Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            markerfacecolor=palette_colors[idx],
            markeredgecolor="#222222",
            markersize=8,
            label=label,
        )
        for idx, label in enumerate(hue_order)
    ]

    scenario_legend = ax.legend(
        handles=scenario_handles,
        title="Cenarios",
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        borderaxespad=0.0,
        frameon=True,
    )
    ax.add_artist(scenario_legend)

    ax.legend(
        handles=size_handles,
        title="Tamanho medio da resposta",
        loc="upper left",
        bbox_to_anchor=(1.02, 0.38),
        borderaxespad=0.0,
        frameon=True,
        labelspacing=2,
        handletextpad=1.6,
        handleheight=3.5,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight", dpi=300)


def main() -> None:
    args = build_parser().parse_args()
    results_dir = Path(args.results_dir)
    output_path = Path(args.output)
    summary_path = Path(args.summary_csv)

    discovered = discover_result_files(results_dir, SCENARIO_LABELS)
    run_rows = [compute_run_metrics(row) for _, row in discovered.iterrows()]
    run_df = pd.DataFrame(run_rows).sort_values(["order", "run", "scenario"])
    summary_df = summarize_runs(run_df, METRICS, sort_columns=("metric", "order", "scenario"))

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
