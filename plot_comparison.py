import math
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.axis3d import mpatches

from plot_helper import (
    apply_standard_renames,
    filter_http_success,
    load_config_file,
    read_results,
    select_series,
)
from utils import format_size

PODS_SERIES = "znn_pods_per_tag"
RESP_SIZE_SERIES = "ing_avg_response_size"
RESP_TIME_SERIES = "loc_response_time"
STATUS_CODE_COL = "loc_status_code"
LOC_RESP_SIZE_COL = "loc_response_size"
SLO_BREACH_SERIES = "znn_slo_breach_pct"
SLO_BREACH_SUCCESS_SERIES = "znn_slo_breach_success_pct"
REQ_DURATION_SERIES = "znn_req_duration_avg_ms"

SLO_MILISECONDS = 1000

if len(sys.argv) < 2:
    sys.stderr.write("Must inform config file")
    sys.exit(1)

arg_config_filename = sys.argv[1]
data_source = load_config_file(arg_config_filename)

files_root = "tests/results/"

full_df = read_results(data_source, files_root, ["scaling", "order"])
full_df = apply_standard_renames(full_df)

order_cols = ["order", "scaling"]

grouped = full_df[full_df["series"] == PODS_SERIES].groupby(order_cols)
pod_means = grouped["value"].mean().reset_index()

res_sizes = (
    full_df[full_df["series"] == RESP_TIME_SERIES]
    .groupby(order_cols)[LOC_RESP_SIZE_COL]
    .mean()
    .reset_index()
    .rename(columns={LOC_RESP_SIZE_COL: "value"})
)

resp_time = select_series(full_df, RESP_TIME_SERIES, order_cols + [STATUS_CODE_COL])
resp_time_mean = resp_time.groupby(order_cols)["value"].mean().reset_index()

pct_success = (
    resp_time.assign(success=resp_time[STATUS_CODE_COL] == 200)
    .groupby(order_cols)["success"]
    .mean()
    .mul(100)
    .reset_index()
    .rename(columns={"success": "value"})
)

resp_time_success = filter_http_success(resp_time, STATUS_CODE_COL)

slo_breach = (
    resp_time.assign(breach=resp_time["value"] > SLO_MILISECONDS)
    .groupby(order_cols)["breach"]
    .mean()
    .mul(100)
    .reset_index()
    .rename(columns={"breach": "value"})
)

slo_breach_200 = (
    resp_time_success.assign(breach=resp_time_success["value"] > SLO_MILISECONDS)
    .groupby(order_cols)["breach"]
    .mean()
    .mul(100)
    .reset_index()
    .rename(columns={"breach": "value"})
)

plt.style.use("bmh")
cmap = mpl.colormaps[mpl.rcParams["image.cmap"]]
fig = plt.figure(figsize=(12, 6), layout="constrained")
gs = fig.add_gridspec(nrows=4, ncols=2, height_ratios=[2, 2, 2, 1])
ax1 = fig.add_subplot(gs[0, 0])
ax2 = fig.add_subplot(gs[0, 1])
ax3 = fig.add_subplot(gs[1, 0])
ax4 = fig.add_subplot(gs[1, 1])
ax5 = fig.add_subplot(gs[2, 0])
ax6 = fig.add_subplot(gs[2, 1])
ax_legend = fig.add_subplot(gs[3, :])

n = len(pod_means)
indices = list(range(n))
colors = [cmap(i / max(1, n - 1)) for i in indices]

rects1 = ax1.bar(indices, pod_means["value"], color=colors)
ax1.bar_label(rects1, padding=3, fmt="%.2f")
ax1.set_ylim(0, math.ceil(pod_means["value"].max() * 1.2))
ax1.set_title("Média de Pods (ZNN)")

rects2 = ax2.bar(indices, res_sizes["value"], color=colors)
ax2.bar_label(rects2, padding=3, fmt=format_size)
ax2.set_ylim(0, math.ceil(res_sizes["value"].max() * 1.2))
ax2.set_title("Tamanho médio das respostas (LOC)")

rects3 = ax3.bar(indices, resp_time_mean["value"], color=colors)
ax3.bar_label(rects3, padding=3, fmt="%.2f")
ax3.set_ylim(0, math.ceil(resp_time_mean["value"].max() * 1.2))
ax3.set_title("Tempo médio das respostas (ms) (LOC)")

rects4 = ax4.bar(indices, pct_success["value"], color=colors)
ax4.bar_label(rects4, padding=3, fmt="%.2f")
ax4.set_ylim(0, 120)
ax4.set_title("Respostas 200 (%) (LOC)")

rects5 = ax5.bar(indices, slo_breach["value"], color=colors)
ax5.bar_label(rects5, padding=3, fmt="%.2f")
ax5.set_ylim(0, 120)
ax5.set_title("Requisições acima do SLO (%) (LOC)")

rects6 = ax6.bar(indices, slo_breach_200["value"], color=colors)
ax6.bar_label(rects6, padding=3, fmt="%.2f")
ax6.set_ylim(0, 120)
ax6.set_title("Requisições acima do SLO, apenas sucesso (%) (LOC)")

legend_handles = [
    mpatches.Patch(
        label=f"{pod_means['order'][i]} - {pod_means['scaling'][i]}",
        facecolor=colors[i],
    )
    for i in pod_means.index
]
ax_legend.axis("off")
ax_legend.legend(handles=legend_handles, loc="lower center", ncols=3)

for ax in (ax1, ax2, ax3, ax4):
    ax.set_xticks(indices)

fig.suptitle("Comparação entre Cenários de Teste")
# plt.tight_layout()
plt.show()
