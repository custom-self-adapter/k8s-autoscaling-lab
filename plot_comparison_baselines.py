import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mpl_toolkits.mplot3d.axis3d import mpatches

root_dir = Path(__file__).resolve().parent
files_root = root_dir / "tests/results"
exemplars_path = files_root / "exemplars.json"

if not exemplars_path.is_file():
    raise SystemExit(f"Missing input file: {exemplars_path}")

data = json.loads(exemplars_path.read_text(encoding="utf-8"))
baseline_section = next(
    (
        section
        for section in data.get("sections", [])
        if section.get("title") == "Baseline - no Autoscaling"
    ),
    None,
)
if not baseline_section:
    raise SystemExit("Baseline section not found in exemplars.json")

data_source = []
for item in baseline_section.get("items", []):
    attributes = item.get("attributes", {})
    quality = attributes.get("quality")
    replicas = attributes.get("replicas")
    if quality is None or replicas is None:
        raise SystemExit(f"Missing baseline attributes in item: {item.get('csv')}")
    csv_name = item["csv"]
    if not csv_name.endswith(".csv"):
        csv_name = f"{csv_name}.csv"
    data_source.append(
        {
            "quality": quality,
            "replicas": replicas,
            "file": csv_name,
        }
    )

all_dfs = []
for src in data_source:
    df = pd.read_csv(files_root / src["file"])
    df["quality"] = src["quality"]
    df["replicas"] = src["replicas"]
    all_dfs.append(df)

full_df = pd.concat(all_dfs)

plt.style.use("bmh")
cmap = mpl.colormaps[mpl.rcParams["image.cmap"]]

req_duration = full_df[full_df["series"] == "req_duration_avg_ms"].copy()
slo_breach = full_df[full_df["series"] == "slo_breach_pct"].copy()
slo_breach_200 = full_df[full_df["series"] == "slo_breach_success_pct"].copy()
qualities = req_duration["quality"].unique()
replicas_values = np.sort(req_duration["replicas"].unique())

grp_duration = req_duration.groupby(["quality", "replicas"])
breach_ratio = (
    grp_duration["value"].apply(lambda s: (s > 1000).sum())
    / grp_duration["value"].count()
)

breach_pct_by_quality = (
    breach_ratio.mul(100)
    .unstack("replicas")
    .reindex(index=qualities, columns=replicas_values)
)
print(breach_pct_by_quality)

slo_breach_last = slo_breach.groupby(["quality", "replicas"])["value"].last()
slo_breach_by_quality = slo_breach_last.unstack("replicas").reindex(
    index=qualities, columns=replicas_values
)
print(slo_breach_by_quality)

slo_breach_200_last = slo_breach_200.groupby(["quality", "replicas"])["value"].last()
slo_breach_200_by_quality = slo_breach_200_last.unstack("replicas").reindex(
    index=qualities, columns=replicas_values
)
print(slo_breach_200_by_quality)

fig, ax = plt.subplots()

x = np.arange(len(qualities))
n_rep = len(replicas_values)
width = 0.9 / n_rep

norm = mpl.colors.Normalize(vmin=replicas_values.min(), vmax=replicas_values.max())

for i, r in enumerate(replicas_values):
    offset = (i - (n_rep - 3) / 2) * width
    y = slo_breach_200_by_quality[r].to_numpy()
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
