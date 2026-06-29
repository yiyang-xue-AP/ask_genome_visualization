"""Deterministic tab-level filtering and facet splitting."""

from __future__ import annotations

from copy import deepcopy
from itertools import product as cartesian_product
from typing import Any

import pandas as pd

from backend.app.schemas import FacetSlice, FilterCondition, TabFilterResult, TabSpec
from backend.app.tab_configs import AGGREGATE_VALUES

BLANK_AGGREGATE_TOKEN = "blank"
TEXT_AGGREGATE_VALUES = {
    value for value in AGGREGATE_VALUES if value != BLANK_AGGREGATE_TOKEN
}
AGGREGATE_ORDER = {
    value: index for index, value in enumerate(AGGREGATE_VALUES)
}


def get_outcome_fields(df: pd.DataFrame) -> list[str]:
    """Return all columns before activity_group."""

    columns = list(df.columns)
    if "activity_group" not in columns:
        raise ValueError("DataFrame must contain an activity_group column")

    activity_group_index = columns.index("activity_group")
    return columns[:activity_group_index]


def filter_tab(
    tab_spec: TabSpec,
    dropdown_state: dict[str, Any],
    df: pd.DataFrame,
) -> TabFilterResult:
    """Apply tab-level tactic filters, aggregate handling, and facet splitting."""

    outcome_fields = get_outcome_fields(df)
    filtered_df = df.copy()

    for condition in tab_spec.tactic_filter:
        filtered_df = _apply_filter_condition(filtered_df, condition)

    auto_filtered_fields: list[str] = []
    facet_fields: dict[str, list[Any]] = {}

    for field in outcome_fields:
        selected = _selected_values(dropdown_state, field)
        field_has_aggregate = _field_has_aggregate_values(filtered_df[field])

        if tab_spec.aggregate_field_behavior == "auto_filter" and field_has_aggregate:
            filtered_df = _filter_to_aggregate_values(filtered_df, field)
            auto_filtered_fields.append(field)
            continue

        if tab_spec.aggregate_field_behavior == "single_select_only":
            _validate_aggregate_single_select(field, selected)

        if selected:
            facet_fields[field] = selected

    _validate_facet_limits(tab_spec, facet_fields)
    facet_slices = _build_facet_slices(filtered_df, facet_fields)

    return TabFilterResult(
        shared_df=filtered_df,
        facet_slices=facet_slices,
        auto_filtered_fields=auto_filtered_fields,
    )


def normalize_dropdown_state(
    tab_spec: TabSpec,
    dropdown_state: dict[str, Any],
    df: pd.DataFrame,
) -> dict[str, Any]:
    """Drop invalid outcome selections according to real data combinations."""

    outcome_fields = get_outcome_fields(df)
    base_df, auto_filtered_fields = _base_dropdown_df(tab_spec, df, outcome_fields)
    visible_fields = [
        field for field in outcome_fields if field not in auto_filtered_fields
    ]

    normalized_state = deepcopy(dropdown_state)
    normalized_outcomes: dict[str, list[str]] = {}
    selected_outcomes = dropdown_state.get("outcome_fields")
    if not isinstance(selected_outcomes, dict):
        selected_outcomes = {}

    for field in auto_filtered_fields:
        selected = _selected_values({"outcome_fields": selected_outcomes}, field)
        selected = [_facet_label(value) for value in selected]
        available = {
            option_label(value)
            for value in base_df[field].drop_duplicates()
        }
        retained = [value for value in selected if value in available]
        if retained:
            normalized_outcomes[field] = retained

    for field in visible_fields:
        selected = _selected_values({"outcome_fields": selected_outcomes}, field)
        selected = [_facet_label(value) for value in selected]
        selected = _normalize_aggregate_selection(tab_spec, selected)

        option_df = _filter_df_by_selections(base_df, normalized_outcomes)
        available = {
            option_label(value)
            for value in option_df[field].drop_duplicates()
        }
        retained = [value for value in selected if value in available]
        if retained:
            normalized_outcomes[field] = retained

    normalized_state["outcome_fields"] = normalized_outcomes
    return normalized_state


