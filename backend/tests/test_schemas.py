from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from backend.app.schemas import (
    ChartData,
    ChartSpec,
    FacetCalcResult,
    FacetSlice,
    RawChartRow,
    TabFilterResult,
    TabSpec,
    ValidationReport,
)


class SchemaTests(unittest.TestCase):
    def test_raw_chart_row_preserves_raw_columns(self) -> None:
        row = RawChartRow(
            columns={
                "Chart Item Num": "1.1.1.1",
                "Calculation": None,
            },
            row_hash="abc123",
        )

        self.assertIsNone(row.columns["Calculation"])
        self.assertEqual(row.row_hash, "abc123")

    def test_chart_spec_accepts_required_schema(self) -> None:
        chart = ChartSpec(
            chart_id="1.1.1.1",
            chart_description="Aggregated Marketing ROI Snapshot at Portfolio Level",
            page={"num": 1, "name": "ROI / Efficiency"},
            tab={"num": "1.1", "name": "Portfolio Overview"},
            section={
                "num": "1.1.1",
                "name": "Aggregated Marketing ROI at Overall Portfolio level",
            },
            source="bi",
            metrics=["roi", "spend"],
            visual_type="cards",
            data_level="portfolio",
            sorting={"field": "roi", "direction": "desc"},
            calculation={
                "operation": "weighted_roi_by_spend",
                "also_compute": ["growth_rate"],
            },
            facet={"enabled": True, "source_fields": "dropdown_outcome_fields"},
            axes={"x": None, "y": ["roi", "spend"]},
            time_scope="snapshot",
            narrative_instruction=(
                "Should conduct cross-level comparison for both most recent period "
                "and growth rate."
            ),
            validation_warnings=[],
        )

        self.assertEqual(chart.source, "bi")
        self.assertEqual(chart.chart_title, "")
        self.assertEqual(chart.axes.x, None)
        self.assertEqual(chart.calculation.also_compute, ["growth_rate"])

    def test_chart_spec_rejects_unknown_metric(self) -> None:
        payload = {
            "chart_id": "1.1.1.1",
            "chart_description": "Invalid metric example",
            "page": {"num": 1, "name": "ROI / Efficiency"},
            "tab": {"num": "1.1", "name": "Portfolio Overview"},
            "section": {"num": "1.1.1", "name": "Section"},
            "source": "bi",
            "metrics": ["clicks"],
            "visual_type": "cards",
            "data_level": "portfolio",
            "calculation": {"operation": "weighted_roi_by_spend"},
            "facet": {"enabled": True, "source_fields": "dropdown_outcome_fields"},
            "axes": {"x": None, "y": ["roi"]},
            "time_scope": "snapshot",
            "narrative_instruction": "",
        }

        with self.assertRaises(ValidationError):
            ChartSpec(**payload)

    def test_chart_spec_accepts_bar_chart_visual_type(self) -> None:
        chart = ChartSpec(
            chart_id="1.1.2.2",
            chart_description="Marketing Tactics ROI drivers",
            page={"num": 1, "name": "ROI / Efficiency"},
            tab={"num": "1.1", "name": "Portfolio Overview"},
            section={"num": "1.1.2", "name": "Marketing Tactics ROI"},
            source="bi",
            metrics=["roi", "response", "cpm"],
            visual_type="bar_chart",
            data_level="tactic",
            sorting={"field": "roi", "direction": "desc"},
            calculation={"operation": "weighted_roi_by_spend", "also_compute": []},
            facet={"enabled": True, "source_fields": "dropdown_outcome_fields"},
            axes={
                "x": "activity_group",
                "y": ["roi", "response", "cpm"],
                "left_y": ["roi", "cpm"],
                "right_y": ["response"],
            },
            time_scope="snapshot",
            narrative_instruction="",
            validation_warnings=[],
        )

        self.assertEqual(chart.visual_type, "bar_chart")
        self.assertEqual(chart.axes.x, "activity_group")
        self.assertEqual(chart.axes.left_y, ["roi", "cpm"])
        self.assertEqual(chart.axes.right_y, ["response"])

    def test_chart_spec_accepts_grouped_line_bar_series_axis(self) -> None:
        chart = ChartSpec(
            chart_id="1.1.2.4",
            chart_description="Marketing Tactics ROI trend",
            page={"num": 1, "name": "ROI / Efficiency"},
            tab={"num": "1.1", "name": "Portfolio Overview"},
            section={"num": "1.1.2", "name": "Marketing Tactics ROI"},
            source="bi",
            metrics=["roi", "spend"],
            visual_type="grouped_line_bar",
            data_level="tactic",
            sorting={"field": "roi", "direction": "desc"},
            calculation={"operation": "weighted_roi_by_spend", "also_compute": []},
            facet={"enabled": True, "source_fields": "dropdown_outcome_fields"},
            axes={
                "x": "activity_group",
                "series": "time",
                "y": ["roi", "spend"],
                "left_y": ["spend"],
                "right_y": ["roi"],
            },
            time_scope="trend",
            narrative_instruction="",
            validation_warnings=[],
        )

        self.assertEqual(chart.visual_type, "grouped_line_bar")
        self.assertEqual(chart.axes.x, "activity_group")
        self.assertEqual(chart.axes.series, "time")
        self.assertEqual(chart.axes.left_y, ["spend"])
        self.assertEqual(chart.axes.right_y, ["roi"])

    def test_chart_spec_backfills_empty_axes_y_from_axis_sides(self) -> None:
        chart = ChartSpec(
            chart_id="1.1.2.2",
            chart_description="Marketing Tactics ROI drivers",
            page={"num": 1, "name": "ROI / Efficiency"},
            tab={"num": "1.1", "name": "Portfolio Overview"},
            section={"num": "1.1.2", "name": "Marketing Tactics ROI"},
            source="bi",
            metrics=["roi", "response", "cpm"],
            visual_type="bar_chart",
            data_level="tactic",
            sorting={"field": "roi", "direction": "desc"},
            calculation={"operation": "weighted_roi_by_spend", "also_compute": []},
            facet={"enabled": True, "source_fields": "dropdown_outcome_fields"},
            axes={
                "x": "activity_group",
                "y": [],
                "left_y": ["roi", "cpm"],
                "right_y": ["response"],
            },
            time_scope="snapshot",
            narrative_instruction="",
            validation_warnings=[],
        )

        self.assertEqual(chart.axes.y, ["roi", "cpm", "response"])

    def test_tab_spec_matches_required_time_config_shape(self) -> None:
        tab = TabSpec(
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
        )

        self.assertEqual(tab.tactic_filter[0].field, "measure_group")
        self.assertEqual(tab.time_config.trend.min_periods_required, 3)

    def test_validation_report_counts_and_statuses(self) -> None:
        report = ValidationReport(
            total=2,
            ok=1,
            warning=1,
            error=0,
            charts=[
                {"chart_id": "1.1.1.1", "status": "ok", "messages": []},
                {
                    "chart_id": "1.1.1.2",
                    "status": "warning",
                    "messages": ["calculation requires later validation"],
                },
            ],
        )

        self.assertEqual(report.total, 2)
        self.assertEqual(report.charts[1].status, "warning")

    def test_dataframe_carrier_dataclasses_keep_frames(self) -> None:
        df = pd.DataFrame([{"country": "uk", "roi": 1.2}])
        facet = FacetSlice(label="uk", filters={"country": "uk"}, df=df)
        tab_result = TabFilterResult(shared_df=df, facet_slices=[facet])
        calc_result = FacetCalcResult(
            label="uk",
            filters={"country": "uk"},
            df=df,
            formula_log="weighted_roi_by_spend",
        )

        self.assertTrue(tab_result.shared_df.equals(df))
        self.assertEqual(tab_result.facet_slices[0].label, "uk")
        self.assertEqual(calc_result.formula_log, "weighted_roi_by_spend")

    def test_chart_data_schema_matches_frontend_contract(self) -> None:
        chart_data = ChartData(
            chart_id="1.1.1.1",
            chart_title="Portfolio ROI Snapshot",
            visual_type="cards",
            x_axis_field=None,
            series_field=None,
            y_axis_fields=["roi", "spend"],
            auto_filtered_fields=["kpi"],
            facets=[
                {
                    "label": "uk",
                    "filters": {"country": "uk"},
                    "series": [{"roi": 1.2, "spend": 500000}],
                    "calc_result": {"roi": 1.2, "spend": 500000},
                }
            ],
        )

        self.assertEqual(chart_data.facets[0].filters["country"], "uk")
        self.assertEqual(chart_data.chart_title, "Portfolio ROI Snapshot")
        self.assertEqual(chart_data.auto_filtered_fields, ["kpi"])

    def test_chart_data_accepts_derived_display_fields(self) -> None:
        chart_data = ChartData(
            chart_id="1.1.2.3",
            visual_type="line_bar_scatter_switch",
            x_axis_field="activity_group",
            y_axis_fields=["roi_growth_rate", "spend_growth_rate"],
            left_y_axis_fields=["roi_growth_rate"],
            right_y_axis_fields=["spend_growth_rate"],
            auto_filtered_fields=[],
            facets=[
                {
                    "label": "uk",
                    "filters": {"country": "uk"},
                    "series": [
                        {
                            "activity_group": "audio",
                            "roi_growth_rate": 0.4,
                            "spend_growth_rate": -0.2,
                        }
                    ],
                    "calc_result": {},
                }
            ],
        )

        self.assertEqual(
            chart_data.y_axis_fields,
            ["roi_growth_rate", "spend_growth_rate"],
        )
        self.assertEqual(chart_data.left_y_axis_fields, ["roi_growth_rate"])

    def test_frontend_type_contracts_are_present(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        types_source = (repo_root / "frontend" / "src" / "types.ts").read_text(
            encoding="utf-8",
        )

        for expected in (
            "export interface FacetData",
            "export interface ChartData",
            "export interface TabCacheEntry",
            "chart_title?: string;",
            "calc_result: Record<string, unknown>;",
            "series_field?: string | null;",
            "series: Record<string, unknown>[];",
            "chartData: ChartData[];",
            "dropdownState: DropdownState;",
            "availableOutcomeFieldOptions: Record<string, string[]>;",
            "outcomeFieldCombinationsByTab: Record<string, Array<Record<string, string>>>;",
            "metricFormatConfig: MetricFormatConfig;",
            "available_outcome_field_options?: Record<string, string[]>;",
            "normalized_dropdown_state?: DropdownState;",
        ):
            self.assertIn(expected, types_source)


if __name__ == "__main__":
    unittest.main()
