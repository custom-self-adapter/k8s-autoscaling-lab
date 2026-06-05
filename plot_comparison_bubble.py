import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.lines import Line2D

from plot_helper import format_byte_size, padded_axis_upper, scale_bubble_sizes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Gera um grafico de bolhas por cenario a partir do CSV "
            "compartilhado de resumo."
        )
    )
    parser.add_argument(
        "--output",
        default="tests/results/compare_bubble.png",
        help="Arquivo PNG de saida.",
    )
    parser.add_argument(
        "--summary-csv",
        default="tests/results/compare_summary.csv",
        help="Arquivo CSV com os agregados por cenario e metrica.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Abre a figura interativamente alem de salvar o arquivo.",
    )
    return parser


def select_legend_size_values(values: pd.Series, count: int = 2) -> list[float]:
    numeric = pd.to_numeric(values, errors="coerce")
    finite = np.sort(np.unique(numeric[np.isfinite(numeric)]))
    if finite.size == 0:
        return []
    if finite.size == 1 or count <= 1:
        return [float(finite[0])]
    return [float(finite[0]), float(finite[-1])]


def build_plot(summary_df: pd.DataFrame, output_path: Path) -> None:
    required_metrics = [
        "pods_mean",
        "cpu_limits_mean",
        "slo_breach_success_rate",
        "response_size_mean",
    ]
    plot_summary = (
        summary_df[summary_df["metric"].isin(required_metrics)]
        .pivot_table(
            index=["order", "configuration", "label"],
            columns="metric",
            values="mean",
            aggfunc="first",
        )
        .reset_index()
    )
    plot_df = (
        plot_summary.sort_values(["order", "configuration"])
        .dropna(subset=required_metrics)
        .reset_index(drop=True)
    )
    if plot_df.empty:
        raise SystemExit("Nao ha dados suficientes para gerar o grafico de bolhas.")

    plot_df["resource_usage"] = pd.to_numeric(
        plot_df["pods_mean"], errors="coerce"
    ) * pd.to_numeric(plot_df["cpu_limits_mean"], errors="coerce")
    plot_df["slo_breach_success_rate"] = pd.to_numeric(
        plot_df["slo_breach_success_rate"], errors="coerce"
    )
    plot_df["response_size_mean"] = pd.to_numeric(
        plot_df["response_size_mean"], errors="coerce"
    )
    plot_df = (
        plot_df.replace([np.inf, -np.inf], np.nan)
        .dropna(
            subset=["resource_usage", "slo_breach_success_rate", "response_size_mean"]
        )
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
                label=format_byte_size(float(value), precision=2),
            )
        )
    configuration_handles = [
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

    configuration_legend = ax.legend(
        handles=configuration_handles,
        title="Cenarios",
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        borderaxespad=0.0,
        frameon=True,
    )
    ax.add_artist(configuration_legend)

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
    output_path = Path(args.output)
    summary_path = Path(args.summary_csv)

    summary_df = pd.read_csv(summary_path)
    build_plot(summary_df, output_path)

    print(f"Grafico salvo em: {output_path}")
    print(f"Resumo lido de: {summary_path}")

    if args.show:
        plt.show()


if __name__ == "__main__":
    main()
