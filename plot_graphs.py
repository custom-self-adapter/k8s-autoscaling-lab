import os
import glob
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from humanfriendly import format_size


plt.style.use("bmh")
prop_cycle = plt.rcParams["axes.prop_cycle"]
colors = [c["color"] for c in list(prop_cycle)]

arg_file = sys.argv[1] if len(sys.argv) > 1 else None
if arg_file is not None and os.path.isfile(arg_file):
    file_name = arg_file
else:
    file_name = max(glob.glob("tests/results/prom_extract*"))
print(f"Loading data from {file_name}")
data = pd.read_csv(file_name)

DUR_SERIES = "req_duration_avg_ms"
REQ_SERIES = "user_count"
PODS_SERIES = "znn_pods_per_tag"

df_dur = data[data["series"] == DUR_SERIES].groupby("ts")["value"].sum().reset_index()

df_req = data[data["series"] == REQ_SERIES].groupby("ts")["value"].sum().reset_index()

df_pods = data[(data["series"] == PODS_SERIES)]
df_pods_pivot = (
    (df_pods.groupby(["ts", "tag"])["value"].sum().unstack("tag").sort_index())
    if not df_pods.empty and "tag" in df_pods.columns
    else None
)

ts_min = []
ts_max = []

if not df_dur.empty:
    ts_min.append(df_dur["ts"].min())
    ts_max.append(df_dur["ts"].max())
if not df_req.empty:
    ts_min.append(df_req["ts"].min())
    ts_max.append(df_req["ts"].max())
if df_pods_pivot is not None and not df_pods_pivot.empty:
    ts_min.append(df_pods_pivot.index.min())
    ts_max.append(df_pods_pivot.index.max())

if ts_min and ts_max:
    t0 = min(ts_min)
    t1 = max(ts_max)
else:
    t0 = pd.Timestamp.utcnow()
    t1 = t0


def to_rel_seconds(ts_like):
    t0_utc = pd.to_datetime(t0, utc=True)
    ts = pd.to_datetime(ts_like, utc=True)

    delta = ts - t0_utc

    if hasattr(delta, "dt"):
        return delta.dt.total_seconds().astype("float")
    elif isinstance(delta, pd.TimedeltaIndex):
        return delta / np.timedelta64(1, "s")
    else:
        return float(delta.total_seconds())


fig = plt.figure(figsize=(12, 6), constrained_layout=True)
gs = fig.add_gridspec(nrows=3, ncols=1, height_ratios=[3, 2, 1])
ax_graph = fig.add_subplot(gs[0])
ax_grap2 = fig.add_subplot(gs[1])
ax_table = fig.add_subplot(gs[2])

lines = []

ln_slo = ax_graph.axhline(y=1000, linestyle=":", label="SLO", color=colors[1])
lines.append(ln_slo)

if not df_dur.empty:
    (ln_dur,) = ax_graph.plot(
        to_rel_seconds(df_dur["ts"]),
        df_dur["value"],
        label=DUR_SERIES,
        linestyle="-",
        color=colors[2],
    )
    lines.append(ln_dur)
ax_graph.set_ylabel("ZNN request duration avg (ms)")

ax_rps = ax_graph.twinx()
if not df_req.empty:
    (ln_req,) = ax_rps.plot(
        to_rel_seconds(df_req["ts"]),
        df_req["value"],
        label=REQ_SERIES,
        linestyle="-",
        color=colors[3],
    )
    lines.append(ln_req)
else:
    ax_rps.plot([], [])
ax_rps.set_ylabel("Locust User Count")
ax_rps.grid(False)

ax_pods = ax_graph.twinx()
ax_pods.spines["right"].set_position(("axes", 1.10))
ax_pods.plot([], [])
ax_pods.grid(False)

