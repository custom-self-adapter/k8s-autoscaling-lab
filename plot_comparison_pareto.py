import argparse
import colorsys
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import to_rgb
from matplotlib.lines import Line2D

from plot_helper import format_byte_size, padded_axis_upper, scale_bubble_sizes


REQUIRED_METRICS = [
    "pods_mean",
    "cpu_limits_mean",
    "slo_breach_success_rate",
    "response_size_mean",
]
CATEGORY_ORDER = ["Baselines", "HPA", "VPA", "CSA", "Outros"]
CATEGORY_BASE_COLORS = {
    "Baselines": "#4C78A8",
    "HPA": "#F58518",
    "VPA": "#54A24B",
    "CSA": "#E45756",
    "Outros": "#777777",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Gera um grafico Pareto por cenario a partir do CSV "
            "compartilhado de resumo."
        )
    )
    parser.add_argument(
        "--output",
        default="tests/results/compare_pareto.png",
        help="Arquivo PNG de saida.",
    )
    parser.add_argument(
        "--summary-csv",
        default="tests/results/compare_summary.csv",
        help="Arquivo CSV com os agregados por cenario e metrica.",
    )
    parser.add_argument(
        "--pareto-csv",
        default="tests/results/compare_pareto.csv",
        help="Arquivo CSV de saida com os pontos do grafico e a marcacao Pareto.",
    )
    parser.add_argument(
        "--response-size-objective",
        choices=["ignore", "minimize", "maximize"],
        default="ignore",
        help=(
            "Como usar response_size_mean no calculo Pareto. "
            "Use ignore para manter apenas os eixos, minimize para preferir "
            "respostas menores, ou maximize para preferir respostas maiores."
        ),
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Abre a figura interativamente alem de salvar o arquivo.",
    )
    return parser


def pareto_frontier_mask(
    df: pd.DataFrame,
    minimize_cols: tuple[str, ...] = ("resource_usage", "slo_breach_success_rate"),
    maximize_cols: tuple[str, ...] = ("response_size_mean",),
    tolerance: float = 1e-12,
) -> pd.Series:
    """Marca pontos nao dominados, minimizando custos e maximizando qualidade."""
    objective_series = []
    for col in minimize_cols:
        objective_series.append(pd.to_numeric(df[col], errors="coerce"))
    for col in maximize_cols:
        objective_series.append(-pd.to_numeric(df[col], errors="coerce"))

    objectives = pd.concat(objective_series, axis=1)
    valid = objectives.notna().all(axis=1)
    mask = pd.Series(False, index=df.index)

    values = objectives.loc[valid].to_numpy(dtype=float)
    valid_index = objectives.loc[valid].index
    for idx, candidate in enumerate(values):
        others = np.delete(values, idx, axis=0)
        if others.size == 0:
            mask.loc[valid_index[idx]] = True
            continue

        weakly_better = np.all(others <= candidate + tolerance, axis=1)
        strictly_better = np.any(others < candidate - tolerance, axis=1)
        mask.loc[valid_index[idx]] = not np.any(weakly_better & strictly_better)

    return mask


def select_legend_size_values(values: pd.Series, count: int = 2) -> list[float]:
    numeric = pd.to_numeric(values, errors="coerce")
    finite = np.sort(np.unique(numeric[np.isfinite(numeric)]))
    if finite.size == 0:
        return []
    if finite.size == 1 or count <= 1:
        return [float(finite[0])]
    return [float(finite[0]), float(finite[-1])]


def configuration_category(configuration: str) -> str:
    normalized = configuration.lower()
    if normalized.startswith("base_"):
        return "Baselines"
    if normalized.startswith("hpa_") or normalized == "hpa":
        return "HPA"
    if normalized.startswith("vpa"):
        return "VPA"
    if normalized.startswith("csa_") or normalized == "csa":
        return "CSA"
    return "Outros"


def color_variants(base_color: str, count: int) -> list[tuple[float, float, float]]:
    hue, lightness, saturation = colorsys.rgb_to_hls(*to_rgb(base_color))
    if count <= 1:
        return [colorsys.hls_to_rgb(hue, lightness, saturation)]

    lightness_values = np.linspace(0.62, 0.38, count)
    saturation_values = np.linspace(0.62, 0.92, count)
    return [
        colorsys.hls_to_rgb(hue, lightness_value, saturation_value)
        for lightness_value, saturation_value in zip(
            lightness_values, saturation_values
        )
    ]


def build_category_colors(plot_df: pd.DataFrame) -> pd.Series:
    colors = pd.Series(index=plot_df.index, dtype=object)
    categories = plot_df["configuration"].map(configuration_category)
    for category in CATEGORY_ORDER:
        category_index = plot_df.index[categories == category]
        if category_index.empty:
            continue

        variants = color_variants(
            CATEGORY_BASE_COLORS[category],
            count=len(category_index),
        )
        for idx, color in zip(category_index, variants):
            colors.loc[idx] = color

    return colors


def add_pareto_frontier(
    plot_df: pd.DataFrame,
    response_size_objective: str,
) -> pd.DataFrame:
    minimize_cols = ("resource_usage", "slo_breach_success_rate")
    maximize_cols = ()
    if response_size_objective == "minimize":
        minimize_cols = (*minimize_cols, "response_size_mean")
    elif response_size_objective == "maximize":
        maximize_cols = ("response_size_mean",)

    updated = plot_df.copy()
    updated["response_size_objective"] = response_size_objective
    updated["pareto_frontier"] = pareto_frontier_mask(
        updated,
        minimize_cols=minimize_cols,
        maximize_cols=maximize_cols,
    )
    return updated


