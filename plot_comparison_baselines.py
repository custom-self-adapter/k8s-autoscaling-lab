import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mpl_toolkits.mplot3d.axis3d import mpatches

files_root = "tests/results/"
data_source = [
    {
        "scaling": "Baseline",
        "quality": "800k",
        "replicas": 1,
        "file": "prom_extract_202512201450.csv",
    },
    {
        "scaling": "Baseline",
        "quality": "800k",
        "replicas": 3,
        "file": "prom_extract_202512201456.csv",
    },
    {
        "scaling": "Baseline",
        "quality": "800k",
        "replicas": 5,
        "file": "prom_extract_202512201502.csv",
    },
    {
        "scaling": "Baseline",
        "quality": "400k",
        "replicas": 1,
        "file": "prom_extract_202512201508.csv",
    },
    {
        "scaling": "Baseline",
        "quality": "400k",
        "replicas": 3,
        "file": "prom_extract_202512201514.csv",
    },
    {
        "scaling": "Baseline",
        "quality": "400k",
        "replicas": 5,
        "file": "prom_extract_202512201521.csv",
    },
    {
        "scaling": "Baseline",
        "quality": "200k",
        "replicas": 1,
        "file": "prom_extract_202512201527.csv",
    },
    {
        "scaling": "Baseline",
        "quality": "200k",
        "replicas": 3,
        "file": "prom_extract_202512201533.csv",
    },
    {
        "scaling": "Baseline",
        "quality": "200k",
        "replicas": 5,
        "file": "prom_extract_202512201539.csv",
    },
]

all_dfs = []
for src in data_source:
    df = pd.read_csv(f"{files_root}{src['file']}")
    df["scaling"] = src["scaling"]
    df["quality"] = src["quality"]
    df["replicas"] = src["replicas"]
    all_dfs.append(df)

full_df = pd.concat(all_dfs)

plt.style.use("bmh")
cmap = mpl.colormaps[mpl.rcParams["image.cmap"]]

resp_times = full_df[full_df["series"] == "req_duration_avg_ms"].copy()
qualities = resp_times["quality"].unique()
replicas_values = np.sort(resp_times["replicas"].unique())

breach = (
    resp_times.groupby(["quality", "replicas"])["value"]
    .apply(lambda s: (s > 1000).mean() * 100)
    .reset_index()
)

breach_pivot = breach.pivot(
    index="quality", columns="replicas", values="value"
).reindex(index=qualities, columns=replicas_values)

fig, ax = plt.subplots()

x = np.arange(len(qualities))
n_rep = len(replicas_values)
width = 0.9 / n_rep

norm = mpl.colors.Normalize(vmin=replicas_values.min(), vmax=replicas_values.max())

for i, r in enumerate(replicas_values):
    offset = (i - (n_rep - 3) / 2) * width
    y = breach_pivot[r].to_numpy()
    color = cmap(norm(r))
    rects = ax.bar(x + offset, y, width, color=color)
    ax.bar_label(rects, padding=3, fmt="%.2f")

legend_handles = []
for r in replicas_values:
    color = cmap(norm(r))
    label = f"{r} replica" if r == 1 else f"{r} replicas"
    legend_handles.append(mpatches.Patch(facecolor=color, label=label))
ax.legend(loc="upper right", handles=legend_handles)

ax.set_xticks(x + width, qualities)
ax.set_ylim(0, 100)
ax.set_ylabel("Requisições acima do SLO (%)")

fig.suptitle("Linhas de Base em diferentes qualidades")

plt.show()
