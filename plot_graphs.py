import glob
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
from mpl_toolkits.mplot3d.axes3d import mcolors

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

# ==============================
#  ENTRADA DE DADOS
# ==============================
arg_file = sys.argv[1] if len(sys.argv) > 1 else None
arg_output = sys.argv[2] if len(sys.argv) > 2 else None
if arg_file and Path(arg_file).is_file():
    file_name = arg_file
else:
    candidates = glob.glob("tests/results/prom_extract*") or glob.glob(
        "prom_extract*.csv"
    )
    if not candidates:
        raise SystemExit(
            "Nenhum arquivo CSV encontrado. Passe o caminho como argumento."
        )
    file_name = max(candidates)
print(f"Lendo dados de {file_name}")
output_path = Path(arg_output) if arg_output else Path(file_name).with_suffix(".png")
output_path.parent.mkdir(parents=True, exist_ok=True)
print(f"Salvando plot em {output_path}")

data = pd.read_csv(file_name)

# series names
DUR_SERIES = "req_duration_avg_ms"
DUR_LABEL = "Duração das Requisições"
RTM_SERIES = "response_time"
RTM_LABEL = "Tempo de Resposta (ms)"
USERS_SERIES = "user_count"
USERS_LABEL = "Usuários Simultâneos"
PODS_SERIES = "znn_pods_per_tag"
PODS_LABELS = "Pods por Tag"
RESP_SIZE_SERIES = "avg_response_size"
RESP_SIZE_LABEL = "Tamanho da Resposta"
RESP_SIZE_SERIES_L = "response_size"
RESP_CODE_SERIES = "response_code"
RESP_CODE_LABEL = "Código de Resposta"
SLO_BREACH_SERIES = "slo_breach_pct"
SLO_BREACH_200_SERIES = "slo_breach_success_pct"

# ==============================
#  PARÂMETROS AJUSTÁVEIS
# ==============================
# Rolling mean window (number of samples) for response time smoothing.
RTM_ROLLING_WINDOW = 100
SLO_MILISECONDS = 1000

# ==============================
#  FUNÇÕES AUXILIARES
# ==============================


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


def select_series(df, series_name, extra_cols=None):
    cols = ["ts", "value"]
    if extra_cols:
        cols.extend([c for c in extra_cols if c in df.columns])
    subset = df[df["series"] == series_name]
    keep_cols = [c for c in cols if c in subset.columns]
    series_df = subset[keep_cols].copy()
    if "ts" in series_df.columns:
        series_df = series_df.sort_values("ts")
    return series_df


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


def filter_http_success(df):
    if df.empty or "status_code" not in df.columns:
        return df
    status = pd.to_numeric(df["status_code"], errors="coerce")
    return df[status == 200]


# ==============================
#  PRÉ-PROCESSAMENTO
# ==============================
df_duration = select_series(data, DUR_SERIES)
df_resp_time = select_series(data, RTM_SERIES, extra_cols=["status_code"])
df_users = select_series(data, USERS_SERIES)
df_resp_size = select_series(data, RESP_SIZE_SERIES)
df_pods = data[data["series"] == PODS_SERIES].copy()
pivot_pods = (
    df_pods.groupby(["ts", "tag"])["value"].sum().unstack("tag").sort_index()
    if (not df_pods.empty and "tag" in df_pods.columns)
    else None
)
pivot_resp_code, max_resp_code_count = build_status_pivot(df_resp_time)

df_slo_breach = select_series(data, SLO_BREACH_SERIES)
df_slo_breach_200 = select_series(data, SLO_BREACH_200_SERIES)

ts_min_values, ts_max_values = [], []
for df_metric in (df_duration, df_resp_time, df_users, df_resp_size):
    if not df_metric.empty:
        ts_min_values.append(df_metric["ts"].min())
        ts_max_values.append(df_metric["ts"].max())
if pivot_pods is not None and not pivot_pods.empty:
    ts_min_values.append(pivot_pods.index.min())
    ts_max_values.append(pivot_pods.index.max())

ts_zero = min(ts_min_values) if ts_min_values else pd.Timestamp.utcnow()

