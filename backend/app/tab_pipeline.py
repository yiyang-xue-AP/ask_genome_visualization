"""Runtime tab data pipeline for /api/tab/{tab_num}."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from backend.app.calculation_engine import calculate_chart, chart_metrics_for_calculation
from backend.app.compile_pipeline import DEFAULT_DATA_PATHS
from backend.app.filter_engine import (
    build_available_outcome_field_options,
    filter_tab,
    normalize_dropdown_state,
)
from backend.app.llm_chart_compiler import ChartSpecCache, spec_cache
from backend.app.schemas import (
    ChartData,
    ChartSpec,
    FacetCalcResult,
    TabFilterResult,
    TabRequest,
    TabResponse,
)
from backend.app.tab_configs import TAB_CONFIGS

FilterFn = Callable[[Any, dict[str, Any], pd.DataFrame], TabFilterResult]
CalculateFn = Callable[[ChartSpec, TabFilterResult, dict[str, Any]], list[FacetCalcResult]]
_DATAFRAME_CACHE: dict[tuple[str, str, float], pd.DataFrame] = {}
_METRIC_ALIASES = {
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
_AXIS_FIELD_ALIASES = {
    "activity": "activity_group",
    "activity_group": "activity_group",
    "activitygroup": "activity_group",
    "channel": "activity_group",
    "channels": "activity_group",
    "tactic": "activity_group",
    "tactics": "activity_group",
    "date": "time",
    "period": "time",
    "periods": "time",
    "quarter": "time",
    "quarters": "time",
    "time": "time",
    "time_period": "time",
}
CATEGORY_LABEL_COLUMN = "category_label"
CATEGORY_METRIC_COLUMN = "category_metric"
CATEGORY_RANK_COLUMN = "category_rank"


def build_tab_response(
    tab_num: str,
    request: TabRequest,
    cache: ChartSpecCache | None = None,
    data_paths: Mapping[str, Path] | None = None,
    data_frames: Mapping[str, pd.DataFrame] | None = None,
    filter_fn: FilterFn = filter_tab,
    calculate_fn: CalculateFn = calculate_chart,
) -> TabResponse:
    """Build a tab response from cached ChartSpecs and deterministic calculations."""

    active_cache = spec_cache if cache is None else cache
    tab_spec = TAB_CONFIGS.get(tab_num)
    if tab_spec is None:
        raise ValueError(f"Unknown tab_num: {tab_num}")

    chart_specs = _chart_specs_for_tab(active_cache, tab_num)
    if not chart_specs:
        raise ValueError(f"No compiled ChartSpecs found for tab_num: {tab_num}")

    source = _single_source_for_tab(chart_specs)
    source_df = _load_source_dataframe(source, data_paths, data_frames)

    normalized_dropdown_state = normalize_dropdown_state(
        tab_spec,
        request.dropdown_state,
        source_df,
    )
    available_outcome_field_options = build_available_outcome_field_options(
        tab_spec,
        normalized_dropdown_state,
        source_df,
    )

    tab_filter_result = filter_fn(tab_spec, normalized_dropdown_state, source_df)
    tab_filter_result = _prepare_shared_metric_frame(tab_filter_result, chart_specs)
    charts = [
        _assemble_chart_data(
            chart_spec=chart_spec,
            tab_filter_result=tab_filter_result,
            dropdown_state=normalized_dropdown_state,
            calculate_fn=calculate_fn,
        )
        for chart_spec in chart_specs
    ]

    return TabResponse(
        tab_num=tab_num,
        auto_filtered_fields=tab_filter_result.auto_filtered_fields,
        available_outcome_field_options=available_outcome_field_options,
        normalized_dropdown_state=normalized_dropdown_state,
        charts=charts,
    )


def _chart_specs_for_tab(cache: ChartSpecCache, tab_num: str) -> list[ChartSpec]:
    specs: list[ChartSpec] = []
    for entry in cache.values():
        spec = entry.get("spec")
        if isinstance(spec, ChartSpec) and spec.tab.num == tab_num:
            specs.append(spec)
    return specs


def _single_source_for_tab(chart_specs: list[ChartSpec]) -> str:
    sources = {chart_spec.source for chart_spec in chart_specs}
    if len(sources) != 1:
        raise ValueError("A tab request currently supports exactly one chart source")
    return next(iter(sources))


def _load_source_dataframe(
    source: str,
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

    resolved_path = Path(path)
    cache_key = (source, str(resolved_path), resolved_path.stat().st_mtime)
    cached_df = _DATAFRAME_CACHE.get(cache_key)
    if cached_df is None:
        stale_keys = [
            key
            for key in _DATAFRAME_CACHE
            if key[0] == source and key[1] == str(resolved_path)
        ]
        for key in stale_keys:
            _DATAFRAME_CACHE.pop(key, None)
        cached_df = pd.read_csv(resolved_path)
        _DATAFRAME_CACHE[cache_key] = cached_df

    return cached_df.copy()


def _prepare_shared_metric_frame(
    tab_filter_result: TabFilterResult,
    chart_specs: list[ChartSpec],
) -> TabFilterResult:
    shared_df = tab_filter_result.shared_df
    required_metrics = sorted(
        {
            metric
            for chart_spec in chart_specs
            for metric in chart_metrics_for_calculation(chart_spec)
        }
    )

    if all(metric in shared_df.columns for metric in required_metrics):
        return tab_filter_result
    if not {"metric", "value"}.issubset(shared_df.columns):
        return tab_filter_result

    dimension_columns = [column for column in shared_df.columns if column not in {"metric", "value"}]
    metric_frame = shared_df.copy()
    metric_frame["metric"] = metric_frame["metric"].map(_canonical_metric_name)
    wide_df = (
        metric_frame.groupby([*dimension_columns, "metric"], dropna=False)["value"]
        .first()
        .unstack("metric")
        .reset_index()
        .rename_axis(None, axis=1)
    )
    for metric in required_metrics:
        if metric not in wide_df.columns:
            wide_df[metric] = pd.NA

    return TabFilterResult(
        shared_df=wide_df,
        facet_slices=tab_filter_result.facet_slices,
        auto_filtered_fields=tab_filter_result.auto_filtered_fields,
    )


def _canonical_metric_name(value: Any) -> str:
    normalized = str(value).strip().lower()
    if normalized in _METRIC_ALIASES:
        return _METRIC_ALIASES[normalized]
    if "cost per" in normalized:
        return "cpm"
    for metric in ("activity", "cpm", "response", "roi", "spend"):
        if normalized == metric or normalized.endswith(f" {metric}"):
            return metric
    return normalized


def _assemble_chart_data(
    chart_spec: ChartSpec,
    tab_filter_result: TabFilterResult,
    dropdown_state: dict[str, Any],
    calculate_fn: CalculateFn,
) -> ChartData:
    facet_results = calculate_fn(chart_spec, tab_filter_result, dropdown_state)
    facets = [
        _assemble_facet_data(chart_spec, facet_result)
        for facet_result in facet_results
    ]
    chart_warnings = _unique_warnings(
        warning
        for facet_result in facet_results
        for warning in facet_result.warnings
    )

    return ChartData(
        chart_id=chart_spec.chart_id,
        chart_title=chart_spec.chart_title,
        section_num=chart_spec.section.num,
        section_name=chart_spec.section.name,
        visual_type=chart_spec.visual_type,
        x_axis_field=_display_axis_field(chart_spec.axes.x),
        series_field=_display_axis_field(chart_spec.axes.series),
        y_axis_fields=_display_y_axis_fields(chart_spec),
        left_y_axis_fields=_display_metric_fields(chart_spec, chart_spec.axes.left_y),
        right_y_axis_fields=_display_metric_fields(chart_spec, chart_spec.axes.right_y),
        category_in_chart=_chart_category_data(chart_spec),
        auto_filtered_fields=tab_filter_result.auto_filtered_fields,
        facets=facets,
        warnings=chart_warnings,
    )


def _assemble_facet_data(
    chart_spec: ChartSpec,
    facet_result: FacetCalcResult,
) -> dict[str, Any]:
    df = _add_category_encoding(facet_result.df, chart_spec, facet_result.warnings)
    series = _records_for_series(df, chart_spec)
    return {
        "label": facet_result.label,
        "filters": facet_result.filters,
        "series": series,
        "calc_result": _calc_result(df, chart_spec),
        "warnings": _unique_warnings(facet_result.warnings),
        "formula_log": facet_result.formula_log,
    }


def _display_y_axis_fields(chart_spec: ChartSpec) -> list[str]:
    return _display_metric_fields(chart_spec, chart_spec.axes.y)


def _display_axis_field(field: str | None) -> str | None:
    if field is None:
        return None

    normalized = str(field).strip().lower().replace("-", "_").replace(" ", "_")
    return _AXIS_FIELD_ALIASES.get(normalized, field)


def _display_metric_fields(chart_spec: ChartSpec, metrics: list[str]) -> list[str]:
    if (
        chart_spec.visual_type
        in {"bar_chart", "line_bar", "grouped_line_bar", "line_bar_scatter_switch"}
        and chart_spec.calculation.operation == "growth_rate"
    ):
        return [f"{metric}_growth_rate" for metric in metrics]
    return list(metrics)


def _records_for_series(
    df: pd.DataFrame,
    chart_spec: ChartSpec,
) -> list[dict[str, Any]]:
    if df.empty:
        return []

    preferred_columns = _preferred_series_columns(df, chart_spec)
    return _json_records(df[preferred_columns])


def _preferred_series_columns(df: pd.DataFrame, chart_spec: ChartSpec) -> list[str]:
    preferred = []
    metrics = chart_metrics_for_calculation(chart_spec)
    for column in (
        "time",
        "activity_group",
        chart_spec.axes.x,
        chart_spec.axes.series,
        *metrics,
        CATEGORY_LABEL_COLUMN,
        CATEGORY_METRIC_COLUMN,
        CATEGORY_RANK_COLUMN,
        "growth_rate",
        *(f"{metric}_current" for metric in metrics),
        *(f"{metric}_prior" for metric in metrics),
        *(f"{metric}_growth_rate" for metric in metrics),
    ):
        if column is not None and column in df.columns and column not in preferred:
            preferred.append(column)

    if preferred:
        return preferred
    return list(df.columns)


def _calc_result(
    df: pd.DataFrame,
    chart_spec: ChartSpec,
) -> dict[str, Any]:
    if df.empty:
        return {}

    metrics = chart_metrics_for_calculation(chart_spec)
    value_columns = [
        column
        for column in (
            *metrics,
            CATEGORY_LABEL_COLUMN,
            CATEGORY_METRIC_COLUMN,
            CATEGORY_RANK_COLUMN,
            "growth_rate",
            *(f"{metric}_current" for metric in metrics),
            *(f"{metric}_prior" for metric in metrics),
            *(f"{metric}_growth_rate" for metric in metrics),
        )
        if column in df.columns
    ]
    if chart_spec.data_level == "portfolio":
        return _json_record(df[value_columns].iloc[0].to_dict())

    return {"rows": _json_records(df[_preferred_series_columns(df, chart_spec)])}


def _chart_category_data(chart_spec: ChartSpec) -> dict[str, Any] | None:
    category_spec = chart_spec.category_in_chart
    if category_spec is None:
        return None

    return {
        "metric": category_spec.metric,
        "method": category_spec.method,
        "direction": category_spec.direction,
        "labels": list(category_spec.labels),
        "label_field": CATEGORY_LABEL_COLUMN,
        "metric_field": CATEGORY_METRIC_COLUMN,
    }


def _add_category_encoding(
    df: pd.DataFrame,
    chart_spec: ChartSpec,
    warnings: list[str],
) -> pd.DataFrame:
    category_spec = chart_spec.category_in_chart
    if category_spec is None or df.empty:
        return df.copy()

    result = df.copy()
    metric_column = _category_metric_column(result, chart_spec)
    if metric_column is None:
        warnings.append(
            f"category_in_chart: metric {category_spec.metric} is not available"
        )
        return result

    result[CATEGORY_METRIC_COLUMN] = metric_column
    result[CATEGORY_LABEL_COLUMN] = None
    result[CATEGORY_RANK_COLUMN] = None

    if category_spec.method == "threshold" and category_spec.thresholds:
        return _apply_threshold_categories(result, chart_spec, metric_column)

    return _apply_quantile_categories(result, chart_spec, metric_column)


def _category_metric_column(df: pd.DataFrame, chart_spec: ChartSpec) -> str | None:
    metric = chart_spec.category_in_chart.metric if chart_spec.category_in_chart else None
    if metric is None:
        return None

    candidates = [metric, f"{metric}_growth_rate"]
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


def _apply_quantile_categories(
    df: pd.DataFrame,
    chart_spec: ChartSpec,
    metric_column: str,
) -> pd.DataFrame:
    category_spec = chart_spec.category_in_chart
    if category_spec is None:
        return df

    labels = list(category_spec.labels)
    numeric_values = pd.to_numeric(df[metric_column], errors="coerce")
    valid_values = numeric_values.dropna()
    if valid_values.empty:
        return df

    sorted_values = valid_values.sort_values(
        ascending=category_spec.direction == "asc",
        kind="mergesort",
    )
    denominator = len(sorted_values)
    bucket_count = len(labels)
    for rank, index in enumerate(sorted_values.index):
        bucket_index = min((rank * bucket_count) // denominator, bucket_count - 1)
        df.at[index, CATEGORY_LABEL_COLUMN] = labels[bucket_index]
        df.at[index, CATEGORY_RANK_COLUMN] = bucket_index

    return df


def _apply_threshold_categories(
    df: pd.DataFrame,
    chart_spec: ChartSpec,
    metric_column: str,
) -> pd.DataFrame:
    category_spec = chart_spec.category_in_chart
    if category_spec is None:
        return df

    numeric_values = pd.to_numeric(df[metric_column], errors="coerce")
    for index, value in numeric_values.items():
        if pd.isna(value):
            continue
        for rank, threshold in enumerate(category_spec.thresholds):
            if _value_matches_threshold(float(value), threshold):
                df.at[index, CATEGORY_LABEL_COLUMN] = threshold.label
                df.at[index, CATEGORY_RANK_COLUMN] = rank
                break
    return df


def _value_matches_threshold(value: float, threshold: Any) -> bool:
    if threshold.min_value is not None:
        if threshold.include_min:
            if value < threshold.min_value:
                return False
        elif value <= threshold.min_value:
            return False

    if threshold.max_value is not None:
        if threshold.include_max:
            if value > threshold.max_value:
                return False
        elif value >= threshold.max_value:
            return False

    return True
def _json_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [_json_record(record) for record in df.to_dict("records")]


def _json_record(record: Mapping[str, Any]) -> dict[str, Any]:
    clean_record: dict[str, Any] = {}
    for key, value in record.items():
        clean_record[str(key)] = _json_value(value)
    return clean_record


def _json_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _unique_warnings(warnings: Any) -> list[str]:
    unique: list[str] = []
    for warning in warnings:
        if warning not in unique:
            unique.append(warning)
    return unique