def build_available_outcome_field_options(
    tab_spec: TabSpec,
    dropdown_state: dict[str, Any],
    df: pd.DataFrame,
) -> dict[str, list[str]]:
    """Return option values that can produce data under the current selections."""

    outcome_fields = get_outcome_fields(df)
    base_df, _auto_filtered_fields = _base_dropdown_df(tab_spec, df, outcome_fields)
    selected_outcomes = dropdown_state.get("outcome_fields")
    if not isinstance(selected_outcomes, dict):
        selected_outcomes = {}

    options: dict[str, list[str]] = {}
    for field in outcome_fields:
        option_df = _filter_df_by_selections(
            base_df,
            selected_outcomes,
            exclude_field=field,
        )
        labels = [option_label(value) for value in option_df[field].drop_duplicates()]
        unique_labels = sorted(set(labels), key=option_sort_key)
        if unique_labels:
            options[field] = unique_labels
        else:
            options[field] = []
    return options


def build_outcome_field_combinations(
    tab_spec: TabSpec,
    df: pd.DataFrame,
) -> list[dict[str, str]]:
    """Return real outcome-field combinations after tab-level base filtering."""

    outcome_fields = get_outcome_fields(df)
    base_df, _auto_filtered_fields = _base_dropdown_df(
        tab_spec,
        df,
        outcome_fields,
        strict_filters=False,
    )
    if base_df.empty:
        return []

    combo_df = base_df[outcome_fields].drop_duplicates()
    records = [
        {
            field: option_label(record[field])
            for field in outcome_fields
        }
        for record in combo_df.to_dict("records")
    ]
    records.sort(
        key=lambda record: tuple(
            option_sort_key(record[field])
            for field in outcome_fields
        )
    )
    return records


def _apply_filter_condition(df: pd.DataFrame, condition: FilterCondition) -> pd.DataFrame:
    if condition.field not in df.columns:
        raise ValueError(f"Filter field {condition.field!r} is not present in DataFrame")

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
        raise ValueError(f"Unsupported filter operation: {condition.op}")

    return df[mask].copy()


def _selected_values(dropdown_state: dict[str, Any], field: str) -> list[Any]:
    outcome_state = dropdown_state.get("outcome_fields")
    if isinstance(outcome_state, dict) and field in outcome_state:
        raw_value = outcome_state[field]
    else:
        raw_value = dropdown_state.get(field, [])

    if raw_value is None or raw_value == "":
        return []
    if isinstance(raw_value, list):
        return [value for value in raw_value if value is not None and value != ""]
    if isinstance(raw_value, tuple):
        return [value for value in raw_value if value is not None and value != ""]
    return [raw_value]


def _field_has_aggregate_values(series: pd.Series) -> bool:
    return any(_is_aggregate_value(value) for value in series.drop_duplicates())


def _is_aggregate_value(value: Any) -> bool:
    if pd.isna(value) or value == "":
        return True
    if isinstance(value, str):
        return value.strip().lower() in TEXT_AGGREGATE_VALUES
    return False


def _filter_to_aggregate_values(df: pd.DataFrame, field: str) -> pd.DataFrame:
    mask = df[field].map(_is_aggregate_value)
    return df[mask].copy()


def _base_dropdown_df(
    tab_spec: TabSpec,
    df: pd.DataFrame,
    outcome_fields: list[str],
    strict_filters: bool = True,
) -> tuple[pd.DataFrame, list[str]]:
    filtered_df = df.copy()
    for condition in tab_spec.tactic_filter:
        if condition.field not in filtered_df.columns and not strict_filters:
            continue
        filtered_df = _apply_filter_condition(filtered_df, condition)

    auto_filtered_fields: list[str] = []
    if tab_spec.aggregate_field_behavior != "auto_filter":
        return filtered_df, auto_filtered_fields

    for field in outcome_fields:
        if _field_has_aggregate_values(filtered_df[field]):
            filtered_df = _filter_to_aggregate_values(filtered_df, field)
            auto_filtered_fields.append(field)
    return filtered_df, auto_filtered_fields


