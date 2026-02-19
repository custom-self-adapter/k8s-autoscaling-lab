import json
from pathlib import Path

import pandas as pd
from pandas import DataFrame

SERIES_RENAMES = {
    "req_duration_avg_ms": "znn_req_duration_avg_ms",
    "requests_per_second": "znn_requests_per_second",
    "error_rate": "znn_error_rate",
    "avg_response_size": "ing_avg_response_size",
    "response_siz": "loc_response_size",
    "slo_breach_pct": "znn_slo_breach_pct",
    "slo_breach_success_pct": "znn_slo_breach_success_pct",
    "response_time": "loc_response_time",
    "user_count": "loc_user_count",
}

COLUMN_RENAMES = {
    "status_code": "loc_status_code",
    "response_size": "loc_response_size",
}


def select_series(df, series_name, extra_cols=None) -> DataFrame:
    cols = ["ts", "value"]
    if extra_cols:
        cols.extend([c for c in extra_cols if c in df.columns])
    subset = df[df["series"] == series_name]
    keep_cols = [c for c in cols if c in subset.columns]
    series_df = subset[keep_cols].copy()
    if "ts" in series_df.columns:
        series_df = series_df.sort_values("ts")
    return series_df


def filter_http_success(df: DataFrame, status_code_series: str):
    if df.empty or status_code_series not in df.columns:
        return df
    status = pd.to_numeric(df[status_code_series], errors="coerce")
    return df[status == 200]


def load_config_file(config_path: str):
    path = Path(config_path)
    if not path.is_file():
        raise SystemExit(f"{config_path} must exist")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise SystemExit(f"{config_path} must be a valid JSON file")


def read_results(data_source, files_root, extra_fields):
    root = Path(files_root)
    all_dfs = []
    for src in data_source:
        df = pd.read_csv(root / src["file"])
        for field in extra_fields:
            df[field] = src[field]
        all_dfs.append(df)
    if not all_dfs:
        return pd.DataFrame()
    return pd.concat(all_dfs, ignore_index=True)


def apply_standard_renames(
    df: DataFrame, series_renames=None, column_renames=None
) -> DataFrame:
    if df.empty:
        return df
    series_renames = series_renames or SERIES_RENAMES
    column_renames = column_renames or COLUMN_RENAMES
    updated = df.copy()
    if "series" in updated.columns:
        updated["series"] = updated["series"].replace(series_renames)
    if column_renames:
        updated = updated.rename(columns=column_renames)
    return updated
