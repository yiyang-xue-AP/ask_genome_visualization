"""Hardcoded tab-level rules from the dashboard requirements."""

from backend.app.schemas import TabSpec

AGGREGATE_VALUES = ["overall", "portfolio", "blank"]

TAB_CONFIGS: dict[str, TabSpec] = {
    "1.1": TabSpec(
        tab_num="1.1",
        tab_name="Portfolio Overview",
        tactic_filter=[
            {"field": "measure_group", "op": "is_blank"},
            {"field": "measure", "op": "is_blank"},
        ],
        aggregate_field_behavior="auto_filter",
        non_aggregate_behavior="multi_select",
        max_multiselect_fields=2,
        max_combination_product=6,
        time_config={
            "snapshot": {
                "default_current_period": "most_recent_period",
                "default_prior_period": "same_period_previous_year",
                "min_periods_required": 2,
            },
            "trend": {
                "default_start_period": "earliest_period_on_file",
                "default_end_period": "latest_period_on_file",
                "min_periods_required": 3,
            },
        },
    ),
    "1.2": TabSpec(
        tab_num="1.2",
        tab_name="Level Focused Views",
        tactic_filter=[
            {"field": "measure_group", "op": "is_blank"},
            {"field": "measure", "op": "is_blank"},
        ],
        aggregate_field_behavior="single_select_only",
        non_aggregate_behavior="multi_select",
        max_multiselect_fields=2,
        max_combination_product=6,
        time_config={
            "snapshot": {
                "default_current_period": "most_recent_period",
                "default_prior_period": "same_period_previous_year",
                "min_periods_required": 2,
            },
            "trend": {
                "default_start_period": "earliest_period_on_file",
                "default_end_period": "latest_period_on_file",
                "min_periods_required": 3,
            },
        },
    ),
}