def _filter_df_by_selections(
    df: pd.DataFrame,
    selected_outcomes: dict[str, list[Any]],
    exclude_field: str | None = None,
) -> pd.DataFrame:
    filtered_df = df
    for field, selected_values in selected_outcomes.items():
        if field == exclude_field or field not in filtered_df.columns:
            continue
        values = [value for value in selected_values if value is not None and value != ""]
        if not values:
            continue
        masks = [_value_mask(filtered_df[field], value) for value in values]
        mask = pd.concat(masks, axis=1).any(axis=1)
        filtered_df = filtered_df[mask]
    return filtered_df


def _normalize_aggregate_selection(
    tab_spec: TabSpec,
    selected: list[str],
) -> list[str]:
    if tab_spec.aggregate_field_behavior != "single_select_only":
        return selected

    for value in selected:
        if _is_aggregate_selection(value):
            return [value]
    return selected


def _validate_aggregate_single_select(field: str, selected: list[Any]) -> None:
    if len(selected) <= 1:
        return
    if any(_is_aggregate_selection(value) for value in selected):
        raise ValueError(f"{field}: aggregate value must be single-select only")


def _is_aggregate_selection(value: Any) -> bool:
    if pd.isna(value) or value == "":
        return True
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in TEXT_AGGREGATE_VALUES or normalized == BLANK_AGGREGATE_TOKEN
    return False


def _validate_facet_limits(tab_spec: TabSpec, facet_fields: dict[str, list[Any]]) -> None:
    combination_product = 1
    for field, values in facet_fields.items():
        if len(values) > tab_spec.max_multiselect_fields:
            raise ValueError(
                f"{field}: too many selected values: {len(values)} exceeds "
                f"{tab_spec.max_multiselect_fields}"
            )
        combination_product *= len(values)
    if combination_product > tab_spec.max_combination_product:
        raise ValueError(
            f"Too many facet combinations: {combination_product} exceeds "
            f"{tab_spec.max_combination_product}"
        )


def _build_facet_slices(
    df: pd.DataFrame,
    facet_fields: dict[str, list[Any]],
) -> list[FacetSlice]:
    if not facet_fields:
        return [FacetSlice(label="all", filters={}, df=df.copy())]

    fields = list(facet_fields.keys())
    slices: list[FacetSlice] = []
    for combo in cartesian_product(*(facet_fields[field] for field in fields)):
        filters = dict(zip(fields, combo, strict=True))
        mask = _facet_mask(df, filters)
        slices.append(
            FacetSlice(
                label=" | ".join(_facet_label(value) for value in combo),
                filters={field: _facet_label(value) for field, value in filters.items()},
                df=df[mask].copy(),
            )
        )

    return slices


def _facet_mask(df: pd.DataFrame, filters: dict[str, Any]) -> pd.Series:
    masks = [_value_mask(df[field], value) for field, value in filters.items()]
    if not masks:
        return pd.Series(True, index=df.index)
    return pd.concat(masks, axis=1).all(axis=1)


def _value_mask(series: pd.Series, selected_value: Any) -> pd.Series:
    if isinstance(selected_value, str) and selected_value.strip().lower() == BLANK_AGGREGATE_TOKEN:
        return series.isna() | (series == "")
    return series == selected_value


def _facet_label(value: Any) -> str:
    if pd.isna(value) or value == "":
        return BLANK_AGGREGATE_TOKEN
    return str(value)


def option_label(value: Any) -> str:
    return _facet_label(value)


def option_sort_key(value: str) -> tuple[int, int, str]:
    normalized = value.strip().lower()
    if normalized in AGGREGATE_ORDER:
        return (0, AGGREGATE_ORDER[normalized], normalized)
    return (1, 0, normalized)
