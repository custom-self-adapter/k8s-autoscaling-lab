import argparse
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
    "base_1": "1 Replica",
    "base_5": "5 Replicas",
    "base_1000": "1 Replica 1 CPU",
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
    MetricSpec("pods_mean", "Media de Pods (número de réplicas)"),
    MetricSpec("cpu_limits_mean", "Média do limite de CPU (fração de CPU)"),
    MetricSpec("response_time_mean", "Tempo medio das respostas (ms)"),
    MetricSpec("response_size_mean", "Tamanho medio das respostas (MB)"),
    MetricSpec("success_rate", "Respostas 200 (%)", percent_axis=True),
    MetricSpec(
        "slo_breach_success_rate",
        "Requisicoes acima do SLO, apenas sucesso (%)",
        percent_axis=True,
    ),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Gera graficos agregados das metricas de comparacao a partir de "
            "todos os CSVs nomeados como <run>_<sequencial>_<cenario>.csv."
        )
    )
    parser.add_argument(
        "--results-dir",
        default="tests/results",
        help="Diretorio com os CSVs de resultados.",
    )
    parser.add_argument(
        "--output",
        default="tests/results/compare_aggregated.png",
        help="Arquivo PNG de saida.",
    )
    parser.add_argument(
        "--summary-csv",
        default="tests/results/compare_aggregated_summary.csv",
        help="Arquivo CSV com os agregados por cenario e metrica.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Abre a figura interativamente alem de salvar o arquivo.",
    )
    return parser


def prepare_plot_data(run_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    scenarios = (
        run_df.groupby(["order", "scenario", "label"], as_index=False)
        .size()
        .rename(columns={"size": "run_count"})
        .sort_values(["order", "scenario"])
        .reset_index(drop=True)
    )
    scenario_order = scenarios["scenario"].tolist()
    label_map = scenarios.set_index("scenario")["label"].to_dict()

    plot_df = run_df.melt(
        id_vars=["run", "order", "scenario", "label"],
        value_vars=[metric.key for metric in METRICS],
        var_name="metric",
        value_name="value",
    )
    plot_df["value"] = pd.to_numeric(plot_df["value"], errors="coerce")
    plot_df = plot_df.dropna(subset=["value"]).copy()
    plot_df["scenario"] = pd.Categorical(
        plot_df["scenario"], categories=scenario_order, ordered=True
    )
    plot_df["label"] = plot_df["scenario"].map(label_map)
    return scenarios, plot_df


def metric_upper_bound(metric_summary: pd.DataFrame, percent_axis: bool) -> float:
    if percent_axis:
        return 105.0
    maxs = pd.to_numeric(metric_summary["max"], errors="coerce").to_numpy(dtype=float)
    valid_maxs = maxs[np.isfinite(maxs)]
    if not valid_maxs.size:
        return 1.0
    return max(1.0, float(valid_maxs.max()) * 1.15)


def build_plot(
    summary_df: pd.DataFrame, run_df: pd.DataFrame, output_path: Path
) -> None:
    sns.set_theme(
        style="whitegrid",
        context="notebook",
        rc={
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "savefig.dpi": 300,
        },
    )

    scenarios, plot_df = prepare_plot_data(run_df)
    scenario_order = scenarios["scenario"].tolist()
    scenario_labels = scenarios["label"].tolist()
    palette_colors = sns.color_palette("Set2", n_colors=len(scenarios))
    scenario_palette = {
        scenario: palette_colors[idx] for idx, scenario in enumerate(scenario_order)
    }
    mean_df = (
        plot_df.groupby(["metric", "scenario"], as_index=False, observed=False)[
            "value"
        ].mean()
        if not plot_df.empty
        else pd.DataFrame(columns=["metric", "scenario", "value"])
    )
    mean_df["scenario"] = pd.Categorical(
        mean_df["scenario"], categories=scenario_order, ordered=True
    )

    fig, axes = plt.subplots(3, 2, figsize=(11, 16), sharex=True, layout="constrained")
    axes = axes.flatten()

    for idx, metric in enumerate(METRICS):
        ax = axes[idx]
        metric_df = plot_df[plot_df["metric"] == metric.key]
        metric_means = mean_df[mean_df["metric"] == metric.key]

        if not metric_df.empty:
            sns.boxplot(
                data=metric_df,
                x="scenario",
                y="value",
                order=scenario_order,
                hue="scenario",
                hue_order=scenario_order,
                palette=scenario_palette,
                dodge=False,
                width=0.62,
                whis=(0, 100),
                saturation=0.85,
                linewidth=1.1,
                fliersize=3,
                medianprops={"color": "#1f1f1f", "linewidth": 1.6},
                whiskerprops={"color": "#555555", "linewidth": 1.1},
                capprops={"color": "#555555", "linewidth": 1.1},
                boxprops={"edgecolor": "#333333"},
                ax=ax,
            )
            sns.stripplot(
                data=metric_df,
                x="scenario",
                y="value",
                order=scenario_order,
                color="#2f2f2f",
                size=3.2,
                jitter=0.18,
                alpha=0.45,
                ax=ax,
            )
            sns.scatterplot(
                data=metric_means,
                x="scenario",
                y="value",
                marker="D",
                s=42,
                color="white",
                edgecolor="#111111",
                linewidth=0.9,
                zorder=5,
                legend=False,
                ax=ax,
            )

        metric_summary = summary_df[summary_df["metric"] == metric.key]
        ax.set_ylim(0, metric_upper_bound(metric_summary, metric.percent_axis))

        ax.set_title(metric.title)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_xticks(range(len(scenario_order)), scenario_labels)
        ax.tick_params(axis="x", rotation=40)
        for tick_label in ax.get_xticklabels():
            tick_label.set_ha("right")
            tick_label.set_rotation_mode("anchor")
        ax.grid(axis="y", linestyle="--", alpha=0.35)
        ax.grid(axis="x", visible=False)

        legend = ax.get_legend()
        if legend is not None:
            legend.remove()

        if metric_df.empty:
            ax.text(
                0.5,
                0.5,
                "Sem dados",
                transform=ax.transAxes,
                ha="center",
                va="center",
                fontsize=11,
                color="#666666",
                bbox={
                    "boxstyle": "round,pad=0.3",
                    "facecolor": "white",
                    "edgecolor": "#cccccc",
                },
            )

    fig.suptitle("Box = Q1-Q3, linha = mediana, pontos = execucoes, losango = media")

    stat_legend = [
        Line2D(
            [0],
            [0],
            color="black",
            linewidth=1.5,
            label="Mediana",
        ),
        Line2D(
            [0],
            [0],
            color="#2f2f2f",
            marker="o",
            markerfacecolor="#2f2f2f",
            linewidth=0,
            markersize=5,
            alpha=0.45,
            label="Execucoes",
        ),
        Line2D(
            [0],
            [0],
            color="#111111",
            marker="D",
            markerfacecolor="white",
            linewidth=0,
            markersize=6,
            label="Media",
        ),
    ]
    fig.legend(
        handles=stat_legend, loc="lower center", ncols=3, bbox_to_anchor=(0.5, -0.01)
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")


def main() -> None:
    args = build_parser().parse_args()
    results_dir = Path(args.results_dir)
    output_path = Path(args.output)
    summary_path = Path(args.summary_csv)

    discovered = discover_result_files(results_dir, SCENARIO_LABELS)
    run_rows = [compute_run_metrics(row) for _, row in discovered.iterrows()]
    run_df = pd.DataFrame(run_rows).sort_values(["order", "run", "scenario"])
    summary_df = summarize_runs(run_df, METRICS, sort_columns=("metric", "order"))

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
