import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick


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

fig, ax = plt.subplots()
lines = []

ln_slo = ax.axhline(y=3000, linestyle=":", label="SLO", color=colors[1])
lines.append(ln_slo)

if not df_dur.empty:
    ln_dur, = ax.plot(to_rel_seconds(df_dur["ts"]), df_dur["value"], label=DUR_SERIES, linestyle=":", color=colors[2])
    lines.append(ln_dur)
ax.set_ylabel("nginx request duration avg (ms)")

ax2 = ax.twinx()
if not df_req.empty:
    ln_req, = ax2.plot(to_rel_seconds(df_req["ts"]), df_req["value"], label=REQ_SERIES, linestyle="--", color=colors[3])
    lines.append(ln_req)
else:
    ax2.plot([], [])
ax2.set_ylabel("K6 Requests per second (rps)")
ax2.grid(False)

ax3 = ax.twinx()
ax3.spines["right"].set_position(("axes", 1.12))
ax3.plot([], [])
ax3.grid(False)

if df_pods_pivot is not None:
    df_pods_pivot.rename(columns=lambda c: c.zfill(4), inplace=True)
    columns = df_pods_pivot.columns.tolist()
    columns.sort()
    cmap = plt.get_cmap('autumn')
    autumn = cmap(np.linspace(0.75, 0, len(columns)))
    for color, tag_col in zip(autumn, columns):
        ln_tag, = ax3.plot(
            to_rel_seconds(df_pods_pivot.index),
            df_pods_pivot[tag_col],
            label=f"{PODS_SERIES}[tag={tag_col}]",
            linestyle="-",
            color=color
        )
        lines.append(ln_tag)
ax3.set_ylabel("Number of Pods Running (per tag)")

ax.set_title("Nginx request duration vs K6 requests per second vs ZNN pods per tag")
ax.set_xlabel("Time")
ax.grid(True, axis="y", alpha=0.3)

labels = [l.get_label() for l in lines]
ax.legend(lines, labels, loc="best")


def mmss_fmt(x, pos):
    x = max(0, float(x))
    m = int(x // 60)
    s = int(x % 60)
    return f"{m:02d}:{s:02d}"


ax.xaxis.set_major_formatter(mtick.FuncFormatter(mmss_fmt))

plt.tight_layout()
plt.show()
