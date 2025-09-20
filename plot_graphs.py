import sys
import pandas as pd
import matplotlib.pyplot as plt
from cycler import cycler

plt.style.use('bmh')
prop_cycle = plt.rcParams['axes.prop_cycle']
colors = [c['color'] for c in list(prop_cycle)]

data = pd.read_csv(sys.argv[1])

DUR_SERIES  = "nginx_ingress_avg_ms"
REQ_SERIES  = "requests_total_rps"
PODS_SERIES = "znn_pods_per_tag"

df_dur = (
    data[data["series"] == DUR_SERIES]
    .groupby("ts")["value"]
    .sum()
    .reset_index()
)

df_req = (
    data[data["series"] == REQ_SERIES]
    .groupby("ts")["value"]
    .sum()
    .reset_index()
)

df_pods = data[(data["series"] == PODS_SERIES)]
df_pods_pivot = (
    df_pods.groupby(["ts", "tag"])["value"].sum().unstack("tag").sort_index()
) if not df_pods.empty and "tag" in df_pods.columns else None

fig, ax = plt.subplots()
lines = []

if not df_dur.empty:
    ln_dur, = ax.plot(df_dur["ts"], df_dur["value"], label=DUR_SERIES, linestyle="-", color=colors[7])
    lines.append(ln_dur)

ax.set_ylabel("nginx request duration avg (ms)")

ax2 = ax.twinx()

if not df_req.empty:
    ln_req, = ax2.plot(df_req["ts"], df_req["value"], label=REQ_SERIES, linestyle="--")
    lines.append(ln_req)
else:
    ax2.plot([], [])

if df_pods_pivot is not None:
    for tag_col in df_pods_pivot.columns:
        ln_tag, = ax2.plot(
            df_pods_pivot.index,
            df_pods_pivot[tag_col],
            label=f"{PODS_SERIES}[tag={tag_col}]",
            linestyle="-",
        )
        lines.append(ln_tag)

ax2.set_ylabel("req/s & pods per tag")

ax.set_title("Nginx request duration vs K6 requests per second vs ZNN pods per tag")
ax.set_xlabel("Time")
ax.grid(True, axis="y", alpha=0.3)

labels = [l.get_label() for l in lines]
ax.legend(lines, labels, loc="best")

plt.tight_layout()
plt.show()
