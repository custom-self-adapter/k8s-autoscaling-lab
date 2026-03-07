import glob
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
from mpl_toolkits.mplot3d.axes3d import mcolors

from plot_helper import apply_standard_renames, filter_http_success, select_series
from utils import format_size

plt.style.use("bmh")
plt.rcParams.update(
    {
        "font.size": 10,
        "axes.titlesize": 14,
        "axes.labelsize": 11,
        "legend.fontsize": 9,
        "savefig.dpi": 300,
    }
)

ZNN_DUR_SERIES = "znn_latency_ms_p95"
ZNN_DUR_LABEL = "Duração das Requisições (ZNN)"
ZNN_PODS_SERIES = "znn_pods_per_tag"
ZNN_PODS_LABELS = "Pods por Tag (ZNN)"
LOC_RESP_TIME_SERIES = "loc_response_time"
LOC_RESP_TIME_LABEL = "Tempo de Resposta (LOC)"
LOC_RESP_SIZE_SERIES = "loc_response_size"
LOC_RESP_SIZE_LABEL = "Tamanho das Respostas (LOC)"
LOC_STATUS_CODE_SERIES = "loc_status_code"
LOC_USERS_SERIES = "loc_user_count"
LOC_USERS_LABEL = "Usuários Simultâneos"
KUBE_POD_CPU_SERIES = "kube_pod_cpu_limits"
KUBE_POD_CPU_LABEL = "Limite de CPU dos Contêineres"


RTM_SERIES = "response_time"
RTM_LABEL = "Tempo de Resposta (ms)"
ING_AVG_RESP_SIZE_SERIES = "ing_avg_response_size"
ING_AVG_RESP_SIZE_LABEL = "Tamanho da Resposta (ING)"
RESP_SIZE_SERIES_L = "response_size"
RESP_CODE_SERIES = "response_code"
RESP_CODE_LABEL = "Código de Resposta"
SLO_BREACH_SERIES = "slo_breach_pct"
SLO_BREACH_200_SERIES = "slo_breach_success_pct"

SLO_MILISECONDS = 1000

# ==============================
#  CORES (exclusivas por métrica + degradê para pods)
# ==============================
COLORS_METRICS = {
    "SLO": "#ff7f0e",
    ZNN_DUR_SERIES: "#2ca02c",
    LOC_RESP_TIME_SERIES: "#8cd0ac",
    LOC_USERS_SERIES: "#1f77b4",
    LOC_RESP_SIZE_SERIES: "#7f7f7f",
    "RESP_CODE": "#d62728",
}
# PODS_CMAP_NAME = "Dark2"
PODS_BASE_COLOR = "#ff8888"
PODS_RED_MAP = {100: 0.0, 200: 0.5, 400: 0.75, 800: 1}
PODS_RED_DENOM = 1000.0
PODS_RED_CLAMP = (0.10, 0.90)

BASE_RBG = mcolors.to_rgb(PODS_BASE_COLOR)
RESP_CODE_PALETTE = [
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]


def _to_ts_utc(ts_like):
    return pd.to_datetime(ts_like, utc=True, errors="coerce")


def to_rel_seconds(ts_like, ts_zero):
    ts = _to_ts_utc(ts_like)
    delta = ts - _to_ts_utc(ts_zero)
    if hasattr(delta, "dt"):
        return delta.dt.total_seconds().astype(float)
    if isinstance(delta, pd.TimedeltaIndex):
        return delta / np.timedelta64(1, "s")
    return float(delta.total_seconds())


