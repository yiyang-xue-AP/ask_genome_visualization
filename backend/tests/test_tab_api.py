from __future__ import annotations

import unittest

import pandas as pd

from backend.app.schemas import (
    ChartSpec,
    FacetCalcResult,
    FacetSlice,
    TabFilterResult,
    TabRequest,
)
from backend.app.tab_pipeline import build_tab_response


def make_chart_spec(
    chart_id: str,
    tab_num: str = "1.1",
    data_level: str = "portfolio",
) -> ChartSpec:
    return ChartSpec(
        chart_id=chart_id,
        chart_description="Synthetic tab API chart",
        chart_title="Synthetic Chart Title",
        page={"num": 1, "name": "ROI / Efficiency"},
        tab={"num": tab_num, "name": "Portfolio Overview"},
        section={"num": "1.1.1", "name": "Synthetic section"},
        source="bi",
        metrics=["roi", "spend"],
        visual_type="cards",
        data_level=data_level,
        sorting=None,
        calculation={"operation": "weighted_roi_by_spend", "also_compute": []},
        facet={"enabled": True, "source_fields": "dropdown_outcome_fields"},
        axes={"x": None, "y": ["roi", "spend"]},
        time_scope="snapshot",
        narrative_instruction="",
        validation_warnings=[],
    )


def make_cache() -> dict[str, dict[str, object]]:
    return {
        "1.1.1.1": {"hash": "hash-1", "spec": make_chart_spec("1.1.1.1")},
        "1.1.1.2": {
            "hash": "hash-2",
            "spec": make_chart_spec("1.1.1.2", data_level="tactic"),
        },
        "1.2.1.1": {
            "hash": "hash-3",
            "spec": make_chart_spec("1.2.1.1", tab_num="1.2"),
        },
    }


def make_source_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "country": "uk",
                "kpi": "overall",
                "detailed_kpi": "overall",
                "business_unit_for_kpi": "APS",
                "activity_group": "paid search",
                "measure_group": "",
                "measure": "",
                "time": "Q1 2026",
                "roi": 1.2,
                "spend": 100.0,
            }
        ]
    )


def make_long_source_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "country": "uk",
                "kpi": "overall",
                "detailed_kpi": "overall",
                "business_unit_for_kpi": "APS",
                "activity_group": "paid search",
                "measure_group": "",
                "measure": "",
                "time": "Q1 2026",
                "metric": "gross portfolio roi",
                "value": 1.2,
            },
            {
                "country": "uk",
                "kpi": "overall",
                "detailed_kpi": "overall",
                "business_unit_for_kpi": "APS",
                "activity_group": "paid search",
                "measure_group": "",
                "measure": "",
                "time": "Q1 2026",
                "metric": "gross portfolio spend",
                "value": 100.0,
            },
        ]
    )


