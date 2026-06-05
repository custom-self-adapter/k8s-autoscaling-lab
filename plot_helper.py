import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Pattern

import numpy as np
import pandas as pd
from pandas import DataFrame

PODS_SERIES = "znn_pods_per_tag"
CPU_LIMITS_SERIES = "kube_pod_cpu_limits"
RESP_TIME_SERIES = "loc_response_time"
STATUS_CODE_COL = "loc_status_code"
LOC_RESP_SIZE_COL = "loc_response_size"
SLO_MILLISECONDS = 1000
RESULT_FILE_PATTERN = re.compile(
    r"(?P<run>\d{2})_(?P<order>\d+)_(?P<configuration>.+)\.csv$"
)


@dataclass(frozen=True)
class MetricSpec:
    key: str
    title: str
    percent_axis: bool = False


@dataclass(frozen=True)
class ParetoObjective:
    key: str
    minimize: bool = True


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


def configuration_label(configuration: str, configuration_labels: Mapping[str, str]) -> str:
    return configuration_labels.get(configuration, configuration.replace("_", " ").title())


def discover_result_files(
    results_dir: Path,
    configuration_labels: Mapping[str, str],
    file_pattern: Pattern[str] = RESULT_FILE_PATTERN,
) -> DataFrame:
    rows = []
    for path in sorted(results_dir.glob("*.csv")):
        match = file_pattern.fullmatch(path.name)
        if not match:
            continue
        configuration = match.group("configuration")
        rows.append(
            {
                "file": path,
                "run": match.group("run"),
                "order": int(match.group("order")),
                "configuration": configuration,
                "label": configuration_label(configuration, configuration_labels),
            }
        )
    if not rows:
        raise SystemExit(
            f"Nenhum CSV no padrao <run>_<sequencial>_<cenario>.csv foi encontrado em {results_dir}"
        )
    return pd.DataFrame(rows).sort_values(["order", "run", "configuration"])


def safe_numeric_mean(series: pd.Series | None) -> float:
    if series is None:
        return math.nan
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    return float(numeric.mean()) if not numeric.empty else math.nan


def safe_grouped_numeric_sum_mean(
    df: DataFrame | None, group_col: str, value_col: str = "value"
) -> float:
    if df is None or df.empty or value_col not in df.columns:
        return math.nan
    if group_col not in df.columns:
        return safe_numeric_mean(df.get(value_col))

    grouped = df[[group_col, value_col]].copy()
    grouped[value_col] = pd.to_numeric(grouped[value_col], errors="coerce")
    grouped = grouped.dropna(subset=[group_col, value_col])
    if grouped.empty:
        return math.nan

    summed = grouped.groupby(group_col, sort=False)[value_col].sum()
    return float(summed.mean()) if not summed.empty else math.nan


def scale_bubble_sizes(
    values: pd.Series,
    min_size: float = 300.0,
    max_size: float = 2600.0,
    lower: float | None = None,
    upper: float | None = None,
) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    finite = numeric[np.isfinite(numeric)]
    if finite.empty:
        return pd.Series(np.full(len(numeric), min_size), index=numeric.index)

    lower = float(finite.min()) if lower is None else float(lower)
    upper = float(finite.max()) if upper is None else float(upper)
    if upper < lower:
        lower, upper = upper, lower
    if math.isclose(lower, upper):
        mid = (min_size + max_size) / 2.0
        return pd.Series(np.full(len(numeric), mid), index=numeric.index)

    scaled = min_size + (numeric - lower) * (max_size - min_size) / (upper - lower)
    return scaled.clip(lower=min_size, upper=max_size).fillna(min_size)


def padded_axis_upper(
    values: pd.Series, minimum: float, multiplier: float = 1.15
) -> float:
    numeric = pd.to_numeric(values, errors="coerce")
    finite = numeric[np.isfinite(numeric)]
    if finite.empty:
        return minimum
    return max(minimum, float(finite.max()) * multiplier)


def format_byte_size(value: float, precision: int = 1) -> str:
    if value >= 1024 * 1024:
        return f"{value / (1024 * 1024):.{precision}f} MiB"
    if value >= 1024:
        return f"{value / 1024:.{precision}f} KiB"
    return f"{value:.0f} B"


def add_resource_usage(
    df: DataFrame,
    pods_col: str = "pods_mean",
    cpu_limits_col: str = "cpu_limits_mean",
    output_col: str = "resource_usage",
) -> DataFrame:
    updated = df.copy()
    updated[output_col] = pd.to_numeric(
        updated[pods_col], errors="coerce"
    ) * pd.to_numeric(updated[cpu_limits_col], errors="coerce")
    return updated


