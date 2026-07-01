"""Core data contracts for the dashboard pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Source = Literal["bi", "br", "total"]
Metric = Literal["roi", "spend", "response", "cpm", "activity"]
VisualType = Literal[
    "cards",
    "bar_chart",
    "line_bar",
    "grouped_line_bar",
    "line_bar_scatter_switch",
]
DataLevel = Literal["portfolio", "tactic"]
TimeScope = Literal["snapshot", "trend"]
SortField = Literal[
    "roi",
    "spend",
    "response",
    "cpm",
    "activity",
    "roi_change",
    "spend_change",
    "response_change",
    "cpm_change",
    "activity_change",
    "period",
]
SortDirection = Literal["asc", "desc"]
CategoryMethod = Literal["quantile", "threshold"]
CalculationOperation = Literal["weighted_roi_by_spend", "growth_rate"]
FilterOperation = Literal[
    "eq",
    "in",
    "not_in",
    "gte",
    "lte",
    "is_blank",
    "is_not_blank",
]
AggregateFieldBehavior = Literal["auto_filter", "single_select_only"]
NonAggregateBehavior = Literal["multi_select"]
ValidationStatus = Literal["ok", "warning", "error"]
PeriodGranularity = Literal["year", "half_year", "quarter", "month"]


class StrictModel(BaseModel):
    """Base model that rejects fields outside the declared schema."""

    model_config = ConfigDict(extra="forbid")


class RawChartRow(StrictModel):
    columns: dict[str, str | None]
    row_hash: str = Field(min_length=1)


class CompileRequest(StrictModel):
    grid_path: str


class PageRef(StrictModel):
    num: int
    name: str


class TabRef(StrictModel):
    num: str
    name: str


class SectionRef(StrictModel):
    num: str
    name: str


class SortingSpec(StrictModel):
    field: SortField
    direction: SortDirection


class CalculationSpec(StrictModel):
    operation: CalculationOperation
    also_compute: list[CalculationOperation] = Field(default_factory=list)


class CategoryThresholdSpec(StrictModel):
    label: str = Field(min_length=1)
    min_value: float | None = None
    max_value: float | None = None
    include_min: bool = True
    include_max: bool = False


class CategoryInChartSpec(StrictModel):
    metric: Metric
    method: CategoryMethod = "quantile"
    direction: SortDirection = "desc"
    labels: list[str] = Field(min_length=1)
    thresholds: list[CategoryThresholdSpec] = Field(default_factory=list)


class FacetSpec(StrictModel):
    enabled: bool
    source_fields: Literal["dropdown_outcome_fields"]


class AxesSpec(StrictModel):
    x: str | None
    y: list[Metric] = Field(default_factory=list)
    left_y: list[Metric] = Field(default_factory=list)
    right_y: list[Metric] = Field(default_factory=list)
    series: str | None = None


class ChartSpec(StrictModel):
    chart_id: str = Field(min_length=1)
    chart_description: str
    chart_title: str = ""
    page: PageRef
    tab: TabRef
    section: SectionRef
    source: Source
    metrics: list[Metric] = Field(min_length=1)
    visual_type: VisualType
    data_level: DataLevel
    sorting: SortingSpec | None = None
    calculation: CalculationSpec
    category_in_chart: CategoryInChartSpec | None = None
    facet: FacetSpec
    axes: AxesSpec
    time_scope: TimeScope
    narrative_instruction: str
    validation_warnings: list[str] = Field(default_factory=list)

    @field_validator("metrics")
    @classmethod
    def metrics_must_be_unique(cls, metrics: list[Metric]) -> list[Metric]:
        if len(metrics) != len(set(metrics)):
            raise ValueError("metrics must be unique")
        return metrics

    @model_validator(mode="after")
    def axes_must_have_display_metrics(self) -> "ChartSpec":
        axis_metrics = _unique_metrics(
            [*self.axes.y, *self.axes.left_y, *self.axes.right_y]
        )
        if not axis_metrics:
            axis_metrics = list(self.metrics)

        if not axis_metrics:
            raise ValueError("axes must include at least one y metric")

        if axis_metrics != self.axes.y:
            self.axes = self.axes.model_copy(update={"y": axis_metrics})
        return self


def _unique_metrics(metrics: list[Metric]) -> list[Metric]:
    unique: list[Metric] = []
    for metric in metrics:
        if metric not in unique:
            unique.append(metric)
    return unique


class FilterCondition(StrictModel):
    field: str = Field(min_length=1)
    op: FilterOperation
    value: str | int | float | bool | None = None
    values: list[str | int | float | bool | None] | None = None


class SnapshotTimeConfig(StrictModel):
    default_current_period: Literal["most_recent_period"]
    default_prior_period: Literal["same_period_previous_year"]
    min_periods_required: int = Field(ge=1)


class TrendTimeConfig(StrictModel):
    default_start_period: Literal["earliest_period_on_file"]
    default_end_period: Literal["latest_period_on_file"]
    min_periods_required: int = Field(ge=1)


class TabTimeConfig(StrictModel):
    snapshot: SnapshotTimeConfig
    trend: TrendTimeConfig


class TabSpec(StrictModel):
    tab_num: str
    tab_name: str
    tactic_filter: list[FilterCondition]
    aggregate_field_behavior: AggregateFieldBehavior
    non_aggregate_behavior: NonAggregateBehavior
    max_multiselect_fields: int = Field(ge=1)
    max_combination_product: int = Field(ge=1)
    time_config: TabTimeConfig


class ValidationChartReport(StrictModel):
    chart_id: str
    status: ValidationStatus
    messages: list[str] = Field(default_factory=list)


class ValidationReport(StrictModel):
    compiled_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    total: int = Field(ge=0)
    ok: int = Field(ge=0)
    warning: int = Field(ge=0)
    error: int = Field(ge=0)
    charts: list[ValidationChartReport] = Field(default_factory=list)


class CompileResponse(StrictModel):
    chart_specs: list[ChartSpec]
    validation_report: ValidationReport
    recompiled_ids: list[str]
    cached_ids: list[str]


class DashboardTab(StrictModel):
    tab_num: str
    tab_name: str


class PeriodDefault(StrictModel):
    snapshot_current_period: str
    snapshot_prior_period: str
    trend_start_period: str
    trend_end_period: str


class DropdownDefaultState(StrictModel):
    outcome_fields: dict[str, list[str]]
    metric: str
    period_granularity: PeriodGranularity
    snapshot_current_period: str
    snapshot_prior_period: str
    trend_start_period: str
    trend_end_period: str


class MetricFormatRule(StrictModel):
    unit_sign: str = ""
    keep_digit: int = Field(ge=0)


class DashboardConfigResponse(StrictModel):
    tabs: list[DashboardTab]
    outcome_field_options: dict[str, list[str]]
    outcome_field_labels: dict[str, str] = Field(default_factory=dict)
    outcome_field_combinations_by_tab: dict[str, list[dict[str, str]]] = Field(
        default_factory=dict
    )
    metric_format_config: dict[str, MetricFormatRule] = Field(default_factory=dict)
    metric_options: list[str]
    period_options: dict[PeriodGranularity, list[str]]
    period_defaults: dict[PeriodGranularity, PeriodDefault]
    default_dropdown_state: DropdownDefaultState


class TabRequest(StrictModel):
    dropdown_state: dict[str, Any]


@dataclass(slots=True)
class FacetSlice:
    label: str
    filters: dict[str, str]
    df: pd.DataFrame


@dataclass(slots=True)
class TabFilterResult:
    shared_df: pd.DataFrame
    facet_slices: list[FacetSlice]
    auto_filtered_fields: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FacetCalcResult:
    label: str
    filters: dict[str, str]
    df: pd.DataFrame
    formula_log: str
    warnings: list[str] = field(default_factory=list)


class FacetData(StrictModel):
    label: str
    filters: dict[str, str]
    series: list[dict[str, Any]]
    calc_result: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    formula_log: str = ""


class ChartCategoryData(StrictModel):
    metric: str
    method: CategoryMethod
    direction: SortDirection
    labels: list[str] = Field(default_factory=list)
    label_field: str = "category_label"
    metric_field: str = "category_metric"


class ChartData(StrictModel):
    chart_id: str
    chart_title: str = ""
    section_num: str = ""
    section_name: str = ""
    visual_type: VisualType
    x_axis_field: str | None
    series_field: str | None = None
    y_axis_fields: list[str]
    left_y_axis_fields: list[str] = Field(default_factory=list)
    right_y_axis_fields: list[str] = Field(default_factory=list)
    category_in_chart: ChartCategoryData | None = None
    auto_filtered_fields: list[str]
    facets: list[FacetData]
    warnings: list[str] = Field(default_factory=list)


class TabResponse(StrictModel):
    tab_num: str
    auto_filtered_fields: list[str]
    available_outcome_field_options: dict[str, list[str]] = Field(default_factory=dict)
    normalized_dropdown_state: dict[str, Any] = Field(default_factory=dict)
    charts: list[ChartData]


class NarrativeFacetInput(StrictModel):
    label: str
    calc_result: dict[str, Any]
    series: list[dict[str, Any]] = Field(default_factory=list)
    formula_log: str = ""


class NarrativeRequest(StrictModel):
    facets: list[NarrativeFacetInput]


class DataReference(StrictModel):
    facet: str
    metric: str
    value: Any


class NarrativeResponse(StrictModel):
    narrative: str
    data_references: list[DataReference] = Field(default_factory=list)
