import glob
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from mpl_toolkits.mplot3d.axes3d import mcolors
import numpy as np
import pandas as pd

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

data = pd.read_csv(file_name)

# series names
DUR_SERIES = "req_duration_avg_ms"
DUR_LABEL = "Duração das Requisições (ms)"
USERS_SERIES = "user_count"
USERS_LABEL = "Usuários Simultâneos"
PODS_SERIES = "znn_pods_per_tag"
PODS_LABELS = "Pods por Tag"
RESP_SIZE_SERIES = "avg_response_size"
RESP_SIZE_LABEL = "Tamanho da Resposta"

# ==============================
#  FUNÇÕES AUXILIARES
# ==============================


def _to_ts_utc(ts_like):
    return pd.to_datetime(ts_like, utc=True, errors="coerce")


def to_rel_seconds(ts_like, t0):
    ts = _to_ts_utc(ts_like)
    delta = ts - _to_ts_utc(t0)
    if hasattr(delta, "dt"):
        return delta.dt.total_seconds().astype(float)
    if isinstance(delta, pd.TimedeltaIndex):
        return delta / np.timedelta64(1, "s")
    return float(delta.total_seconds())


def format_size(v):
    try:
        v = float(v)
    except Exception:
        return "—"
    if not np.isfinite(v):
        return "—"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while v >= 1024 and i < len(units) - 1:
        v /= 1024.0
        i += 1
    return f"{v:.2f} {units[i]}" if i else f"{int(v)} {units[i]}"