def mmss_fmt(x, pos):
    x = max(0, float(x))
    m = int(x // 60)
    s = int(x % 60)
    return f"{m:02d}:{s:02d}"


def is_uniform(s):
    a = s.to_numpy()
    return (a[0] == a).all()


def build_status_pivot(df_response_code):
    if df_response_code.empty or "status_code" not in df_response_code.columns:
        return None, 0.0
    df_status = df_response_code.copy()
    df_status["status_code"] = df_status["status_code"].astype(str)
    pivot = df_status.pivot_table(
        index="ts", columns="status_code", values="value", aggfunc="sum"
    ).sort_index()
    try:
        max_count = float(np.nanmax(pivot.to_numpy())) if not pivot.empty else 0.0
    except (ValueError, TypeError):
        max_count = 0.0
    return pivot, max_count


def pods_color_from_tag(tag_str: str):
    try:
        v = int(str(tag_str).lstrip("0").rstrip("k") or "0")
    except Exception:
        v = None
    if v in PODS_RED_MAP:
        r = float(PODS_RED_MAP[v])
    elif isinstance(v, int) and v >= 0:
        r = np.clip(v / PODS_RED_DENOM, PODS_RED_CLAMP[0], PODS_RED_CLAMP[1])
    else:
        r = 0.5
    g, b = BASE_RBG[1], BASE_RBG[2]
    return (float(r), float(g), float(b))


def resp_code_color(idx: int):
    return RESP_CODE_PALETTE[idx % len(RESP_CODE_PALETTE)]


def main(file_input: str, file_output: Path | None):

    data = pd.read_csv(file_input)
    data = apply_standard_renames(data)

    df_resp_time_ing = select_series(data, ZNN_DUR_SERIES)
    df_resp_time_loc = select_series(
        data,
        LOC_RESP_TIME_SERIES,
        extra_cols=[LOC_RESP_SIZE_SERIES, LOC_STATUS_CODE_SERIES],
    )
    df_users = select_series(data, LOC_USERS_SERIES)
    df_cpu = select_series(data, KUBE_POD_CPU_SERIES)
    df_pods = data[data["series"] == ZNN_PODS_SERIES].copy()
    pivot_pods = (
        df_pods.groupby(["ts", "tag"])["value"].sum().unstack("tag").sort_index()
        if (not df_pods.empty and "tag" in df_pods.columns)
        else None
    )

    ts_min_values, ts_max_values = [], []
    for df_metric in (df_resp_time_ing, df_resp_time_loc, df_users):
        if not df_metric.empty:
            ts_min_values.append(df_metric["ts"].min())
            ts_max_values.append(df_metric["ts"].max())
    if pivot_pods is not None and not pivot_pods.empty:
        ts_min_values.append(pivot_pods.index.min())
        ts_max_values.append(pivot_pods.index.max())

    ts_zero = min(ts_min_values) if ts_min_values else pd.Timestamp.utcnow()

    # ==============================
    #  FIGURE: 2 PLOTS + LEGEND + TABLE
    # ==============================
    fig = plt.figure(figsize=(10, 7), layout="constrained")
    gs = fig.add_gridspec(nrows=4, ncols=1, height_ratios=[2, 2, 1, 1])

    ax_top = fig.add_subplot(gs[0])
    ax_mid = fig.add_subplot(gs[1], sharex=ax_top)
    ax_leg = fig.add_subplot(gs[2])
    ax_tbl = fig.add_subplot(gs[3])

    legend_lines = []
    legend_labels = []

    # ------------------------------
    #  Top: Response Time + Pods(tag)
    # ------------------------------
    ax_top.set_title("Latência e Pods por Tag")
    ax_top.tick_params(labelbottom=False)

    if not df_resp_time_loc.empty:
        (ln_dur,) = ax_top.plot(
            to_rel_seconds(df_resp_time_loc["ts"], ts_zero),
            df_resp_time_loc["value"],
            linewidth=1.0,
            color=COLORS_METRICS[LOC_RESP_TIME_SERIES],
        )
        legend_lines.append(ln_dur)
        legend_labels.append(LOC_RESP_TIME_LABEL)

    if not df_resp_time_ing.empty:
        (ln_resp_time_ing,) = ax_top.plot(
            to_rel_seconds(df_resp_time_ing["ts"], ts_zero),
            df_resp_time_ing["value"],
            linewidth=1.0,
            color=COLORS_METRICS[ZNN_DUR_SERIES],
        )
        legend_lines.append(ln_resp_time_ing)
        legend_labels.append(ZNN_DUR_LABEL)
    ax_top.set_ylim(0, 10000)
    ax_top.set_ylabel(ZNN_DUR_LABEL)

    ln_slo = ax_top.axhline(
        y=SLO_MILISECONDS,
        linestyle=":",
        linewidth=1.3,
        color=COLORS_METRICS["SLO"],
        label="SLO (1s)",
    )
    legend_lines.append(ln_slo)
    legend_labels.append(f"SLO ({SLO_MILISECONDS}ms)")
    
    # if not is_uniform(df_cpu["value"]):
    if True:
        # Only show CPU limits variation if there's variation to show
        ax_cpu = ax_top.twinx()
        # Move the third y-axis to the right so it does not overlap response size axis
        ax_cpu.spines["right"].set_position(("outward", 80))
        ax_cpu.patch.set_visible(False)
        ax_cpu.grid(False)
        (ln_cpu,) = ax_cpu.plot(
            to_rel_seconds(df_cpu["ts"], ts_zero),
            df_cpu["value"],
            label=KUBE_POD_CPU_LABEL,
            linewidth=1.0,
            color=COLORS_METRICS["SLO"],
        )
        legend_lines.append(ln_cpu)
        legend_labels.append(KUBE_POD_CPU_LABEL)
        ax_cpu.set_ylabel(KUBE_POD_CPU_LABEL)
        ax_cpu.set_ylim(0, 1.1)


    ax_pods = ax_top.twinx()
    ax_pods.patch.set_visible(False)
    ax_pods.grid(False)
    if pivot_pods is not None and not pivot_pods.empty:
        tags = sorted([str(c).zfill(4) for c in pivot_pods.columns])
        pivot_pods = pivot_pods.rename(columns=lambda c: str(c).zfill(4))
        for tag in tags:
            color = pods_color_from_tag(tag)
            (ln_tag,) = ax_pods.plot(
                to_rel_seconds(pivot_pods.index, ts_zero),
                pivot_pods[tag],
                linewidth=1.5,
                color=color,
                alpha=0.95,
            )
            # incluir cada tag na legenda
            legend_lines.append(ln_tag)
            legend_labels.append(f"Pods tag {tag}")
    ax_pods.set_ylabel(ZNN_PODS_LABELS)
    ax_pods.set_ylim(0.5, 5.5)
    
    ax_top.set_xlim(0, 300)

    # ------------------------------
    #  Mid: Users + Response size
    # ------------------------------
    ax_mid.set_title("Usuários e Tamanho das Respostas")

    if not df_users.empty:
        (ln_users,) = ax_mid.plot(
            to_rel_seconds(df_users["ts"], ts_zero),
            df_users["value"],
            label="Users",
            linewidth=1.5,
            color=COLORS_METRICS[LOC_USERS_SERIES],
        )
        legend_lines.append(ln_users)
        legend_labels.append(LOC_USERS_LABEL)
    ax_mid.set_ylabel(LOC_USERS_LABEL)

    ax_rsz = ax_mid.twinx()
    ax_rsz.grid(False)
    if not df_resp_time_loc[LOC_RESP_SIZE_SERIES].empty:
        (ln_rsz,) = ax_rsz.plot(
            to_rel_seconds(df_resp_time_loc["ts"], ts_zero),
            df_resp_time_loc[LOC_RESP_SIZE_SERIES],
            label=LOC_RESP_SIZE_LABEL,
            linewidth=1.0,
            color=COLORS_METRICS[LOC_RESP_SIZE_SERIES],
        )
        legend_lines.append(ln_rsz)
        legend_labels.append("Response size")

    ax_rsz.set_ylabel("Response size")
    ax_rsz.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, p: format_size(v)))
    ax_rsz.set_ylim(0, 1_100_000)
    
    # Eixo do tempo no subplot inferior
    ax_mid.set_xlabel("Tempo (mm:ss)")
    ax_mid.xaxis.set_major_formatter(mtick.FuncFormatter(mmss_fmt))
    ax_mid.set_xlim(0, 300)


    # ------------------------------
    #  LEGENDA
    # ------------------------------
    ax_leg.axis("off")
    # colunas com base no total de itens de legenda já conhecido
    _total_items = len(legend_lines)
    if _total_items <= 12:
        ncols = 4
    elif _total_items <= 25:
        ncols = 5
    else:
        ncols = 6
    ax_leg.legend(legend_lines, legend_labels, loc="center", ncols=ncols, frameon=True)

    # ------------------------------
    #  TABELA FINAL
    # ------------------------------
    ax_tbl.axis("off")

    count_reqs = df_resp_time_loc["value"].count()

    pct_success = (
        df_resp_time_loc.assign(
            success=df_resp_time_loc[LOC_STATUS_CODE_SERIES] == 200
        )["success"].mean()
        * 100
    )

    df_resp_time_success = filter_http_success(df_resp_time_loc, LOC_STATUS_CODE_SERIES)

    slo_breach = (
        df_resp_time_loc.assign(breach=df_resp_time_loc["value"] > SLO_MILISECONDS)[
            "breach"
        ].mean()
        * 100
    )
    slo_breach_200 = (
        df_resp_time_success.assign(
            breach=df_resp_time_success["value"] > SLO_MILISECONDS
        )["breach"].mean()
        * 100
    )
    pods_mean = df_pods["value"].mean()
    mean_rsz = df_resp_time_loc[LOC_RESP_SIZE_SERIES].mean()

    rows = [
        ("Número de requisições", f"{count_reqs}"),
        ("Requisições Sucesso (HTTP 200)", f"{pct_success:.2f}%"),
        ("% acima do SLO", f"{slo_breach:.2f}%"),
        ("% acima do SLO (sucesso)", f"{slo_breach_200:.2f}%"),
        ("Quantidade média de Pods", f"{pods_mean:.2f}"),
        ("Tamanho da Resposta (média)", format_size(mean_rsz)),
    ]

    cell_text = [[k, v] for k, v in rows]
    width = 0.6
    left = (1.0 - width) / 2.0
    bbox = [left, 0.06, width, 0.88]
    col_widths = [0.62, 0.38]

    tbl = ax_tbl.table(
        cellText=cell_text,
        cellLoc="left",
        colWidths=col_widths,
        bbox=bbox,
        edges="closed",
    )
    try:
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)
    except Exception:
        pass

    # Espaçamentos finos
    fig.set_constrained_layout_pads(w_pad=0.03, h_pad=0.03, hspace=0.03)

    if file_output is not None:
        file_output.parent.mkdir(parents=True, exist_ok=True)
        print(f"Salvando plot em {file_output}")
        fig.savefig(file_output)
        plt.close(fig)
    else:
        plt.show()


if __name__ == "__main__":
    arg_input = sys.argv[1] if len(sys.argv) > 1 else None
    arg_output = sys.argv[2] if len(sys.argv) > 2 else None
    if arg_input and Path(arg_input).is_file():
        file_input = arg_input
    else:
        candidates = glob.glob("tests/results/prom_extract*") or glob.glob(
            "prom_extract*.csv"
        )
        if not candidates:
            raise SystemExit(
                "Nenhum arquivo CSV encontrado. Passe o caminho como argumento."
            )
        file_input = max(candidates)
    print(f"Lendo dados de {file_input}")
    file_output = Path(arg_output) if arg_output else None

    main(file_input, file_output)
