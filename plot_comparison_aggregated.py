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
    r"(?P<timestamp>\d{14})_(?P<order>\d+)_(?P<scenario>.+)\.csv$"
)

SCENARIO_LABELS = {
    "base_1": "1 Replica",
    "base_5": "5 Replicas",
    "base_100": "1 Replica 1 CPU",
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
    MetricSpec("pods_mean", "Media de Pods (ZNN)"),
    MetricSpec("cpu_limits_mean", "Media de kube_pod_cpu_limits"),
    MetricSpec("response_time_mean", "Tempo medio das respostas (ms) (LOC)"),
    MetricSpec("response_size_mean", "Tamanho medio das respostas (LOC)"),
    MetricSpec("success_rate", "Respostas 200 (%) (LOC)", percent_axis=True),
    MetricSpec(
        "slo_breach_success_rate",
        "Requisicoes acima do SLO, apenas sucesso (%) (LOC)",
        percent_axis=True,
    ),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Gera graficos agregados das metricas de comparacao a partir de "
            "todos os CSVs nomeados como <timestamp>_<sequencial>_<cenario>.csv."
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
                "timestamp": match.group("timestamp"),
                "order": int(match.group("order")),
                "scenario": match.group("scenario"),
                "label": scenario_label(match.group("scenario")),
            }
        )
    if not rows:
        raise SystemExit(
            f"Nenhum CSV no padrao <timestamp>_<sequencial>_<cenario>.csv foi encontrado em {results_dir}"
        )
    return pd.DataFrame(rows).sort_values(["order", "timestamp", "scenario"])


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
        "timestamp": file_info["timestamp"],
        "order": int(file_info["order"]),
        "scenario": file_info["scenario"],
        "label": file_info["label"],
        "file": str(file_info["file"]),
        "pods_mean": safe_numeric_mean(pods["value"]),
        "cpu_limits_mean": safe_numeric_mean(cpu_limits.get("value")),
        "response_size_mean": safe_numeric_mean(resp_time.get(LOC_RESP_SIZE_COL)),
        "response_time_mean": safe_numeric_mean(resp_time.get("value")),
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


def build_plot(
    summary_df: pd.DataFrame, run_df: pd.DataFrame, output_path: Path
) -> None:
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

    scenarios = (
        run_df.groupby(["order", "scenario", "label"], as_index=False)
        .size()
        .rename(columns={"size": "run_count"})
        .sort_values(["order", "scenario"])
        .reset_index(drop=True)
    )
    scenario_labels = [f"{row.label}" for row in scenarios.itertuples(index=False)]
    positions = np.arange(len(scenarios))
    cmap = plt.get_cmap("tab10")
    colors = [cmap(i % cmap.N) for i in positions]

    fig, axes = plt.subplots(3, 2, figsize=(11, 16), sharex=True, layout="constrained")
    axes = axes.flatten()

    for idx, metric in enumerate(METRICS):
        ax = axes[idx]
        metric_values = []
        plot_positions = []
        for pos, scenario_row in enumerate(scenarios.itertuples(index=False)):
            values = pd.to_numeric(
                run_df.loc[
                    (run_df["order"] == scenario_row.order)
                    & (run_df["scenario"] == scenario_row.scenario),
                    metric.key,
                ],
                errors="coerce",
            ).dropna()
            if values.empty:
                continue
            metric_values.append(values.to_numpy(dtype=float))
            plot_positions.append(pos)

        if metric_values:
            boxplot = ax.boxplot(
                metric_values,
                positions=plot_positions,
                widths=0.6,
                whis=(0, 100),
                showmeans=True,
                meanprops={
                    "marker": "o",
                    "markerfacecolor": "white",
                    "markeredgecolor": "black",
                    "markersize": 6,
                },
                medianprops={"color": "black", "linewidth": 1.5},
                whiskerprops={"color": "#444444", "linewidth": 1.2},
                capprops={"color": "#444444", "linewidth": 1.2},
                flierprops={
                    "marker": "x",
                    "markeredgecolor": "#666666",
                    "markersize": 5,
                },
                patch_artist=True,
            )
            for patch, pos in zip(boxplot["boxes"], plot_positions):
                patch.set_facecolor(colors[pos])
                patch.set_alpha(0.75)
                patch.set_edgecolor("#333333")
                patch.set_linewidth(1.0)

        metric_summary = summary_df[summary_df["metric"] == metric.key]
        maxs = metric_summary["max"].to_numpy(dtype=float)
        valid_maxs = maxs[np.isfinite(maxs)]
        if valid_maxs.size:
            highest = float(valid_maxs.max())
        else:
            highest = 0.0

        if metric.percent_axis:
            ax.set_ylim(0, 105)
        else:
            ax.set_ylim(0, max(1.0, highest * 1.15))

        ax.set_title(metric.title)
        ax.set_xticks(positions, scenario_labels)
        ax.tick_params(axis="x", rotation=45)
        for tick_label in ax.get_xticklabels():
            tick_label.set_ha("right")
            tick_label.set_rotation_mode("anchor")
        ax.grid(axis="y", linestyle="--", alpha=0.45)

        if not metric_values:
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

    fig.suptitle(
        "Comparacao agregada entre cenarios de teste\n"
        "Box = Q1-Q3, linha = mediana, circulo = media, whiskers = minimo/maximo"
    )

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
            color="#444444",
            linewidth=1.2,
            marker="_",
            markersize=10,
            label="Min/Max",
        ),
        Line2D(
            [0],
            [0],
            color="black",
            marker="o",
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
    run_df = pd.DataFrame(run_rows).sort_values(["order", "timestamp", "scenario"])
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