def mmss_fmt(x, pos):
    x = max(0, float(x))
    m = int(x // 60)
    s = int(x % 60)
    return f"{m:02d}:{s:02d}"


# ==============================
#  PRÉ-PROCESSAMENTO
# ==============================
_df_dur = data[data["series"] == DUR_SERIES][["ts", "value"]].copy()
_df_req = data[data["series"] == USERS_SERIES][["ts", "value"]].copy()
_df_rsz = data[data["series"] == RESP_SIZE_SERIES][["ts", "value"]].copy()
_df_pods = data[data["series"] == PODS_SERIES].copy()
_pods_pivot = (
    _df_pods.groupby(["ts", "tag"])["value"].sum().unstack("tag").sort_index()
    if (not _df_pods.empty and "tag" in _df_pods.columns)
    else None
)

_ts_min, _ts_max = [], []
for d in (_df_dur, _df_req, _df_rsz):
    if not d.empty:
        _ts_min.append(d["ts"].min())
        _ts_max.append(d["ts"].max())
if _pods_pivot is not None and not _pods_pivot.empty:
    _ts_min.append(_pods_pivot.index.min())
    _ts_max.append(_pods_pivot.index.max())

t0 = min(_ts_min) if _ts_min else pd.Timestamp.utcnow()

# ==============================
#  CORES (exclusivas por métrica + degradê para pods)
# ==============================
COLORS_METRICS = {
    "SLO": "#ff7f0e",
    "DURATION": "#2ca02c",
    "USERS": "#1f77b4",
    "RESP_SIZE": "#7f7f7f",
}
# PODS_CMAP_NAME = "Dark2"
PODS_BASE_COLOR = "#ff8888"
PODS_RED_MAP = {100: 0.0, 200: 0.5, 400: 0.75, 800: 1}
PODS_RED_DENOM = 1000.0
PODS_RED_CLAMP = (0.10, 0.90)

BASE_RBG = mcolors.to_rgb(PODS_BASE_COLOR)

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

# ==============================
#  DIMENSIONAR ALTURA DA LEGENDA (todas as tags)
# ==============================
pods_count = 0
if _pods_pivot is not None and not _pods_pivot.empty:
    pods_count = _pods_pivot.shape[1]
base_leg_items = (
    1 + int(not _df_dur.empty) + int(not _df_req.empty) + int(not _df_rsz.empty)
)  # SLO + 3 métricas
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
fig = plt.figure(figsize=(10, 7), constrained_layout=True)
gs = fig.add_gridspec(nrows=4, ncols=1, height_ratios=[2.8, 2.8, legend_height, 1.5])

ax_top = fig.add_subplot(gs[0])
ax_mid = fig.add_subplot(gs[1], sharex=ax_top)
ax_leg = fig.add_subplot(gs[2])
ax_tbl = fig.add_subplot(gs[3])

legend_lines = []
legend_labels = []

# ------------------------------
#  Top: Latency + Pods(tag)
# ------------------------------
ax_top.set_title("Latência e Pods por Tag")
ax_top.tick_params(labelbottom=False)

ln_slo = ax_top.axhline(
    y=1000, linestyle=":", linewidth=1.3, color=COLORS_METRICS["SLO"], label="SLO (1s)"
)
legend_lines.append(ln_slo)
legend_labels.append("SLO (1s)")

if not _df_dur.empty:
    (ln_dur,) = ax_top.plot(
        to_rel_seconds(_df_dur["ts"], t0),
        _df_dur["value"],
        linewidth=1.5,
        color=COLORS_METRICS["DURATION"],
    )
    legend_lines.append(ln_dur)
    legend_labels.append(DUR_LABEL)
ax_top.set_ylabel(DUR_LABEL)
ax_top.set_ylim(0, 5000)

ax_pods = ax_top.twinx()
ax_pods.grid(False)
if _pods_pivot is not None and not _pods_pivot.empty:
    tags = sorted([str(c).zfill(4) for c in _pods_pivot.columns])
    _pods_pivot = _pods_pivot.rename(columns=lambda c: str(c).zfill(4))
    for tag in tags:
        color = pods_color_from_tag(tag)
        (ln_tag,) = ax_pods.plot(
            to_rel_seconds(_pods_pivot.index, t0),
            _pods_pivot[tag],
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

if not _df_req.empty:
    (ln_users,) = ax_mid.plot(
        to_rel_seconds(_df_req["ts"], t0),
        _df_req["value"],
        label="Users",
        linewidth=1.5,
        color=COLORS_METRICS["USERS"],
    )
    legend_lines.append(ln_users)
    legend_labels.append(USERS_LABEL)
ax_mid.set_ylabel(USERS_LABEL)

ax_rsz = ax_mid.twinx()
ax_rsz.grid(False)
if not _df_rsz.empty:
    (ln_rsz,) = ax_rsz.plot(
        to_rel_seconds(_df_rsz["ts"], t0),
        _df_rsz["value"],
        label="Response size",
        linewidth=1.5,
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

breach_pct = (_df_dur["value"] > 1000).mean() * 100 if not _df_dur.empty else 0.0
pods_mean = _df_pods["value"].mean() if not _df_pods.empty else np.nan
mean_rsz = _df_rsz["value"].mean() if not _df_rsz.empty else np.nan
rows = [
    (
        "Latência média (ms)",
        f"{_df_dur['value'].mean():.2f}" if not _df_dur.empty else "—",
    ),
    ("% acima do SLO (1s)", f"{breach_pct:.2f}%"),
    ("Quantidade média de Pods", f"{pods_mean:.2f}" if np.isfinite(pods_mean) else "—"),
    (
        "Tamanho da Resposta (média)",
        format_size(mean_rsz) if np.isfinite(mean_rsz) else "—",
    ),
]

cell_text = [[k, v] for k, v in rows]
width = 0.56
left = (1.0 - width) / 2.0
bbox = [left, 0.06, width, 0.88]
col_widths = [0.62, 0.38]

tbl = ax_tbl.table(
    cellText=cell_text, cellLoc="left", colWidths=col_widths, bbox=bbox, edges="closed"
)
try:
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
except Exception:
    pass

# Espaçamentos finos
fig.set_constrained_layout_pads(w_pad=0.04, h_pad=0.03, hspace=0.03)

if __name__ == "__main__":
    plt.show()
