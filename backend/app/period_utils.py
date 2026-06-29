"""Period label parsing, filtering, and chronological sorting helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Any

import pandas as pd

_YEAR_RE = re.compile(r"^(?:year\s*)?(\d{4})$", re.IGNORECASE)
_QUARTER_RE = re.compile(r"^(?:q|quarter\s*)([1-4])\s+(\d{4})$", re.IGNORECASE)
_HALF_YEAR_RE = re.compile(
    r"^(?:h|half[-_\s]*year\s*)([1-2])\s+(\d{4})$",
    re.IGNORECASE,
)
_MONTH_RE = re.compile(r"^(?:m|month\s*)(1[0-2]|[1-9])\s+(\d{4})$", re.IGNORECASE)

_GRANULARITY_ALIASES = {
    "year": "year",
    "years": "year",
    "half year": "half_year",
    "half-year": "half_year",
    "half_year": "half_year",
    "h": "half_year",
    "quarter": "quarter",
    "quarters": "quarter",
    "q": "quarter",
    "month": "month",
    "months": "month",
    "m": "month",
}

_GRANULARITY_RANK = {
    "year": 0,
    "half_year": 1,
    "quarter": 2,
    "month": 3,
}

PeriodSortKey = tuple[int, int, int, int, str]


def normalize_period_granularity(value: Any) -> str:
    """Normalize dropdown and data-source period granularity labels."""

    if value is None:
        return "quarter"
    normalized = str(value).strip().lower().replace("_", " ")
    return _GRANULARITY_ALIASES.get(normalized, normalized.replace(" ", "_"))


def period_sort_key(label: Any) -> PeriodSortKey:
    """Return a chronological key for common dashboard period labels."""

    text = "" if label is None else str(label).strip()
    lowered = text.lower()

    quarter_match = _QUARTER_RE.fullmatch(lowered)
    if quarter_match:
        quarter = int(quarter_match.group(1))
        year = int(quarter_match.group(2))
        return (0, year, (quarter - 1) * 3 + 1, _GRANULARITY_RANK["quarter"], lowered)

    half_year_match = _HALF_YEAR_RE.fullmatch(lowered)
    if half_year_match:
        half_year = int(half_year_match.group(1))
        year = int(half_year_match.group(2))
        return (
            0,
            year,
            (half_year - 1) * 6 + 1,
            _GRANULARITY_RANK["half_year"],
            lowered,
        )

    month_match = _MONTH_RE.fullmatch(lowered)
    if month_match:
        month = int(month_match.group(1))
        year = int(month_match.group(2))
        return (0, year, month, _GRANULARITY_RANK["month"], lowered)

    year_match = _YEAR_RE.fullmatch(lowered)
    if year_match:
        year = int(year_match.group(1))
        return (0, year, 1, _GRANULARITY_RANK["year"], lowered)

    return (1, 0, 0, 99, lowered)


def infer_period_granularity(label: Any) -> str | None:
    """Infer period granularity from a period label."""

    text = "" if label is None else str(label).strip().lower()
    if _QUARTER_RE.fullmatch(text):
        return "quarter"
    if _HALF_YEAR_RE.fullmatch(text):
        return "half_year"
    if _MONTH_RE.fullmatch(text):
        return "month"
    if _YEAR_RE.fullmatch(text):
        return "year"
    return None


def same_period_previous_year(current_period: str, candidates: Iterable[Any]) -> str | None:
    """Find the candidate matching the same period one year earlier."""

    sorted_candidates = sort_periods(candidates)
    current = current_period.strip().lower()
    target_key: tuple[int, int, int, int] | None = None

    quarter_match = _QUARTER_RE.fullmatch(current)
    if quarter_match:
        quarter = int(quarter_match.group(1))
        year = int(quarter_match.group(2)) - 1
        target_key = (0, year, (quarter - 1) * 3 + 1, _GRANULARITY_RANK["quarter"])

    half_year_match = _HALF_YEAR_RE.fullmatch(current)
    if half_year_match:
        half_year = int(half_year_match.group(1))
        year = int(half_year_match.group(2)) - 1
        target_key = (
            0,
            year,
            (half_year - 1) * 6 + 1,
            _GRANULARITY_RANK["half_year"],
        )

    month_match = _MONTH_RE.fullmatch(current)
    if month_match:
        month = int(month_match.group(1))
        year = int(month_match.group(2)) - 1
        target_key = (0, year, month, _GRANULARITY_RANK["month"])

    year_match = _YEAR_RE.fullmatch(current)
    if year_match:
        year = int(year_match.group(1)) - 1
        target_key = (0, year, 1, _GRANULARITY_RANK["year"])

    if target_key is None:
        return None

    for candidate in sorted_candidates:
        if period_sort_key(candidate)[:4] == target_key:
            return candidate
    return None


def sort_periods(periods: Iterable[Any]) -> list[str]:
    """Return unique non-empty period labels in chronological order."""

    unique_by_label: dict[str, str] = {}
    for period in periods:
        if period is None or pd.isna(period):
            continue
        label = str(period).strip()
        if not label:
            continue
        unique_by_label[label.lower()] = label
    return sorted(unique_by_label.values(), key=period_sort_key)


def period_range(
    periods: Iterable[Any],
    start_period: str | None,
    end_period: str | None,
) -> list[str]:
    """Return periods between start and end using chronological period order."""

    sorted_periods = sort_periods(periods)
    if not sorted_periods:
        return []

    start_key = period_sort_key(start_period) if start_period else period_sort_key(sorted_periods[0])
    end_key = period_sort_key(end_period) if end_period else period_sort_key(sorted_periods[-1])
    if start_key > end_key:
        start_key, end_key = end_key, start_key

    return [
        period
        for period in sorted_periods
        if start_key <= period_sort_key(period) <= end_key
    ]


def filter_by_granularity(df: pd.DataFrame, granularity: Any) -> pd.DataFrame:
    """Filter a DataFrame to one period_type when the column is available."""

    if "period_type" not in df.columns:
        return df.copy()

    normalized_granularity = normalize_period_granularity(granularity)
    period_types = df["period_type"].map(normalize_period_granularity)
    return df[period_types == normalized_granularity].copy()


def sort_period_frame(
    df: pd.DataFrame,
    *,
    time_column: str = "time",
    secondary_columns: Sequence[str] = (),
) -> pd.DataFrame:
    """Sort rows chronologically by period label, then by stable secondary fields."""

    if df.empty or time_column not in df.columns:
        return df.copy()

    result = df.copy()
    sort_keys = result[time_column].map(period_sort_key)
    result["__period_parse_rank"] = sort_keys.map(lambda key: key[0])
    result["__period_year"] = sort_keys.map(lambda key: key[1])
    result["__period_month"] = sort_keys.map(lambda key: key[2])
    result["__period_granularity"] = sort_keys.map(lambda key: key[3])
    result["__period_label"] = sort_keys.map(lambda key: key[4])

    helper_columns = [
        "__period_parse_rank",
        "__period_year",
        "__period_month",
        "__period_granularity",
        "__period_label",
    ]
    stable_secondary = [
        column
        for column in secondary_columns
        if column in result.columns and column not in helper_columns
    ]
    sorted_result = result.sort_values(
        [*helper_columns, *stable_secondary],
        kind="mergesort",
    )
    return sorted_result.drop(columns=helper_columns).reset_index(drop=True)
