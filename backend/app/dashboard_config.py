"""Build frontend dashboard configuration from the active data source."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from pathlib import Path
import re
from typing import Any

import pandas as pd

from backend.app.compile_pipeline import DEFAULT_DATA_PATHS
from backend.app.filter_engine import build_outcome_field_combinations, get_outcome_fields
from backend.app.grid_parser import parse_config_aliases
from backend.app.period_utils import (
    infer_period_granularity,
    normalize_period_granularity,
    same_period_previous_year,
    sort_periods,
)
from backend.app.schemas import DashboardConfigResponse, Source
from backend.app.tab_configs import AGGREGATE_VALUES, TAB_CONFIGS

GRANULARITY_PRIORITY = ["year", "half_year", "quarter", "month"]
METRIC_ORDER = ["roi", "spend", "response", "cpm", "activity"]
METRIC_ALIASES = {
    "activity": "activity",
    "portfolio activity": "activity",
    "cpm": "cpm",
    "portfolio cpm": "cpm",
    "gross cost per conversion": "cpm",
    "response": "response",
    "portfolio response": "response",
    "roi": "roi",
    "gross portfolio roi": "roi",
    "spend": "spend",
    "gross portfolio spend": "spend",
}

BLANK_OPTION = "blank"
AGGREGATE_ORDER = {
    value: index for index, value in enumerate(AGGREGATE_VALUES)
}


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METRIC_FORMAT_PATH = (
    PROJECT_ROOT / "supporting_files" / "unit_sign_config.csv"
)

def build_dashboard_config(
    source: Source = "bi",
    data_paths: Mapping[str, Path] | None = None,
    data_frames: Mapping[str, pd.DataFrame] | None = None,
    grid_path: Path | str | None = "visualgrid.xlsx",
    outcome_field_aliases: Mapping[str, str] | None = None,
    metric_format_path: Path | str | None = DEFAULT_METRIC_FORMAT_PATH,
) -> DashboardConfigResponse:
    """Derive dropdown options and default state from the selected source data."""

    df = _load_source_dataframe(source, data_paths, data_frames)
    outcome_field_options = _build_outcome_field_options(df)
    aliases = _load_outcome_field_aliases(grid_path, outcome_field_aliases)
    metric_options = _build_metric_options(df)
    period_options = _build_period_options(df)
    period_defaults = _build_period_defaults(period_options)
    default_granularity = _select_default_granularity(period_options)
    default_periods = period_defaults[default_granularity]

    return DashboardConfigResponse(
        tabs=[
            {"tab_num": tab.tab_num, "tab_name": tab.tab_name}
            for tab in sorted(TAB_CONFIGS.values(), key=lambda tab: _dotted_key(tab.tab_num))
        ],
        outcome_field_options=outcome_field_options,
        outcome_field_labels=_build_outcome_field_labels(
            outcome_field_options,
            aliases,
        ),
        outcome_field_combinations_by_tab=_build_outcome_field_combinations_by_tab(df),
        metric_format_config=_load_metric_format_config(metric_format_path),
        metric_options=metric_options,
        period_options=period_options,
        period_defaults=period_defaults,
        default_dropdown_state={
            "outcome_fields": _default_outcome_fields(df, outcome_field_options),
            "metric": _default_metric(metric_options),
            "period_granularity": default_granularity,
            "snapshot_current_period": default_periods["snapshot_current_period"],
            "snapshot_prior_period": default_periods["snapshot_prior_period"],
            "trend_start_period": default_periods["trend_start_period"],
            "trend_end_period": default_periods["trend_end_period"],
        },
    )


def _build_outcome_field_combinations_by_tab(
    df: pd.DataFrame,
) -> dict[str, list[dict[str, str]]]:
    return {
        tab.tab_num: build_outcome_field_combinations(tab, df)
        for tab in sorted(TAB_CONFIGS.values(), key=lambda tab: _dotted_key(tab.tab_num))
    }


def _load_metric_format_config(
    metric_format_path: Path | str | None,
) -> dict[str, dict[str, Any]]:
    if metric_format_path is None:
        return {}

    path = Path(metric_format_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"Metric format config not found: {path}")

    config: dict[str, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"metric", "unit_sign", "keep_digit", "alias"}
        available_columns = set(reader.fieldnames or [])
        missing_columns = required_columns - available_columns
        if missing_columns:
            raise ValueError(
                "Metric format config is missing columns: "
                + ", ".join(sorted(missing_columns))
            )

        for row_number, row in enumerate(reader, start=2):
            metric = str(row.get("metric") or "").strip()
            if not metric:
                continue

            keep_digit_text = str(row.get("keep_digit") or "").strip()
            try:
                keep_digit = int(keep_digit_text)
            except ValueError as exc:
                raise ValueError(
                    f"Metric format config row {row_number} has invalid keep_digit"
                ) from exc
            if keep_digit < 0:
                raise ValueError(
                    f"Metric format config row {row_number} has negative keep_digit"
                )

            rule = {
                "unit_sign": str(row.get("unit_sign") or "").strip(),
                "keep_digit": keep_digit,
            }
            alias = str(row.get("alias") or "").strip()
            for configured_name in (metric, alias):
                if not configured_name:
                    continue
                key = _normalize_alias_key(configured_name)
                existing = config.get(key)
                if existing is not None and existing != rule:
                    raise ValueError(
                        f"Metric format config has conflicting rules for {configured_name!r}"
                    )
                config[key] = rule

    return config

def _load_outcome_field_aliases(
    grid_path: Path | str | None,
    outcome_field_aliases: Mapping[str, str] | None,
) -> dict[str, str]:
    if outcome_field_aliases is not None:
        return {
            str(field_name): str(alias)
            for field_name, alias in outcome_field_aliases.items()
            if str(field_name).strip() and str(alias).strip()
        }
    if grid_path is None:
        return {}

    try:
        return parse_config_aliases(Path(grid_path))
    except FileNotFoundError:
        return {}


def _load_source_dataframe(
    source: Source,
    data_paths: Mapping[str, Path] | None,
    data_frames: Mapping[str, pd.DataFrame] | None,
) -> pd.DataFrame:
    if data_frames is not None and source in data_frames:
        return data_frames[source].copy()

    active_paths = DEFAULT_DATA_PATHS if data_paths is None else data_paths
    path = active_paths.get(source)
    if path is None:
        raise ValueError(f"No data path configured for source: {source}")
    if not Path(path).exists():
        raise FileNotFoundError(f"Data source file not found: {path}")
    return pd.read_csv(path)


def _build_outcome_field_options(df: pd.DataFrame) -> dict[str, list[str]]:
    options: dict[str, list[str]] = {}
    for field in get_outcome_fields(df):
        labels = [_option_label(value) for value in df[field].drop_duplicates()]
        unique_labels = sorted(set(labels), key=_option_sort_key)
        if unique_labels:
            options[field] = unique_labels
    return options


def _build_outcome_field_labels(
    outcome_field_options: Mapping[str, list[str]],
    aliases: Mapping[str, str],
) -> dict[str, str]:
    normalized_aliases = {
        _normalize_alias_key(field_name): alias.strip()
        for field_name, alias in aliases.items()
        if str(alias).strip()
    }
    return {
        field_name: normalized_aliases.get(
            _normalize_alias_key(field_name),
            field_name,
        )
        for field_name in outcome_field_options
    }


def _build_metric_options(df: pd.DataFrame) -> list[str]:
    metrics: set[str] = set()
    if "metric" in df.columns:
        metrics.update(_canonical_metric_name(value) for value in df["metric"].dropna())
    for metric in METRIC_ORDER:
        if metric in df.columns:
            metrics.add(metric)
    ordered = [metric for metric in METRIC_ORDER if metric in metrics]
    return ordered or ["roi"]


def _build_period_options(df: pd.DataFrame) -> dict[str, list[str]]:
    options = {granularity: [] for granularity in GRANULARITY_PRIORITY}
    if "time" not in df.columns:
        return options

    if "period_type" in df.columns:
        for granularity in GRANULARITY_PRIORITY:
            normalized_types = df["period_type"].map(normalize_period_granularity)
            periods = df.loc[normalized_types == granularity, "time"]
            options[granularity] = sort_periods(periods)
        return options

    period_groups: dict[str, list[Any]] = {granularity: [] for granularity in GRANULARITY_PRIORITY}
    for period in df["time"].dropna().drop_duplicates():
        granularity = infer_period_granularity(period)
        if granularity in period_groups:
            period_groups[granularity].append(period)
    return {
        granularity: sort_periods(periods)
        for granularity, periods in period_groups.items()
    }


def _build_period_defaults(
    period_options: Mapping[str, list[str]],
) -> dict[str, dict[str, str]]:
    defaults: dict[str, dict[str, str]] = {}
    for granularity, periods in period_options.items():
        if not periods:
            continue

        current_period = periods[-1]
        prior_period = same_period_previous_year(current_period, periods)
        if prior_period is None:
            prior_period = periods[-2] if len(periods) > 1 else current_period

        defaults[granularity] = {
            "snapshot_current_period": current_period,
            "snapshot_prior_period": prior_period,
            "trend_start_period": periods[0],
            "trend_end_period": periods[-1],
        }

    if not defaults:
        defaults["quarter"] = {
            "snapshot_current_period": "",
            "snapshot_prior_period": "",
            "trend_start_period": "",
            "trend_end_period": "",
        }
    return defaults


def _select_default_granularity(period_options: Mapping[str, list[str]]) -> str:
    for granularity in GRANULARITY_PRIORITY:
        if len(period_options.get(granularity, [])) >= 3:
            return granularity
    for granularity in GRANULARITY_PRIORITY:
        if period_options.get(granularity):
            return granularity
    return "quarter"


def _default_outcome_fields(
    df: pd.DataFrame,
    outcome_field_options: Mapping[str, list[str]],
) -> dict[str, list[str]]:
    outcome_fields = [
        field for field in outcome_field_options.keys() if field in df.columns
    ]
    if not outcome_fields:
        return {}

    candidate_df = _default_candidate_df(df)
    if candidate_df.empty:
        candidate_df = df

    records = candidate_df[outcome_fields].drop_duplicates().to_dict("records")
    if not records:
        return {}

    records.sort(
        key=lambda record: tuple(
            _option_sort_key(_option_label(record[field]))
            for field in outcome_fields
        )
    )
    selected = records[0]
    return {
        field: [_option_label(selected[field])]
        for field in outcome_fields
        if _option_label(selected[field]) in outcome_field_options[field]
    }


def _default_candidate_df(df: pd.DataFrame) -> pd.DataFrame:
    tabs = sorted(TAB_CONFIGS.values(), key=lambda tab: _dotted_key(tab.tab_num))
    if not tabs:
        return df

    filtered_df = df.copy()
    for condition in tabs[0].tactic_filter:
        if condition.field not in filtered_df.columns:
            continue
        filtered_df = _apply_filter_condition(filtered_df, condition)
    return filtered_df


def _apply_filter_condition(df: pd.DataFrame, condition: Any) -> pd.DataFrame:
    series = df[condition.field]
    if condition.op == "is_blank":
        mask = series.isna() | (series == "")
    elif condition.op == "is_not_blank":
        mask = series.notna() & (series != "")
    elif condition.op == "eq":
        mask = series == condition.value
    elif condition.op == "in":
        mask = series.isin(condition.values or [])
    elif condition.op == "not_in":
        mask = ~series.isin(condition.values or [])
    elif condition.op == "gte":
        mask = series >= condition.value
    elif condition.op == "lte":
        mask = series <= condition.value
    else:
        return df
    return df[mask].copy()


def _default_metric(metric_options: list[str]) -> str:
    return "roi" if "roi" in metric_options else metric_options[0]


def _canonical_metric_name(value: Any) -> str:
    normalized = str(value).strip().lower()
    if normalized in METRIC_ALIASES:
        return METRIC_ALIASES[normalized]
    if "cost per" in normalized:
        return "cpm"
    for metric in METRIC_ORDER:
        if normalized == metric or normalized.endswith(f" {metric}"):
            return metric
    return normalized


def _option_label(value: Any) -> str:
    if pd.isna(value) or value == "":
        return BLANK_OPTION
    return str(value)


def _option_sort_key(value: str) -> tuple[int, int, str]:
    normalized = value.strip().lower()
    if normalized in AGGREGATE_ORDER:
        return (0, AGGREGATE_ORDER[normalized], normalized)
    return (1, 0, normalized)


def _is_aggregate_option(value: str) -> bool:
    return value.strip().lower() in AGGREGATE_ORDER


def _dotted_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def _normalize_alias_key(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())
    return normalized.strip("_")