if df_pods_pivot is not None:
    df_pods_pivot.rename(columns=lambda c: c.zfill(4), inplace=True)
    metrics = df_pods_pivot.columns.tolist()
    metrics.sort()
    cmap = plt.get_cmap("autumn")
    autumn = cmap(np.linspace(0.75, 0, len(metrics)))
    for color, tag_col in zip(autumn, metrics):
        (ln_tag,) = ax_pods.plot(
            to_rel_seconds(df_pods_pivot.index),
            df_pods_pivot[tag_col],
            label=f"{PODS_SERIES}[tag={tag_col}]",
            linestyle="-",
            color=color,
        )
        lines.append(ln_tag)
ax_pods.set_ylabel("Number of Pods Running (per tag)")

ax_graph.set_title("ZNN request duration vs Locust User Count vs ZNN Pods per tag")
ax_graph.set_xlabel("Time")
ax_graph.grid(True, axis="y", alpha=0.3)

labels = [line.get_label() for line in lines]
ax_graph.legend(
    lines,
    labels,
    loc="upper right",
    bbox_to_anchor=(1.5, 1),
    ncols=1,
    frameon=True,
    borderaxespad=0.0
)

def mmss_fmt(x, pos):
    x = max(0, float(x))
    m = int(x // 60)
    s = int(x % 60)
    return f"{m:02d}:{s:02d}"
ax_graph.xaxis.set_major_formatter(mtick.FuncFormatter(mmss_fmt))

ax_graph.set_ylim(0, 5000)
ax_rps.set_ylim(0, 210)
ax_pods.set_ylim(0, 5.5)

ax_grap2.set_title("Response Size and Success Rate")
lines2 = []

avg_response_sizes = data[data["series"] == "avg_response_size"][["ts", "value"]]
(ln_resp_size,) = ax_grap2.plot(
    to_rel_seconds(avg_response_sizes["ts"]),
    avg_response_sizes["value"],
    label="Response sizes (MB)",
    color=colors[0]
)
lines2.append(ln_resp_size)
ax_grap2.yaxis.set_major_formatter(mtick.FuncFormatter(format_size))
ax_grap2.xaxis.set_major_formatter(mtick.FuncFormatter(mmss_fmt))

requests_200_percent = data[data["series"] == "requests_200_percent"]
ax_200 = ax_grap2.twinx()
ax_200.spines["right"]
ax_200.grid(False)
(ln_success,) = ax_200.plot(
    to_rel_seconds(requests_200_percent["ts"]),
    requests_200_percent["value"],
    label="Success rate",
    color=colors[1]
)
lines2.append(ln_success)
ax_grap2.legend(
    lines2,
    [line.get_label() for line in lines2],
    loc="upper right",
    bbox_to_anchor=(1.4, 1),
    frameon=True,
    borderaxespad=0.0
)

data_req_duration = data[data["series"] == DUR_SERIES]
req_duration_breach = (data_req_duration["value"]>1000).astype(float).mean() * 100

data_pods_per_tag = data[data["series"] == PODS_SERIES]
pods_mean = data_pods_per_tag["value"].mean()

avg_response_size = avg_response_sizes.loc[avg_response_sizes["ts"].idxmax(), "value"]

# reqs_per_tag = data_pods_per_tag["tag"].value_counts().rename(index=lambda q: f"Requests at {q}")

metrics = [
    'Avg Requests above SLO (1s)',
    'Avg Pods',
    'Avg Response Size'
]
values = [
    f"{req_duration_breach:.2f}%",
    f"{pods_mean:.2f}",
    format_size(avg_response_size, binary=True)
]

series_table = pd.Series(data=values, index=metrics)

ax_table.axis('off')

tbl = ax_table.table(
    cellText=[[v] for v in series_table.values],
    rowLabels=series_table.index,
    bbox=[0.6, 0.0, 0.1, 1.0],
    edges='closed',
    loc='center'
)

# fig.set_constrained_layout_pads(w_pad=0.02, h_pad=0.02, hspace=0.02)
plt.show()
