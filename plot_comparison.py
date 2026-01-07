import json
import os
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
from mpl_toolkits.mplot3d.axis3d import mpatches

from utils import format_size

if len(sys.argv) < 2:
    sys.stderr.write("Must inform config file")
    sys.exit(1)

arg_config_filename = sys.argv[1]
if not os.path.isfile(arg_config_filename):
    sys.stderr.write(f"{arg_config_filename} must exist")
    sys.exit(1)

try:
    data_source = json.load(open(arg_config_filename))
except json.JSONDecodeError:
    sys.stderr.write(f"{arg_config_filename} must be a valid JSON file")
    sys.exit(1)

files_root = "tests/results/"

all_dfs = []
for src in data_source:
    df = pd.read_csv(f"{files_root}{src['file']}")
    df["scaling"] = src["scaling"]
    df["order"] = src["order"]
    all_dfs.append(df)

full_df = pd.concat(all_dfs)

order_cols = ["order", "scaling"]

grouped = full_df[full_df["series"] == "znn_pods_per_tag"].groupby(order_cols)
pod_means = grouped["value"].mean().reset_index()


def align_to_pods(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        base = pod_means.copy()
        if "value" not in base.columns:
            base["value"] = 0
        base["value"] = 0
        return base[order_cols + ["value"]]
    return (
        df.set_index(order_cols)
        .reindex(pod_means.set_index(order_cols).index)
        .fillna(0)
        .reset_index()
    )


res_sizes = (
    full_df[full_df["series"] == "avg_response_size"]
    .groupby(order_cols)["value"]
    .mean()
    .reset_index()
)
res_sizes = align_to_pods(res_sizes)

res_duration = (
    full_df[full_df["series"] == "req_duration_avg_ms"]
    .groupby(order_cols)["value"]
    .mean()
    .reset_index()
)

grp_success = full_df[full_df["series"] == "response_time"].groupby(order_cols)
res_success = (
    grp_success["status_code"]
    .apply(lambda s: (s.astype(float).astype(int) == 200).mean() * 100)
    .reset_index(name="value")
)
res_success = align_to_pods(res_success)

slo_breach = (
    full_df[full_df["series"] == "slo_breach_pct"]
    .groupby(order_cols)["value"]
    .last()
    .reset_index()
)
slo_breach = align_to_pods(slo_breach)

slo_breach_200 = (
    full_df[full_df["series"] == "slo_breach_success_pct"]
    .groupby(order_cols)["value"]
    .last()
    .reset_index()
)
slo_breach_200 = align_to_pods(slo_breach_200)

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
ax1.set_ylim(0, 5)
ax1.set_title("Média de Pods")

rects2 = ax2.bar(indices, res_sizes["value"], color=colors)
ax2.bar_label(rects2, padding=3, fmt=format_size)
ax2.set_ylim(0, 1500_000)
ax2.set_title("Tamanho médio das respostas (Prometheus)")

rects3 = ax3.bar(indices, res_duration["value"], color=colors)
ax3.bar_label(rects3, padding=3)
ax3.set_ylim(0, 8000)
ax3.set_title("Tempo médio das respostas (ms)")

rects4 = ax4.bar(indices, res_success["value"], color=colors)
ax4.bar_label(rects4, padding=3, fmt="%.2f")
ax4.set_ylim(0, 120)
ax4.set_title("Respostas 200 (%)")

rects5 = ax5.bar(indices, slo_breach["value"], color=colors)
ax5.bar_label(rects5, padding=3, fmt="%.2f")
ax5.set_ylim(0, 100)
ax5.set_title("Requisições acima do SLO")

rects6 = ax6.bar(indices, slo_breach_200["value"], color=colors)
ax6.bar_label(rects6, padding=3, fmt="%.2f")
ax6.set_ylim(0, 100)
ax6.set_title("Requisições acima do SLO, apenas sucesso")

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