class TabApiTests(unittest.TestCase):
    def test_tab_response_selects_cached_specs_and_runs_filter_once_per_request(self) -> None:
        calls = {"filter": 0, "calculate": []}

        def fake_filter(tab_spec, dropdown_state, df):
            calls["filter"] += 1
            return TabFilterResult(
                shared_df=df,
                facet_slices=[
                    FacetSlice(
                        label="uk",
                        filters={"country": "uk"},
                        df=df,
                    )
                ],
                auto_filtered_fields=["kpi"],
            )

        def fake_calculate(chart_spec, tab_filter_result, dropdown_state):
            calls["calculate"].append(chart_spec.chart_id)
            if chart_spec.data_level == "portfolio":
                result_df = pd.DataFrame(
                    [{"roi": 1.2, "spend": 100.0, "growth_rate": 0.2}]
                )
            else:
                result_df = pd.DataFrame(
                    [
                        {
                            "activity_group": "paid search",
                            "roi": 1.2,
                            "spend": 100.0,
                        }
                    ]
                )
            return [
                FacetCalcResult(
                    label="uk",
                    filters={"country": "uk"},
                    df=result_df,
                    formula_log="weighted_roi_by_spend",
                    warnings=["synthetic warning"],
                )
            ]

        response = build_tab_response(
            "1.1",
            TabRequest(
                dropdown_state={
                    "outcome_fields": {"country": ["uk"]},
                    "snapshot_current_period": "Q1 2026",
                    "snapshot_prior_period": "Q1 2025",
                    "trend_start_period": "Q1 2025",
                    "trend_end_period": "Q3 2026",
                }
            ),
            cache=make_cache(),
            data_frames={"bi": make_source_df()},
            filter_fn=fake_filter,
            calculate_fn=fake_calculate,
        )

        self.assertEqual(response.tab_num, "1.1")
        self.assertEqual(response.auto_filtered_fields, ["kpi"])
        self.assertEqual(response.normalized_dropdown_state["outcome_fields"], {"country": ["uk"]})
        self.assertEqual(response.available_outcome_field_options["country"], ["uk"])
        self.assertEqual(response.available_outcome_field_options["kpi"], ["overall"])
        self.assertEqual(len(response.charts), 2)
        self.assertEqual(calls["filter"], 1)
        self.assertEqual(calls["calculate"], ["1.1.1.1", "1.1.1.2"])

    def test_tab_response_returns_normalized_dropdown_and_available_options(self) -> None:
        response = build_tab_response(
            "1.2",
            TabRequest(
                dropdown_state={
                    "outcome_fields": {"country": ["uk"], "kpi": ["overall", "conversions"]},
                    "snapshot_current_period": "Q1 2026",
                    "snapshot_prior_period": "Q1 2025",
                    "trend_start_period": "Q1 2025",
                    "trend_end_period": "Q3 2026",
                }
            ),
            cache=make_cache(),
            data_frames={"bi": make_source_df()},
        )

        self.assertEqual(
            response.normalized_dropdown_state["outcome_fields"],
            {"country": ["uk"], "kpi": ["overall"]},
        )
        self.assertEqual(response.available_outcome_field_options["country"], ["uk"])
        self.assertEqual(response.available_outcome_field_options["kpi"], ["overall"])

    def test_tab_response_prepares_long_metric_frame_once_per_request(self) -> None:
        seen_columns = []

        def fake_filter(tab_spec, dropdown_state, df):
            return TabFilterResult(
                shared_df=df,
                facet_slices=[
                    FacetSlice(label="uk", filters={"country": "uk"}, df=df)
                ],
                auto_filtered_fields=[],
            )

        def fake_calculate(chart_spec, tab_filter_result, dropdown_state):
            seen_columns.append(list(tab_filter_result.shared_df.columns))
            return [
                FacetCalcResult(
                    label="uk",
                    filters={"country": "uk"},
                    df=pd.DataFrame([{"roi": 1.2, "spend": 100.0}]),
                    formula_log="weighted_roi_by_spend",
                )
            ]

        response = build_tab_response(
            "1.1",
            TabRequest(dropdown_state={}),
            cache=make_cache(),
            data_frames={"bi": make_long_source_df()},
            filter_fn=fake_filter,
            calculate_fn=fake_calculate,
        )

        self.assertEqual(len(response.charts), 2)
        self.assertEqual(len(seen_columns), 2)
        for columns in seen_columns:
            self.assertIn("roi", columns)
            self.assertIn("spend", columns)
            self.assertNotIn("metric", columns)
            self.assertNotIn("value", columns)

    def test_tab_response_calculates_axes_y_metric_when_metrics_omits_it(self) -> None:
        chart_spec = make_chart_spec("1.1.1.1").model_copy(update={"metrics": ["roi"]})
        response = build_tab_response(
            "1.1",
            TabRequest(
                dropdown_state={
                    "outcome_fields": {"country": ["uk"]},
                    "snapshot_current_period": "Q1 2026",
                    "snapshot_prior_period": "Q1 2025",
                    "trend_start_period": "Q1 2025",
                    "trend_end_period": "Q3 2026",
                }
            ),
            cache={"1.1.1.1": {"hash": "hash-1", "spec": chart_spec}},
            data_frames={"bi": make_source_df()},
        )

        facet = response.charts[0].facets[0]
        self.assertEqual(response.charts[0].y_axis_fields, ["roi", "spend"])
        self.assertEqual(facet.calc_result["roi"], 1.2)
        self.assertEqual(facet.calc_result["spend"], 100.0)

    def test_tab_response_uses_growth_fields_for_growth_visuals(self) -> None:
        base_spec = make_chart_spec("1.1.2.3", data_level="tactic")
        chart_spec = base_spec.model_copy(
            update={
                "visual_type": "line_bar_scatter_switch",
                "calculation": base_spec.calculation.model_copy(
                    update={"operation": "growth_rate", "also_compute": []}
                ),
                "axes": base_spec.axes.model_copy(
                    update={"x": "activity_group", "y": ["roi", "spend"]}
                ),
            }
        )

        def fake_calculate(chart_spec, tab_filter_result, dropdown_state):
            return [
                FacetCalcResult(
                    label="uk",
                    filters={"country": "uk"},
                    df=pd.DataFrame(
                        [
                            {
                                "activity_group": "audio",
                                "roi": 2.1,
                                "spend": 100.0,
                                "roi_growth_rate": 0.4,
                                "spend_growth_rate": -0.2,
                            }
                        ]
                    ),
                    formula_log="growth_rate",
                )
            ]

        response = build_tab_response(
            "1.1",
            TabRequest(
                dropdown_state={
                    "outcome_fields": {"country": ["uk"]},
                    "snapshot_current_period": "Q1 2026",
                    "snapshot_prior_period": "Q1 2025",
                    "trend_start_period": "Q1 2025",
                    "trend_end_period": "Q3 2026",
                }
            ),
            cache={"1.1.2.3": {"hash": "hash-1", "spec": chart_spec}},
            data_frames={"bi": make_source_df()},
            calculate_fn=fake_calculate,
        )

        chart = response.charts[0]
        facet = chart.facets[0]

        self.assertEqual(chart.y_axis_fields, ["roi_growth_rate", "spend_growth_rate"])
        self.assertEqual(facet.series[0]["roi_growth_rate"], 0.4)
        self.assertEqual(facet.series[0]["spend_growth_rate"], -0.2)

    def test_tab_response_exposes_axis_side_fields(self) -> None:
        base_spec = make_chart_spec("1.1.2.2", data_level="tactic")
        chart_spec = base_spec.model_copy(
            update={
                "metrics": ["roi", "response", "cpm"],
                "visual_type": "bar_chart",
                "axes": base_spec.axes.model_copy(
                    update={
                        "x": "activity_group",
                        "y": ["roi", "response", "cpm"],
                        "left_y": ["roi", "cpm"],
                        "right_y": ["response"],
                    }
                ),
            }
        )

        def fake_calculate(chart_spec, tab_filter_result, dropdown_state):
            return [
                FacetCalcResult(
                    label="uk",
                    filters={"country": "uk"},
                    df=pd.DataFrame(
                        [
                            {
                                "activity_group": "audio",
                                "roi": 7.7,
                                "response": 142.0,
                                "cpm": 14.7,
                            }
                        ]
                    ),
                    formula_log="weighted_roi_by_spend",
                )
            ]

        response = build_tab_response(
            "1.1",
            TabRequest(dropdown_state={}),
            cache={"1.1.2.2": {"hash": "hash-1", "spec": chart_spec}},
            data_frames={"bi": make_source_df()},
            calculate_fn=fake_calculate,
        )

        chart = response.charts[0]
        self.assertEqual(chart.left_y_axis_fields, ["roi", "cpm"])
        self.assertEqual(chart.right_y_axis_fields, ["response"])

    def test_tab_response_exposes_grouped_series_field(self) -> None:
        base_spec = make_chart_spec("1.1.2.4", data_level="tactic")
        chart_spec = base_spec.model_copy(
            update={
                "visual_type": "grouped_line_bar",
                "time_scope": "trend",
                "axes": base_spec.axes.model_copy(
                    update={
                        "x": "activity_group",
                        "series": "time",
                        "y": ["roi", "spend"],
                        "left_y": ["spend"],
                        "right_y": ["roi"],
                    }
                ),
            }
        )

        def fake_calculate(chart_spec, tab_filter_result, dropdown_state):
            return [
                FacetCalcResult(
                    label="uk",
                    filters={"country": "uk"},
                    df=pd.DataFrame(
                        [
                            {
                                "time": "Q1 2026",
                                "activity_group": "audio",
                                "roi": 7.7,
                                "spend": 100.0,
                            }
                        ]
                    ),
                    formula_log="weighted_roi_by_spend",
                )
            ]

        response = build_tab_response(
            "1.1",
            TabRequest(dropdown_state={}),
            cache={"1.1.2.4": {"hash": "hash-1", "spec": chart_spec}},
            data_frames={"bi": make_source_df()},
            calculate_fn=fake_calculate,
        )

        chart = response.charts[0]
        self.assertEqual(chart.visual_type, "grouped_line_bar")
        self.assertEqual(chart.x_axis_field, "activity_group")
        self.assertEqual(chart.series_field, "time")
        self.assertEqual(chart.left_y_axis_fields, ["spend"])
        self.assertEqual(chart.right_y_axis_fields, ["roi"])

    def test_tab_response_normalizes_axis_field_aliases_for_display(self) -> None:
        base_spec = make_chart_spec("1.1.2.4", data_level="tactic")
        chart_spec = base_spec.model_copy(
            update={
                "visual_type": "grouped_line_bar",
                "time_scope": "trend",
                "axes": base_spec.axes.model_copy(
                    update={
                        "x": "tactic",
                        "series": "period",
                        "y": ["roi", "spend"],
                        "left_y": ["spend"],
                        "right_y": ["roi"],
                    }
                ),
            }
        )

        def fake_calculate(chart_spec, tab_filter_result, dropdown_state):
            return [
                FacetCalcResult(
                    label="uk",
                    filters={"country": "uk"},
                    df=pd.DataFrame(
                        [
                            {
                                "time": "Q1 2026",
                                "activity_group": "audio",
                                "roi": 7.7,
                                "spend": 100.0,
                            }
                        ]
                    ),
                    formula_log="weighted_roi_by_spend",
                )
            ]

        response = build_tab_response(
            "1.1",
            TabRequest(dropdown_state={}),
            cache={"1.1.2.4": {"hash": "hash-1", "spec": chart_spec}},
            data_frames={"bi": make_source_df()},
            calculate_fn=fake_calculate,
        )

        chart = response.charts[0]
        self.assertEqual(chart.x_axis_field, "activity_group")
        self.assertEqual(chart.series_field, "time")
        self.assertEqual(chart.facets[0].series[0]["activity_group"], "audio")
        self.assertEqual(chart.facets[0].series[0]["time"], "Q1 2026")

    def test_tab_response_assembles_chart_data_facets_series_calc_result_and_warnings(self) -> None:
        def fake_calculate(chart_spec, tab_filter_result, dropdown_state):
            return [
                FacetCalcResult(
                    label="uk",
                    filters={"country": "uk"},
                    df=pd.DataFrame(
                        [
                            {
                                "time": "Q1 2026",
                                "activity_group": "paid search",
                                "roi": 1.2,
                                "spend": 100.0,
                                "growth_rate": None,
                            }
                        ]
                    ),
                    formula_log="weighted_roi_by_spend",
                    warnings=["missing prior period", "missing prior period"],
                )
            ]

        response = build_tab_response(
            "1.1",
            TabRequest(
                dropdown_state={
                    "outcome_fields": {"country": ["uk"]},
                    "snapshot_current_period": "Q1 2026",
                    "snapshot_prior_period": "Q1 2025",
                    "trend_start_period": "Q1 2025",
                    "trend_end_period": "Q3 2026",
                }
            ),
            cache={"1.1.1.1": {"hash": "hash-1", "spec": make_chart_spec("1.1.1.1")}},
            data_frames={"bi": make_source_df()},
            calculate_fn=fake_calculate,
        )

        chart = response.charts[0]
        facet = chart.facets[0]

        self.assertEqual(chart.chart_id, "1.1.1.1")
        self.assertEqual(chart.chart_title, "Synthetic Chart Title")
        self.assertEqual(chart.visual_type, "cards")
        self.assertEqual(chart.x_axis_field, None)
        self.assertEqual(chart.y_axis_fields, ["roi", "spend"])
        self.assertEqual(chart.warnings, ["missing prior period"])
        self.assertEqual(facet.series[0]["time"], "Q1 2026")
        self.assertEqual(facet.series[0]["growth_rate"], None)
        self.assertEqual(facet.calc_result["roi"], 1.2)
        self.assertEqual(facet.calc_result["growth_rate"], None)
        self.assertEqual(facet.warnings, ["missing prior period"])

    def test_tab_response_applies_category_in_chart_quantiles(self) -> None:
        base_spec = make_chart_spec("1.1.2.5", data_level="tactic")
        payload = base_spec.model_dump()
        payload.update(
            {
                "visual_type": "bar_chart",
                "axes": {
                    "x": "activity_group",
                    "y": ["roi", "spend"],
                    "left_y": ["roi"],
                    "right_y": ["spend"],
                },
                "category_in_chart": {
                    "metric": "roi",
                    "method": "quantile",
                    "direction": "desc",
                    "labels": ["Excellent", "Good", "Fair"],
                    "thresholds": [],
                },
            }
        )
        chart_spec = ChartSpec.model_validate(payload)

        def fake_calculate(chart_spec, tab_filter_result, dropdown_state):
            return [
                FacetCalcResult(
                    label="uk",
                    filters={"country": "uk"},
                    df=pd.DataFrame(
                        [
                            {"activity_group": "low", "roi": 1.0, "spend": 30.0},
                            {"activity_group": "high", "roi": 7.0, "spend": 10.0},
                            {"activity_group": "mid", "roi": 3.0, "spend": 20.0},
                        ]
                    ),
                    formula_log="weighted_roi_by_spend",
                )
            ]

        response = build_tab_response(
            "1.1",
            TabRequest(dropdown_state={}),
            cache={"1.1.2.5": {"hash": "hash-1", "spec": chart_spec}},
            data_frames={"bi": make_source_df()},
            calculate_fn=fake_calculate,
        )

        chart = response.charts[0]
        facet = chart.facets[0]
        levels = {
            row["activity_group"]: row["category_label"]
            for row in facet.series
        }

        self.assertEqual(chart.category_in_chart.labels, ["Excellent", "Good", "Fair"])
        self.assertEqual(levels["high"], "Excellent")
        self.assertEqual(levels["mid"], "Good")
        self.assertEqual(levels["low"], "Fair")
        self.assertEqual(facet.series[0]["category_metric"], "roi")

    def test_tab_response_errors_when_tab_has_no_compiled_specs(self) -> None:
        with self.assertRaisesRegex(ValueError, "No compiled ChartSpecs"):
            build_tab_response(
                "1.1",
                TabRequest(dropdown_state={}),
                cache={},
                data_frames={"bi": make_source_df()},
            )


if __name__ == "__main__":
    unittest.main()