# ==============================
#  CORES (exclusivas por métrica + degradê para pods)
# ==============================
COLORS_METRICS = {
    "SLO": "#ff7f0e",
    "DURATION": "#2ca02c",
    "RESP_TIME": "#8cd0ac",
    "USERS": "#1f77b4",
    "RESP_SIZE": "#7f7f7f",
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


# ==============================
#  DIMENSIONAR ALTURA DA LEGENDA (todas as tags)
# ==============================
pods_count = 0
if pivot_pods is not None and not pivot_pods.empty:
    pods_count = pivot_pods.shape[1]
resp_code_lines = (
    pivot_resp_code.shape[1]
    if (pivot_resp_code is not None and not pivot_resp_code.empty)
    else int(not df_resp_time.empty)
)
base_leg_items = (
    1
    + int(not df_duration.empty)
    + int(not df_resp_time.empty)
    + int(not df_users.empty)
    + int(not df_resp_size.empty)
    + resp_code_lines
)  # SLO + métricas fixas
_estimated = base_leg_items + pods_count
if _estimated <= 12:
    ncols_guess = 4
elif _estimated <= 25:
    ncols_guess = 5
else:
    ncols_guess = 6
rows_guess = max(1, int(np.ceil(_estimated / ncols_guess)))
legend_height = 0.5 * rows_guess

# ==============================
#  FIGURA: 2 PLOTS (balanceados) + LEGENDA + TABELA
# ==============================
fig = plt.figure(figsize=(10, 7), layout="constrained")
gs = fig.add_gridspec(
    nrows=5, ncols=1, height_ratios=[2.8, 2.8, legend_height, 1.5, 0.5]
)

ax_top = fig.add_subplot(gs[0])
ax_mid = fig.add_subplot(gs[1], sharex=ax_top)
ax_leg = fig.add_subplot(gs[2])
ax_tbl = fig.add_subplot(gs[3])
ax_fname = fig.add_subplot(gs[4])
ax_fname.axis("off")
ax_fname.text(0.5, 0, file_name, ha="center")

legend_lines = []
legend_labels = []

# ------------------------------
#  Top: Latency + Pods(tag)
# ------------------------------
ax_top.set_title("Latência e Pods por Tag")
ax_top.tick_params(labelbottom=False)

if not df_resp_time.empty:
    (ln_rtm,) = ax_top.plot(
        to_rel_seconds(df_resp_time["ts"], ts_zero),
        df_resp_time["value"],
        linewidth=1.0,
        color=COLORS_METRICS["RESP_TIME"],
    )
    legend_lines.append(ln_rtm)
    legend_labels.append(RTM_LABEL)
ax_top.set_ylim(0, 8000)
ax_top.set_ylabel(RTM_LABEL)

if not df_duration.empty:
    (ln_dur,) = ax_top.plot(
        to_rel_seconds(df_duration["ts"], ts_zero),
        df_duration["value"],
        linewidth=1.5,
        color=COLORS_METRICS["DURATION"],
    )
    legend_lines.append(ln_dur)
    legend_labels.append(DUR_LABEL)

ln_slo = ax_top.axhline(
    y=SLO_MILISECONDS,
    linestyle=":",
    linewidth=1.3,
    color=COLORS_METRICS["SLO"],
    label="SLO (1s)",
)
legend_lines.append(ln_slo)
legend_labels.append("SLO (1.5s)")

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
ax_pods.set_ylabel(PODS_LABELS)
ax_pods.set_ylim(0.5, 5.5)

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
        color=COLORS_METRICS["USERS"],
    )
    legend_lines.append(ln_users)
    legend_labels.append(USERS_LABEL)
ax_mid.set_ylabel(USERS_LABEL)

ax_rsz = ax_mid.twinx()
ax_rsz.grid(False)
if not df_resp_size.empty:
    (ln_rsz,) = ax_rsz.plot(
        to_rel_seconds(df_resp_size["ts"], ts_zero),
        df_resp_size["value"],
        label=RESP_SIZE_LABEL,
        linewidth=1.0,
        color=COLORS_METRICS["RESP_SIZE"],
    )
    legend_lines.append(ln_rsz)
    legend_labels.append("Response size")
ax_rsz.set_ylabel("Response size")
ax_rsz.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, p: format_size(v)))
ax_rsz.set_ylim(0, 1_100_000)

# Eixo do tempo no subplot inferior
ax_mid.set_xlabel("Tempo (mm:ss)")
ax_mid.xaxis.set_major_formatter(mtick.FuncFormatter(mmss_fmt))

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

df_resp_time_success = filter_http_success(df_resp_time)
print(df_resp_time[df_resp_time["value"] > SLO_MILISECONDS])

print(
    df_duration[df_duration["value"] > SLO_MILISECONDS]["value"].count()
    / df_duration["value"].count()
)
print(
    df_resp_time[df_resp_time["value"] > SLO_MILISECONDS]["value"].count()
    / df_resp_time["value"].count()
)
print(
    df_resp_time_success[df_resp_time_success["value"] > SLO_MILISECONDS][
        "value"
    ].count()
    / df_resp_time_success["value"].count()
)

breach_pct = df_slo_breach["value"].iloc[-1]
breach_pct_200 = df_slo_breach_200["value"].iloc[-1]
pods_mean = df_pods["value"].mean() if not df_pods.empty else np.nan
mean_rsz = df_resp_size["value"].mean() if not df_resp_size.empty else np.nan
rows = [
    ("% acima do SLO", f"{breach_pct:.2f}%"),
    ("% acima do SLO (sucesso)", f"{breach_pct_200:.2f}%"),
    (
        "Quantidade média de Pods",
        f"{pods_mean:.2f}" if np.isfinite(pods_mean) else "—",
    ),
    (
        "Tamanho da Resposta (média)",
        format_size(mean_rsz) if np.isfinite(mean_rsz) else "—",
    ),
]

status_code_counts = (
    df_resp_time.groupby("status_code")["value"].count()
    if ("status_code" in df_resp_time.columns and not df_resp_time.empty)
    else pd.Series(dtype=int)
)
for status_code, count in status_code_counts.items():
    if status_code == 0:
        continue
    rows.append((f"Total HTTP {int(status_code)}", f"{count}"))

cell_text = [[k, v] for k, v in rows]
width = 0.6
left = (1.0 - width) / 2.0
bbox = [left, 0.06, width, 0.88]
col_widths = [0.62, 0.38]

tbl = ax_tbl.table(
    cellText=cell_text, cellLoc="left", colWidths=col_widths, bbox=bbox, edges="closed"
)
try:
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
except Exception:
    pass

# Espaçamentos finos
fig.set_constrained_layout_pads(w_pad=0.03, h_pad=0.03, hspace=0.03)

if __name__ == "__main__":
    fig.savefig(output_path)
    plt.close(fig)