def prepare_plot_data(summary_df: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"order", "configuration", "label", "metric", "mean"}
    missing_columns = sorted(required_columns.difference(summary_df.columns))
    if missing_columns:
        raise SystemExit(
            "CSV de resumo sem colunas obrigatorias: " + ", ".join(missing_columns)
        )

    plot_summary = (
        summary_df[summary_df["metric"].isin(REQUIRED_METRICS)]
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
        .dropna(subset=REQUIRED_METRICS)
        .reset_index(drop=True)
    )
    if plot_df.empty:
        raise SystemExit("Nao ha dados suficientes para gerar o grafico Pareto.")

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
        raise SystemExit("Nao ha dados validos para gerar o grafico Pareto.")

    return plot_df


def build_plot(plot_df: pd.DataFrame, output_path: Path) -> None:
    sns.set_theme(style="whitegrid")

    size_metric = plot_df["response_size_mean"]
    size_lower = float(size_metric.min())
    size_upper = float(size_metric.max())
    bubble_sizes = scale_bubble_sizes(
        size_metric,
        lower=size_lower,
        upper=size_upper,
    )
    configuration_colors = build_category_colors(plot_df)

    figure_height = max(8.0, 0.42 * len(plot_df) + 4.0)
    fig = plt.figure(figsize=(14, figure_height), layout="constrained")
    grid = fig.add_gridspec(1, 2, width_ratios=[4.9, 1.1])
    ax = fig.add_subplot(grid[0, 0])
    legend_ax = fig.add_subplot(grid[0, 1])
    legend_ax.axis("off")
    for idx, row in plot_df.iterrows():
        is_pareto = bool(row["pareto_frontier"])
        ax.scatter(
            row["resource_usage"],
            row["slo_breach_success_rate"],
            s=float(bubble_sizes.loc[idx]),
            marker="o",
            c=[configuration_colors.loc[idx]],
            alpha=0.8,
            edgecolors="#111111" if is_pareto else "#222222",
            linewidths=3.0 if is_pareto else 1.0,
            zorder=4 if is_pareto else 3,
        )

    ax.set_xlabel("Uso medio de recursos (pods x kube_pod_cpu_limits)")
    ax.set_ylabel("Requisicoes acima do SLO, apenas sucesso (%)")

    ax.set_xlim(0, padded_axis_upper(plot_df["resource_usage"], minimum=1.0))
    ax.set_ylim(0, padded_axis_upper(plot_df["slo_breach_success_rate"], minimum=0.1))

    legend_df = plot_df.copy()
    legend_df["color_category"] = legend_df["configuration"].map(configuration_category)
    legend_df["color_category_order"] = legend_df["color_category"].map(
        {category: idx for idx, category in enumerate(CATEGORY_ORDER)}
    )
    legend_df = legend_df.sort_values(
        ["color_category_order", "order", "configuration"],
    )
    configuration_handles = [
        Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            markerfacecolor=configuration_colors.loc[idx],
            markeredgecolor="#111111" if bool(row["pareto_frontier"]) else "#222222",
            markeredgewidth=3.0 if bool(row["pareto_frontier"]) else 1.0,
            markersize=8,
            label=row["label"],
        )
        for idx, row in legend_df.iterrows()
    ]
    configuration_legend = legend_ax.legend(
        handles=configuration_handles,
        title="Cenarios por categoria",
        loc="upper left",
        bbox_to_anchor=(0.0, 1.0),
        borderaxespad=0.0,
        markerscale=1.4,
        frameon=True,
    )
    legend_ax.add_artist(configuration_legend)

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
    size_legend = legend_ax.legend(
        handles=size_handles,
        title="Tamanho medio da resposta",
        loc="upper left",
        bbox_to_anchor=(0.0, 0.45),
        borderaxespad=0.0,
        frameon=True,
        labelspacing=1.0,
        handletextpad=1.6,
        handleheight=4.6,
    )
    legend_ax.add_artist(size_legend)

    legend_ax.legend(
        handles=[
            Line2D(
                [],
                [],
                marker="o",
                linestyle="",
                markerfacecolor="#999999",
                markeredgecolor="#111111",
                markeredgewidth=3.0,
                markersize=9,
                label="Fronteira Pareto",
            )
        ],
        title="Destaque",
        loc="upper left",
        bbox_to_anchor=(0.0, 0.08),
        borderaxespad=0.0,
        frameon=True,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300)


def main() -> None:
    args = build_parser().parse_args()
    output_path = Path(args.output)
    summary_path = Path(args.summary_csv)
    pareto_csv_path = Path(args.pareto_csv)

    summary_df = pd.read_csv(summary_path)
    plot_df = add_pareto_frontier(
        prepare_plot_data(summary_df),
        response_size_objective=args.response_size_objective,
    )
    build_plot(plot_df, output_path)

    pareto_csv_path.parent.mkdir(parents=True, exist_ok=True)
    plot_df[
        [
            "order",
            "configuration",
            "label",
            "resource_usage",
            "slo_breach_success_rate",
            "response_size_mean",
            "response_size_objective",
            "pareto_frontier",
        ]
    ].to_csv(pareto_csv_path, index=False)

    print(f"Grafico salvo em: {output_path}")
    print(f"Resumo lido de: {summary_path}")
    print(f"Resumo Pareto salvo em: {pareto_csv_path}")

    if args.show:
        plt.show()


if __name__ == "__main__":
    main()
