"""Deterministic chart-level calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from backend.app.filter_engine import get_outcome_fields
from backend.app.period_utils import filter_by_granularity, period_range, sort_period_frame
from backend.app.schemas import ChartSpec, FacetCalcResult, TabFilterResult

MISSING_PRIOR_WARNING = (
    "snapshot: prior period not found, growth_rate suppressed, rendering current period only"
)
INSUFFICIENT_TREND_WARNING = "trend: fewer than 3 periods in selected range"
EMPTY_FACET_WARNING = "facet has no rows after filtering and time slicing"

SUM_METRICS = {"spend", "activity", "response"}
FIRST_METRICS = {"roi", "cpm"}


@dataclass(frozen=True, slots=True)
class TimeSlice:
    current_df: pd.DataFrame
    prior_df: pd.DataFrame | None
    warnings: list[str]


def calculate_chart(
    chart_spec: ChartSpec,
    tab_filter_result: TabFilterResult,
    dropdown_state: dict[str, Any],
) -> list[FacetCalcResult]:
    """Calculate grouped results for one chart across all tab facets."""

    chart_spec = _chart_spec_with_display_metrics(chart_spec)
    wide_df = _ensure_metric_columns(tab_filter_result.shared_df, chart_spec.metrics)
    time_slice = _slice_time(wide_df, chart_spec, dropdown_state)
    facet_frames = _split_time_sliced_facets(
        time_slice.current_df,
        tab_filter_result,
        time_slice.prior_df,
    )

    results: list[FacetCalcResult] = []
    for label, filters, current_facet_df, prior_facet_df in facet_frames:
        warnings = list(time_slice.warnings)
        if current_facet_df.empty:
            warnings.append(EMPTY_FACET_WARNING)
            result_df = _empty_result_frame(wide_df, chart_spec)
        else:
            current_result = _group_facet_df(current_facet_df, chart_spec)
            if _should_add_growth_rate(chart_spec) and prior_facet_df is not None:
                prior_result = _group_facet_df(prior_facet_df, chart_spec)
                result_df = _merge_prior_and_add_growth(
                    current_result,
                    prior_result,
                    chart_spec,
                    warnings,
                )
            else:
                result_df = current_result
                if _should_add_growth_rate(chart_spec) and "growth_rate" not in result_df:
                    result_df = add_growth_rate(result_df, warnings)

        result_df = _sort_result_df(result_df, chart_spec)
        results.append(
            FacetCalcResult(
                label=label,
                filters=filters,
                df=result_df,
                formula_log=_formula_log(chart_spec),
                warnings=warnings,
            )
        )

    return results


def chart_metrics_for_calculation(chart_spec: ChartSpec) -> list[str]:
    """Return all metrics needed for calculation and display."""

    metrics: list[str] = []
    for metric in (
        *chart_spec.metrics,
        *chart_spec.axes.y,
        *chart_spec.axes.left_y,
        *chart_spec.axes.right_y,
    ):
        if metric not in metrics:
            metrics.append(metric)
    return metrics


def _chart_spec_with_display_metrics(chart_spec: ChartSpec) -> ChartSpec:
    metrics = chart_metrics_for_calculation(chart_spec)
    if metrics == chart_spec.metrics:
        return chart_spec
    return chart_spec.model_copy(update={"metrics": metrics})


def weighted_roi_by_spend(df: pd.DataFrame) -> pd.Series:
    """Aggregate ROI as spend-weighted ROI and spend as a sum."""

    spend = _sum_metric(df["spend"])
    roi = None if spend is None or spend == 0 else (df["roi"] * df["spend"]).sum() / spend
    return pd.Series({"roi": roi, "spend": spend})


def add_growth_rate(df: pd.DataFrame, warnings: list[str] | None = None) -> pd.DataFrame:
    """Append growth_rate from roi_current and roi_prior columns."""

    result = df.copy()
    if "roi_current" not in result.columns or "roi_prior" not in result.columns:
        result["growth_rate"] = None
        return result

    growth_values: list[float | None] = []
    for _, row in result.iterrows():
        prior = row["roi_prior"]
        current = row["roi_current"]
        if pd.isna(current):
            growth_values.append(None)
        elif pd.isna(prior) or prior == 0:
            growth_values.append(None)
            if warnings is not None:
                warnings.append("growth_rate: prior value is missing or zero")
        else:
            growth_values.append((current - prior) / abs(prior))

    result["growth_rate"] = growth_values
    return result


def add_metric_growth_rates(
    df: pd.DataFrame,
    metrics: list[str],
    warnings: list[str] | None = None,
) -> pd.DataFrame:
    """Append one growth-rate column per metric from current/prior columns."""

    result = df.copy()
    for metric in metrics:
        current_column = f"{metric}_current"
        prior_column = f"{metric}_prior"
        growth_column = f"{metric}_growth_rate"
        if current_column not in result.columns or prior_column not in result.columns:
            result[growth_column] = None
            continue

        growth_values: list[float | None] = []
        for _, row in result.iterrows():
            prior = row[prior_column]
            current = row[current_column]
            if pd.isna(current):
                growth_values.append(None)
            elif pd.isna(prior) or prior == 0:
                growth_values.append(None)
                if warnings is not None:
                    warnings.append(f"{growth_column}: prior value is missing or zero")
            else:
                growth_values.append((current - prior) / abs(prior))
        result[growth_column] = growth_values

    if "roi_growth_rate" in result.columns:
        result["growth_rate"] = result["roi_growth_rate"]
    return result


def add_null_metric_growth_rates(df: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    result = df.copy()
    for metric in metrics:
        result[f"{metric}_growth_rate"] = None
    if "growth_rate" not in result.columns:
        result["growth_rate"] = None
    return result


def _sort_result_df(df: pd.DataFrame, chart_spec: ChartSpec) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    sorting = chart_spec.sorting
    if sorting is not None:
        sort_column = _sort_column_for_field(sorting.field, df)
        if sort_column is not None and sort_column in df.columns:
            if _should_sort_grouped_line_bar_by_latest_period(chart_spec, sort_column, df):
                return _sort_grouped_line_bar_by_latest_period(
                    df,
                    sort_column,
                    sorting.direction,
                )
            secondary_columns = _secondary_sort_columns(df, chart_spec, exclude={sort_column})
            if sort_column == "time":
                sorted_df = sort_period_frame(df, secondary_columns=secondary_columns)
                if sorting.direction == "desc":
                    sorted_df = sorted_df.iloc[::-1].reset_index(drop=True)
                return sorted_df
            return (
                df.sort_values(
                    by=[sort_column, *secondary_columns],
                    ascending=[sorting.direction == "asc", *([True] * len(secondary_columns))],
                    na_position="last",
                    kind="mergesort",
                )
                .reset_index(drop=True)
            )

    if "time" not in df.columns:
        return df.copy()

    secondary_columns = _secondary_sort_columns(df, chart_spec, exclude={"time"})
    return sort_period_frame(df, secondary_columns=secondary_columns)


def _should_sort_grouped_line_bar_by_latest_period(
    chart_spec: ChartSpec,
    sort_column: str,
    df: pd.DataFrame,
) -> bool:
    return (
        chart_spec.visual_type == "grouped_line_bar"
        and sort_column != "time"
        and {"activity_group", "time", sort_column}.issubset(df.columns)
    )


def _sort_grouped_line_bar_by_latest_period(
    df: pd.DataFrame,
    sort_column: str,
    direction: str,
) -> pd.DataFrame:
    sorted_period_df = sort_period_frame(df, secondary_columns=["activity_group"])
    if sorted_period_df.empty:
        return sorted_period_df

    latest_period = sorted_period_df["time"].iloc[-1]
    latest_rows = sorted_period_df[sorted_period_df["time"] == latest_period]
    ordered_tactics = (
        latest_rows.sort_values(
            by=[sort_column, "activity_group"],
            ascending=[direction == "asc", True],
            na_position="last",
            kind="mergesort",
        )["activity_group"]
        .drop_duplicates()
        .tolist()
    )

    remaining_tactics = [
        tactic
        for tactic in sorted_period_df["activity_group"].drop_duplicates().tolist()
        if tactic not in ordered_tactics
    ]
    tactic_order = {tactic: index for index, tactic in enumerate([*ordered_tactics, *remaining_tactics])}

    result = sorted_period_df.copy()
    result["__tactic_sort_order"] = result["activity_group"].map(tactic_order)
    return (
        sort_period_frame(result, secondary_columns=["__tactic_sort_order"])
        .sort_values(
            by=["__tactic_sort_order"],
            kind="mergesort",
        )
        .drop(columns=["__tactic_sort_order"])
        .reset_index(drop=True)
    )


def _sort_column_for_field(field: str, df: pd.DataFrame) -> str | None:
    if field == "period":
        return "time"
    if field.endswith("_change"):
        growth_column = f"{field.removesuffix('_change')}_growth_rate"
        if growth_column in df.columns:
            return growth_column
        if field == "roi_change" and "growth_rate" in df.columns:
            return "growth_rate"
        return growth_column
    if field in df.columns:
        return field
    return None


def _secondary_sort_columns(
    df: pd.DataFrame,
    chart_spec: ChartSpec,
    exclude: set[str],
) -> list[str]:
    columns: list[str] = []
    for column in (
        "time",
        "activity_group",
        chart_spec.axes.x,
        chart_spec.axes.series,
        *chart_spec.metrics,
    ):
        if (
            column is not None
            and column in df.columns
            and column not in exclude
            and column not in columns
        ):
            columns.append(column)
    return columns


def _ensure_metric_columns(df: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    if all(metric in df.columns for metric in metrics):
        return df.copy()

    if {"metric", "value"}.issubset(df.columns):
        dimension_columns = [column for column in df.columns if column not in {"metric", "value"}]
        pivoted = (
            df.pivot_table(
                index=dimension_columns,
                columns="metric",
                values="value",
                aggfunc="first",
                dropna=False,
            )
            .reset_index()
            .rename_axis(None, axis=1)
        )
        return pivoted

    missing_metrics = [metric for metric in metrics if metric not in df.columns]
    raise ValueError(f"DataFrame is missing metric columns: {missing_metrics}")


def _slice_time(
    df: pd.DataFrame,
    chart_spec: ChartSpec,
    dropdown_state: dict[str, Any],
) -> TimeSlice:
    if "time" not in df.columns:
        raise ValueError("DataFrame must contain a time column")

    df = filter_by_granularity(df, dropdown_state.get("period_granularity"))
    if chart_spec.time_scope == "snapshot":
        return _slice_snapshot(df, dropdown_state)
    return _slice_trend(df, dropdown_state)


def _slice_snapshot(
    df: pd.DataFrame,
    dropdown_state: dict[str, Any],
) -> TimeSlice:
    current_period = _required_dropdown_value(dropdown_state, "snapshot_current_period")
    prior_period = _required_dropdown_value(dropdown_state, "snapshot_prior_period")

    current_df = df[df["time"] == current_period].copy()
    prior_df = df[df["time"] == prior_period].copy()

    if prior_df.empty:
        degraded_df = current_df.copy()
        degraded_df["growth_rate"] = None
        return TimeSlice(
            current_df=degraded_df,
            prior_df=None,
            warnings=[MISSING_PRIOR_WARNING],
        )

    return TimeSlice(current_df=current_df, prior_df=prior_df, warnings=[])


def _slice_trend(
    df: pd.DataFrame,
    dropdown_state: dict[str, Any],
) -> TimeSlice:
    start_period = _required_dropdown_value(dropdown_state, "trend_start_period")
    end_period = _required_dropdown_value(dropdown_state, "trend_end_period")
    valid_periods = period_range(df["time"].dropna().unique(), start_period, end_period)

    if len(valid_periods) < 3:
        return TimeSlice(
            current_df=df.iloc[0:0].copy(),
            prior_df=None,
            warnings=[INSUFFICIENT_TREND_WARNING],
        )

    return TimeSlice(
        current_df=sort_period_frame(df[df["time"].isin(valid_periods)]),
        prior_df=None,
        warnings=[],
    )


def _split_time_sliced_facets(
    time_df: pd.DataFrame,
    tab_filter_result: TabFilterResult,
    prior_df: pd.DataFrame | None = None,
) -> list[tuple[str, dict[str, str], pd.DataFrame, pd.DataFrame | None]]:
    if not tab_filter_result.facet_slices:
        return [("all", {}, time_df.copy(), None if prior_df is None else prior_df.copy())]

    facet_frames = []
    for facet in tab_filter_result.facet_slices:
        if not facet.filters:
            facet_frames.append(
                (
                    facet.label,
                    facet.filters,
                    time_df.copy(),
                    None if prior_df is None else prior_df.copy(),
                )
            )
            continue

        mask = _facet_mask(time_df, facet.filters)
        prior_facet_df = None
        if prior_df is not None:
            prior_mask = _facet_mask(prior_df, facet.filters)
            prior_facet_df = prior_df[prior_mask].copy()
        facet_frames.append(
            (facet.label, facet.filters, time_df[mask].copy(), prior_facet_df)
        )

    return facet_frames


def _facet_mask(df: pd.DataFrame, filters: dict[str, str]) -> pd.Series:
    if not filters:
        return pd.Series(True, index=df.index)

    masks = []
    for field, value in filters.items():
        if value == "blank":
            masks.append(df[field].isna() | (df[field] == ""))
        else:
            masks.append(df[field] == value)
    return pd.concat(masks, axis=1).all(axis=1)


def _group_facet_df(df: pd.DataFrame, chart_spec: ChartSpec) -> pd.DataFrame:
    outcome_fields = get_outcome_fields(df)
    group_fields = list(outcome_fields)
    if chart_spec.time_scope == "trend":
        group_fields.append("time")
    if chart_spec.data_level == "tactic":
        group_fields.append("activity_group")

    if not group_fields:
        group_fields = ["time"] if chart_spec.time_scope == "trend" else []

    if chart_spec.data_level == "portfolio":
        return _group_portfolio(df, group_fields, chart_spec)

    result = _group_tactic(df, group_fields, chart_spec)
    return _drop_empty_tactic_rows(result, chart_spec)


def _group_portfolio(
    df: pd.DataFrame,
    group_fields: list[str],
    chart_spec: ChartSpec,
) -> pd.DataFrame:
    if not group_fields:
        return pd.DataFrame([_aggregate_portfolio_group(df, chart_spec.metrics)])

    rows: list[dict[str, Any]] = []
    for key, group in df.groupby(group_fields, dropna=False, sort=True):
        row = _key_to_row(group_fields, key)
        row.update(_aggregate_portfolio_group(group, chart_spec.metrics))
        rows.append(row)
    return pd.DataFrame(rows)


def _aggregate_portfolio_group(
    group: pd.DataFrame,
    metrics: list[str],
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if "roi" in metrics and "spend" in group.columns:
        weighted = weighted_roi_by_spend(group)
        values["roi"] = weighted["roi"]
        values["spend"] = weighted["spend"]
    for metric in metrics:
        if metric in values:
            continue
        values[metric] = _aggregate_metric(group, metric)
    return values


def _group_tactic(
    df: pd.DataFrame,
    group_fields: list[str],
    chart_spec: ChartSpec,
) -> pd.DataFrame:
    aggregations = {
        metric: _aggregation_function(metric)
        for metric in chart_spec.metrics
        if metric in df.columns
    }
    if not aggregations:
        return df[group_fields].drop_duplicates().reset_index(drop=True)

    return (
        df.groupby(group_fields, dropna=False, sort=True)
        .agg(aggregations)
        .reset_index()
    )


def _drop_empty_tactic_rows(df: pd.DataFrame, chart_spec: ChartSpec) -> pd.DataFrame:
    if df.empty:
        return df

    metric_columns = [
        metric for metric in chart_spec.metrics if metric in df.columns
    ]
    if not metric_columns:
        return df

    return df[df[metric_columns].notna().any(axis=1)].reset_index(drop=True)


def _merge_prior_and_add_growth(
    current_result: pd.DataFrame,
    prior_result: pd.DataFrame,
    chart_spec: ChartSpec,
    warnings: list[str],
) -> pd.DataFrame:
    if prior_result.empty:
        result = current_result.copy()
        result = add_null_metric_growth_rates(result, chart_spec.metrics)
        warnings.append(MISSING_PRIOR_WARNING)
        return result

    merge_keys = _result_dimension_columns(current_result, chart_spec.metrics)
    merged = current_result.merge(
        prior_result,
        on=merge_keys,
        how="left",
        suffixes=("_current", "_prior"),
    )

    for metric in chart_spec.metrics:
        current_column = f"{metric}_current"
        if current_column in merged.columns:
            merged[metric] = merged[current_column]

    return add_metric_growth_rates(merged, chart_spec.metrics, warnings)


def _result_dimension_columns(df: pd.DataFrame, metrics: list[str]) -> list[str]:
    metric_columns = set(metrics)
    derived_columns = {
        "growth_rate",
        *(f"{metric}_current" for metric in metrics),
        *(f"{metric}_prior" for metric in metrics),
        *(f"{metric}_growth_rate" for metric in metrics),
    }
    return [
        column
        for column in df.columns
        if column not in metric_columns and column not in derived_columns
    ]


def _aggregate_metric(group: pd.DataFrame, metric: str) -> Any:
    if metric not in group.columns:
        return None
    if metric in SUM_METRICS:
        return _sum_metric(group[metric])
    return _first_metric(group[metric])


def _aggregation_function(metric: str):
    if metric in SUM_METRICS:
        return _sum_metric
    return _first_metric


def _sum_metric(series: pd.Series) -> Any:
    non_null = series.dropna()
    if non_null.empty:
        return None
    return non_null.sum()


def _first_metric(series: pd.Series) -> Any:
    non_null = series.dropna()
    if non_null.empty:
        return None
    return non_null.iloc[0]


def _empty_result_frame(df: pd.DataFrame, chart_spec: ChartSpec) -> pd.DataFrame:
    outcome_fields = get_outcome_fields(df)
    columns = list(outcome_fields)
    if chart_spec.time_scope == "trend":
        columns.append("time")
    if chart_spec.data_level == "tactic":
        columns.append("activity_group")
    columns.extend(metric for metric in chart_spec.metrics if metric not in columns)
    if _should_add_growth_rate(chart_spec) and "growth_rate" not in columns:
        columns.extend(
            f"{metric}_growth_rate"
            for metric in chart_spec.metrics
            if f"{metric}_growth_rate" not in columns
        )
        columns.append("growth_rate")
    return pd.DataFrame(columns=columns)


def _should_add_growth_rate(chart_spec: ChartSpec) -> bool:
    return (
        chart_spec.calculation.operation == "growth_rate"
        or "growth_rate" in chart_spec.calculation.also_compute
    )


def _formula_log(chart_spec: ChartSpec) -> str:
    formula_parts = [chart_spec.calculation.operation]
    if chart_spec.calculation.also_compute:
        formula_parts.extend(chart_spec.calculation.also_compute)
    return " + ".join(formula_parts)


def _required_dropdown_value(dropdown_state: dict[str, Any], field: str) -> str:
    value = dropdown_state.get(field)
    if not isinstance(value, str) or value == "":
        raise ValueError(f"dropdown_state must include {field!r}")
    return value


def _key_to_row(group_fields: list[str], key: Any) -> dict[str, Any]:
    if len(group_fields) == 1:
        key_values = (key,)
    else:
        key_values = tuple(key)
    return dict(zip(group_fields, key_values, strict=True))
