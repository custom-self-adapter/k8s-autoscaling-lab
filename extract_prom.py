import logging
import math
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

ca_bundle_path = "vagrant-kubeadm-kubernetes/certs/rootCA.crt"

PROM_URL = "https://prometheus.k8s.lab"
SLO_SECONDS = 1.0


def build_queries(ns: str):
    req_duration_avg_ms = """
    1000 *
    sum(rate(request_duration_seconds_sum{host="znn"}[30s]))
    /
    sum(rate(request_duration_seconds_count{host="znn"}[30s]))
    """.strip()

    requests_per_second = """sum(rate(requests_total{host="znn"}[5m]))"""

    error_rate = """sum(rate(requests_total{host="znn", status="200"}[5m]))/sum(rate(requests_total{host="znn"}[5m]))"""

    znn_pods_per_tag = f"""
    sum by (tag) (
        (
            max by (namespace, pod, tag) (
                label_replace(
                    kube_pod_container_info{{
                        image=~".*:(20k|100k|200k|400k|600k|800k)(@.*)?$",
                        namespace="{ns}"
                    }},
                    "tag", "$1", "image", ".*:((?:20k|100k|200k|400k|600k|800k))(?:@.*)?$"
                )
            )
        )
        and on (namespace, pod)
        (kube_pod_status_phase{{namespace="{ns}"}} == 1)
    )
    """.strip()

    avg_response_size = f"""
    avg(
        rate(
            nginx_ingress_controller_response_size_sum{{exported_namespace="{ns}", ingress="kube-znn", status="200"}}
            [1m]
        )
    )
    /
    avg(
        rate(
            nginx_ingress_controller_response_size_count{{exported_namespace="{ns}", ingress="kube-znn", status="200"}}
            [1m]
        )
    )
    """

    slo_breach_pct = f"""
    100 *
    (
        1 -
        sum(rate(request_duration_seconds_bucket{{host="znn", le="{SLO_SECONDS:.1f}"}}[5m]))
        /
        sum(rate(request_duration_seconds_count{{host="znn"}}[5m]))
    )
    """

    success_within_slo_pct = f"""
    100 *
    sum(rate(request_duration_seconds_bucket{{host="znn", status="200", le="{SLO_SECONDS:.1f}"}}[5m]))
    /
    sum(rate(requests_total{{host="znn", status="200"}}[5m]))
    """

    return {
        "req_duration_avg_ms": req_duration_avg_ms,
        "requests_per_second": requests_per_second,
        "error_rate": error_rate,
        "znn_pods_per_tag": znn_pods_per_tag,
        "avg_response_size": avg_response_size,
        "slo_breach_pct": slo_breach_pct,
        "success_within_slo_pct": success_within_slo_pct,
    }


def query_range(prom_url, promql, start, end, step):
    r = requests.get(
        f"{prom_url}/api/v1/query_range",
        params={"query": promql, "start": start, "end": end, "step": step},
        timeout=60,
        verify=ca_bundle_path,
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
            rows.append(
                {
                    "ts": pd.to_datetime(ts, unit="s", utc=True),
                    "value": value,
                    "series": series_name,
                    **labels,
                }
            )
    if not rows:
        return pd.DataFrame(columns=["ts", "value", "series"])
    return pd.DataFrame(rows).sort_values("ts")


def extract(user_count=None, response_time=None):
    logging.basicConfig(format="[%(asctime)s] %(name)s %(message)s", level=logging.INFO)
    ns = "default"
    window_minutes = 5
    step = "5s"

    now = datetime.now(timezone.utc)
    START = int((now - timedelta(minutes=window_minutes)).timestamp())
    END = int(now.timestamp())
    queries = build_queries(ns)

    all_dfs = []
    for name, promql in queries.items():
        j = query_range(PROM_URL, promql, START, END, step)
        df = results_to_df(j, name)
        all_dfs.append(df)

    if user_count is not None:
        all_dfs.append(pd.DataFrame(user_count))
    if response_time is not None:
        all_dfs.append(pd.DataFrame(response_time).sort_values("ts"))

    data = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    csv_file = f"./tests/results/prom_extract_{now.strftime('%Y%m%d%H%M')}.csv"
    data.to_csv(csv_file, index=False)
    logging.info(f"Saved data to {csv_file}")


if __name__ == "__main__":
    extract()
