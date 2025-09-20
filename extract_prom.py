import requests
import ssl
import pandas as pd
import math
from datetime import datetime, timezone, timedelta

ca_bundle_path = "vagrant-kubeadm-kubernetes/certs/rootCA.crt"

PROM_URL = "https://prometheus.k8s.lab"
QUERIES = {
    "nginx_ingress_avg_ms": """
      1000 *
      sum by (ingress, exported_namespace) (
        rate(nginx_ingress_controller_request_duration_seconds_sum{exported_namespace="default"}[1m])
      )
      /
      sum by (ingress, exported_namespace) (
        rate(nginx_ingress_controller_request_duration_seconds_count{exported_namespace="default"}[1m])
      )

    """,
    "requests_total_rps": """sum(rate(k6_http_reqs_total[1m]))""",
    "znn_pods_per_tag": """
      sum by (tag) (
        (
          max by (namespace, pod, tag) (
            label_replace(
              kube_pod_container_info{
                image=~".*:(20k|100k|200k|400k|600k|800k)(@.*)?$"
                ,namespace="default"
                # ,container="kube-znn"
              },
              "tag", "$1", "image", ".*:((?:20k|100k|200k|400k|600k|800k))(?:@.*)?$"
            )
          )
        )
        and on (namespace, pod)
        (kube_pod_status_phase{namespace="default",phase="Running"} == 1)
      )
    """
}

now = datetime.now(timezone.utc)
START = int((now - timedelta(minutes=7)).timestamp())
END   = int(now.timestamp())
# Prometheus scrape interval
STEP  = "15s"

def query_range(prom_url, promql, start, end, step):
    r = requests.get(
        f"{prom_url}/api/v1/query_range",
        params={"query": promql, "start": start, "end": end, "step": step},
        timeout=60,
        verify=ca_bundle_path
    )
    r.raise_for_status()
    return r.json()

def results_to_df(result_json, series_name):
    rows = []
    for serie in result_json.get("data", {}).get("result", []):
        labels = serie.get("metric", {})
        for ts, val in serie.get("values", []):
            ts = float(ts)
            try:
                value = float(val)
            except Exception:
                value = math.nan
            rows.append({
                "ts": pd.to_datetime(ts, unit="s", utc=True),
                "value": value,
                "series": series_name,
                **labels
            })
    if not rows:
        return pd.DataFrame(columns=["ts","value","series"])
    df = pd.DataFrame(rows).sort_values("ts")
    return df

all_dfs = []
for name, promql in QUERIES.items():
    j = query_range(PROM_URL, promql, START, END, STEP)
    df = results_to_df(j, name)
    all_dfs.append(df)

data = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
data.to_csv(f"./tests/results/prom_extract_{now.strftime('%Y%m%d%H%M')}.csv", index=False)
