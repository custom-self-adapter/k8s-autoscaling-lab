import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.lines import Line2D

from plot_helper import apply_standard_renames, filter_http_success, select_series

PODS_SERIES = "znn_pods_per_tag"
CPU_LIMITS_SERIES = "kube_pod_cpu_limits"
RESP_TIME_SERIES = "loc_response_time"
STATUS_CODE_COL = "loc_status_code"
LOC_RESP_SIZE_COL = "loc_response_size"
SLO_MILLISECONDS = 1000

FILE_PATTERN = re.compile(r"(?P<run>\d{2})_(?P<order>\d+)_(?P<scenario>.+)\.csv$")

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


@dataclass(frozen=True)
class MetricSpec:
    key: str
    title: str
    percent_axis: bool = False


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
        "response_size_mean": safe_numeric_mean(
            resp_time_success.get(LOC_RESP_SIZE_COL)
        ),
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
            # if scenario == "base_1000" and metric.key == "cpu_limits_mean":
            #     print(values)
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
    return pd.DataFrame(summary_rows).sort_values(["metric", "order"])


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