def pareto_efficient_mask(
    df: DataFrame,
    objectives: Sequence[ParetoObjective],
    tolerance: float = 1e-12,
) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=bool, index=df.index)
    if not objectives:
        raise ValueError("Pelo menos um objetivo de Pareto deve ser informado.")

    normalized = []
    for objective in objectives:
        values = pd.to_numeric(df[objective.key], errors="coerce")
        normalized.append(values if objective.minimize else -values)

    matrix = pd.concat(normalized, axis=1)
    valid = matrix.notna().all(axis=1)
    mask = pd.Series(False, index=df.index)
    values = matrix.loc[valid].to_numpy(dtype=float)
    valid_index = matrix.loc[valid].index

    for idx, candidate in enumerate(values):
        others = np.delete(values, idx, axis=0)
        if others.size == 0:
            mask.loc[valid_index[idx]] = True
            continue

        weakly_better = np.all(others <= candidate + tolerance, axis=1)
        strictly_better = np.any(others < candidate - tolerance, axis=1)
        mask.loc[valid_index[idx]] = not np.any(weakly_better & strictly_better)

    return mask


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


def compute_run_metrics(file_info: pd.Series) -> dict:
    df = pd.read_csv(file_info["file"])
    df = apply_standard_renames(df)

    pods = select_series(df, PODS_SERIES)
    cpu_limits = select_series(df, CPU_LIMITS_SERIES)
    resp_time = select_series(
        df,
        RESP_TIME_SERIES,
        extra_cols=[STATUS_CODE_COL, LOC_RESP_SIZE_COL],
    )

    status_source = (
        resp_time[STATUS_CODE_COL]
        if STATUS_CODE_COL in resp_time.columns
        else pd.Series(dtype=float)
    )
    status_codes = pd.to_numeric(status_source, errors="coerce")

    success_mask = status_codes == 200
    success_rate = float(success_mask.mean() * 100) if len(success_mask) else math.nan

    resp_time_success = filter_http_success(resp_time, STATUS_CODE_COL)
    success_response_values = pd.to_numeric(
        (
            resp_time_success["value"]
            if "value" in resp_time_success.columns
            else pd.Series(dtype=float)
        ),
        errors="coerce",
    )
    slo_breach_success_mask = success_response_values > SLO_MILLISECONDS
    slo_breach_success_rate = (
        float(slo_breach_success_mask.mean() * 100)
        if len(slo_breach_success_mask)
        else math.nan
    )

    return {
        "run": file_info["run"],
        "order": int(file_info["order"]),
        "configuration": file_info["configuration"],
        "label": file_info["label"],
        "file": str(file_info["file"]),
        "pods_mean": safe_grouped_numeric_sum_mean(pods, "ts"),
        "cpu_limits_mean": safe_numeric_mean(cpu_limits.get("value")),
        "response_size_mean": safe_numeric_mean(
            resp_time_success.get(LOC_RESP_SIZE_COL)
        ),
        "response_time_mean": safe_numeric_mean(resp_time_success.get("value")),
        "success_rate": success_rate,
        "slo_breach_success_rate": slo_breach_success_rate,
    }


def summarize_runs(
    run_df: DataFrame,
    metrics: Sequence[MetricSpec],
    sort_columns: Sequence[str] = ("metric", "order", "configuration"),
) -> DataFrame:
    summary_rows = []
    configuration_cols = ["order", "configuration", "label"]
    for configuration_info, configuration_runs in run_df.groupby(configuration_cols, sort=True):
        order, configuration, label = configuration_info
        for metric in metrics:
            values = pd.to_numeric(configuration_runs[metric.key], errors="coerce").dropna()
            if values.empty:
                continue
            summary_rows.append(
                {
                    "order": order,
                    "configuration": configuration,
                    "label": label,
                    "metric": metric.key,
                    "metric_title": metric.title,
                    "runs": int(values.count()),
                    "mean": float(values.mean()),
                    "min": float(values.min()),
                    "max": float(values.max()),
                    "median": float(values.median()),
                    "std": float(values.std(ddof=0)),
                    "q25": float(values.quantile(0.25)),
                    "q75": float(values.quantile(0.75)),
                }
            )
    if not summary_rows:
        raise SystemExit(
            "Nao foi possivel calcular agregados a partir dos arquivos encontrados."
        )
    return pd.DataFrame(summary_rows).sort_values(list(sort_columns))
