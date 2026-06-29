from __future__ import annotations

import unittest

import pandas as pd

from backend.app.calculation_engine import add_metric_growth_rates, calculate_chart
from backend.app.filter_engine import (
    build_available_outcome_field_options,
    filter_tab,
    get_outcome_fields,
    normalize_dropdown_state,
)
from backend.app.period_utils import filter_by_granularity, period_range, sort_periods
from backend.app.schemas import ChartSpec
from backend.app.tab_configs import TAB_CONFIGS


def make_wide_df() -> pd.DataFrame:
    rows = []
    for country in ("uk", "us"):
        for business_unit in ("APS", "SBS"):
            for activity_group, current_roi, prior_roi, current_spend, prior_spend in (
                ("paid search", 2.0, 1.0, 100.0, 100.0),
                ("paid social", 4.0, 3.0, 300.0, 300.0),
            ):
                rows.extend(
                    [
                        {
                            "country": country,
                            "kpi": "overall",
                            "detailed_kpi": "overall",
                            "business_unit_for_kpi": business_unit,
                            "activity_group": activity_group,
                            "measure_group": "",
                            "measure": "",
                            "time": "Q1 2026",
                            "roi": current_roi,
                            "spend": current_spend,
                            "response": current_spend * 2,
                            "cpm": 10.0,
                        },
                        {
                            "country": country,
                            "kpi": "overall",
                            "detailed_kpi": "overall",
                            "business_unit_for_kpi": business_unit,
                            "activity_group": activity_group,
                            "measure_group": "",
                            "measure": "",
                            "time": "Q1 2025",
                            "roi": prior_roi,
                            "spend": prior_spend,
                            "response": prior_spend * 2,
                            "cpm": 12.0,
                        },
                        {
                            "country": country,
                            "kpi": "overall",
                            "detailed_kpi": "overall",
                            "business_unit_for_kpi": business_unit,
                            "activity_group": activity_group,
                            "measure_group": "",
                            "measure": "",
                            "time": "Q2 2026",
                            "roi": current_roi + 1,
                            "spend": current_spend + 10,
                            "response": current_spend * 3,
                            "cpm": 11.0,
                        },
                    ]
                )

    rows.append(
        {
            "country": "uk",
            "kpi": "conversions",
            "detailed_kpi": "online",
            "business_unit_for_kpi": "APS",
            "activity_group": "paid search",
            "measure_group": "paid media",
            "measure": "",
            "time": "Q1 2026",
            "roi": 99.0,
            "spend": 999.0,
            "response": 1.0,
            "cpm": 1.0,
        }
    )
    return pd.DataFrame(rows)


def make_period_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"time": "quarter 1 2025", "period_type": "quarter", "value": 1},
            {"time": "quarter 1 2026", "period_type": "quarter", "value": 2},
            {"time": "quarter 2 2025", "period_type": "quarter", "value": 3},
            {"time": "quarter 2 2026", "period_type": "quarter", "value": 4},
            {"time": "year 2025", "period_type": "year", "value": 5},
        ]
    )


def make_long_df() -> pd.DataFrame:
    rows = []
    for metric, value in (("roi", 2.0), ("spend", 100.0)):
        rows.append(
            {
                "country": "uk",
                "kpi": "overall",
                "detailed_kpi": "overall",
                "business_unit_for_kpi": "APS",
                "activity_group": "paid search",
                "measure_group": "",
                "measure": "",
                "time": "Q1 2026",
                "metric": metric,
                "value": value,
            }
        )
    return pd.DataFrame(rows)


def make_chart_spec(
    data_level: str = "portfolio",
    time_scope: str = "snapshot",
    metrics: list[str] | None = None,
    calculation: dict[str, object] | None = None,
) -> ChartSpec:
    selected_metrics = metrics or ["roi", "spend"]
    return ChartSpec(
        chart_id="1.1.1.1",
        chart_description="Synthetic chart",
        page={"num": 1, "name": "ROI / Efficiency"},
        tab={"num": "1.1", "name": "Portfolio Overview"},
        section={"num": "1.1.1", "name": "Synthetic section"},
        source="bi",
        metrics=selected_metrics,
        visual_type="cards",
        data_level=data_level,
        sorting=None,
        calculation=calculation
        or {"operation": "weighted_roi_by_spend", "also_compute": ["growth_rate"]},
        facet={"enabled": True, "source_fields": "dropdown_outcome_fields"},
        axes={"x": None, "y": selected_metrics},
        time_scope=time_scope,
        narrative_instruction="",
        validation_warnings=[],
    )


class FilterEngineTests(unittest.TestCase):
    def test_outcome_fields_are_columns_before_activity_group(self) -> None:
        self.assertEqual(
            get_outcome_fields(make_wide_df()),
            ["country", "kpi", "detailed_kpi", "business_unit_for_kpi"],
        )

    def test_tab_11_auto_filters_aggregates_and_splits_facets(self) -> None:
        result = filter_tab(
            TAB_CONFIGS["1.1"],
            {
                "outcome_fields": {
                    "country": ["uk", "us"],
                    "business_unit_for_kpi": ["APS", "SBS"],
                }
            },
            make_wide_df(),
        )

        self.assertEqual(result.auto_filtered_fields, ["kpi", "detailed_kpi"])
        self.assertEqual(len(result.facet_slices), 4)
        self.assertEqual(result.facet_slices[0].label, "uk | APS")
        self.assertTrue((result.shared_df["kpi"] == "overall").all())
        self.assertTrue((result.shared_df["measure_group"] == "").all())
        self.assertNotIn("conversions", set(result.shared_df["kpi"]))

    def test_tab_12_rejects_aggregate_multi_select(self) -> None:
        with self.assertRaisesRegex(ValueError, "aggregate value must be single-select"):
            filter_tab(
                TAB_CONFIGS["1.2"],
                {"outcome_fields": {"kpi": ["overall", "conversions"]}},
                make_wide_df(),
            )

    def test_facet_limit_allows_many_fields_when_each_field_has_at_most_two_values(self) -> None:
        result = filter_tab(
            TAB_CONFIGS["1.2"],
            {
                "outcome_fields": {
                    "country": ["uk", "us"],
                    "kpi": ["overall"],
                    "detailed_kpi": ["overall"],
                    "business_unit_for_kpi": ["APS"],
                }
            },
            make_wide_df(),
        )

        self.assertEqual(len(result.facet_slices), 2)

    def test_facet_limit_rejects_more_than_two_values_in_one_field(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "country: too many selected values: 3 exceeds 2",
        ):
            filter_tab(
                TAB_CONFIGS["1.2"],
                {
                    "outcome_fields": {
                        "country": ["uk", "us", "ca"],
                        "kpi": ["overall"],
                    }
                },
                make_wide_df(),
            )

    def test_available_outcome_options_follow_real_data_combinations(self) -> None:
        options = build_available_outcome_field_options(
            TAB_CONFIGS["1.2"],
            {"outcome_fields": {"country": ["us"]}},
            make_wide_df(),
        )

        self.assertEqual(options["country"], ["uk", "us"])
        self.assertEqual(options["kpi"], ["overall"])
        self.assertEqual(options["detailed_kpi"], ["overall"])
        self.assertEqual(options["business_unit_for_kpi"], ["APS", "SBS"])

    def test_normalized_dropdown_state_removes_invalid_child_selection(self) -> None:
        normalized = normalize_dropdown_state(
            TAB_CONFIGS["1.2"],
            {"outcome_fields": {"country": ["us"], "kpi": ["conversions"]}},
            make_wide_df(),
        )

        self.assertEqual(normalized["outcome_fields"], {"country": ["us"]})

    def test_normalized_dropdown_state_keeps_aggregate_single_select(self) -> None:
        normalized = normalize_dropdown_state(
            TAB_CONFIGS["1.2"],
            {"outcome_fields": {"country": ["uk"], "kpi": ["overall", "conversions"]}},
            make_wide_df(),
        )

        self.assertEqual(
            normalized["outcome_fields"],
            {"country": ["uk"], "kpi": ["overall"]},
        )

    def test_normalized_dropdown_state_preserves_auto_filtered_hidden_fields(self) -> None:
        normalized = normalize_dropdown_state(
            TAB_CONFIGS["1.1"],
            {
                "outcome_fields": {
                    "country": ["uk"],
                    "kpi": ["overall"],
                    "detailed_kpi": ["overall"],
                    "business_unit_for_kpi": ["APS"],
                }
            },
            make_wide_df(),
        )

        self.assertEqual(
            normalized["outcome_fields"],
            {
                "kpi": ["overall"],
                "detailed_kpi": ["overall"],
                "country": ["uk"],
                "business_unit_for_kpi": ["APS"],
            },
        )


class PeriodUtilsTests(unittest.TestCase):
    def test_sort_periods_uses_chronological_order_not_string_order(self) -> None:
        self.assertEqual(
            sort_periods(
                [
                    "quarter 1 2026",
                    "quarter 2 2025",
                    "quarter 1 2025",
                    "quarter 2 2026",
                ]
            ),
            [
                "quarter 1 2025",
                "quarter 2 2025",
                "quarter 1 2026",
                "quarter 2 2026",
            ],
        )

    def test_period_range_excludes_future_quarters_past_end_period(self) -> None:
        self.assertEqual(
            period_range(
                make_period_df()["time"],
                "quarter 1 2025",
                "quarter 4 2025",
            ),
            ["quarter 1 2025", "quarter 2 2025"],
        )

    def test_filter_by_granularity_uses_period_type(self) -> None:
        filtered = filter_by_granularity(make_period_df(), "quarter")

        self.assertEqual(set(filtered["period_type"]), {"quarter"})
        self.assertNotIn("year 2025", set(filtered["time"]))


class CalculationEngineTests(unittest.TestCase):
    def test_snapshot_portfolio_weighted_roi_and_growth_rate(self) -> None:
        tab_result = filter_tab(
            TAB_CONFIGS["1.1"],
            {"outcome_fields": {"country": ["uk"], "business_unit_for_kpi": ["APS"]}},
            make_wide_df(),
        )

        results = calculate_chart(
            make_chart_spec(),
            tab_result,
            {
                "snapshot_current_period": "Q1 2026",
                "snapshot_prior_period": "Q1 2025",
                "trend_start_period": "Q1 2025",
                "trend_end_period": "Q2 2026",
            },
        )

        uk_aps = results[0]
        self.assertEqual(uk_aps.label, "uk | APS")
        self.assertEqual(uk_aps.warnings, [])
        self.assertEqual(len(uk_aps.df), 1)
        row = uk_aps.df.iloc[0]
        self.assertAlmostEqual(row["roi"], 3.5)
        self.assertAlmostEqual(row["spend"], 400.0)
        self.assertAlmostEqual(row["roi_prior"], 2.5)
        self.assertAlmostEqual(row["roi_growth_rate"], 0.4)
        self.assertAlmostEqual(row["spend_growth_rate"], 0.0)
        self.assertAlmostEqual(row["growth_rate"], 0.4)

    def test_growth_rate_missing_current_does_not_warn(self) -> None:
        warnings: list[str] = []
        result = add_metric_growth_rates(
            pd.DataFrame(
                [
                    {
                        "roi_current": None,
                        "roi_prior": None,
                        "response_current": 10.0,
                        "response_prior": None,
                    }
                ]
            ),
            ["roi", "response"],
            warnings,
        )

        self.assertTrue(pd.isna(result.iloc[0]["roi_growth_rate"]))
        self.assertTrue(pd.isna(result.iloc[0]["response_growth_rate"]))
        self.assertEqual(warnings, ["response_growth_rate: prior value is missing or zero"])

    def test_axes_y_metrics_are_included_even_when_metrics_list_omits_them(self) -> None:
        tab_result = filter_tab(
            TAB_CONFIGS["1.1"],
            {"outcome_fields": {"country": ["uk"], "business_unit_for_kpi": ["APS"]}},
            make_wide_df(),
        )

        chart_spec = make_chart_spec(metrics=["roi"])
        chart_spec = chart_spec.model_copy(
            update={"axes": chart_spec.axes.model_copy(update={"y": ["roi", "spend"]})},
        )
        result = calculate_chart(
            chart_spec,
            tab_result,
            {
                "snapshot_current_period": "Q1 2026",
                "snapshot_prior_period": "Q1 2025",
                "trend_start_period": "Q1 2025",
                "trend_end_period": "Q2 2026",
            },
        )[0]

        self.assertIn("spend", result.df.columns)
        self.assertIn("spend_growth_rate", result.df.columns)
        self.assertAlmostEqual(result.df.iloc[0]["spend"], 400.0)

    def test_snapshot_missing_prior_adds_warning_and_null_growth(self) -> None:
        tab_result = filter_tab(
            TAB_CONFIGS["1.1"],
            {"outcome_fields": {"country": ["uk"], "business_unit_for_kpi": ["APS"]}},
            make_wide_df(),
        )

        result = calculate_chart(
            make_chart_spec(),
            tab_result,
            {
                "snapshot_current_period": "Q1 2026",
                "snapshot_prior_period": "Q1 2024",
                "trend_start_period": "Q1 2025",
                "trend_end_period": "Q2 2026",
            },
        )[0]

        self.assertIn("prior period not found", result.warnings[0])
        self.assertTrue(result.df["growth_rate"].isna().all())

    def test_trend_insufficient_periods_warns_and_returns_empty_facets(self) -> None:
        tab_result = filter_tab(
            TAB_CONFIGS["1.1"],
            {"outcome_fields": {"country": ["uk"], "business_unit_for_kpi": ["APS"]}},
            make_wide_df(),
        )

        result = calculate_chart(
            make_chart_spec(time_scope="trend"),
            tab_result,
            {
                "snapshot_current_period": "Q1 2026",
                "snapshot_prior_period": "Q1 2025",
                "trend_start_period": "Q1 2025",
                "trend_end_period": "Q1 2026",
            },
        )[0]

        self.assertTrue(result.df.empty)
        self.assertTrue(any("fewer than 3 periods" in warning for warning in result.warnings))
        self.assertTrue(any("no rows" in warning for warning in result.warnings))

    def test_tactic_trend_groupby_preserves_activity_group(self) -> None:
        df = pd.concat(
            [
                make_wide_df(),
                pd.DataFrame(
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
                            "roi": 9.0,
                            "spend": 50.0,
                            "response": 5.0,
                            "cpm": 8.0,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        tab_result = filter_tab(
            TAB_CONFIGS["1.1"],
            {"outcome_fields": {"country": ["uk"], "business_unit_for_kpi": ["APS"]}},
            df,
        )

        result = calculate_chart(
            make_chart_spec(
                data_level="tactic",
                time_scope="trend",
                calculation={"operation": "weighted_roi_by_spend", "also_compute": []},
            ),
            tab_result,
            {
                "snapshot_current_period": "Q1 2026",
                "snapshot_prior_period": "Q1 2025",
                "trend_start_period": "Q1 2025",
                "trend_end_period": "Q2 2026",
            },
        )[0]

        paid_search_q1 = result.df[
            (result.df["activity_group"] == "paid search")
            & (result.df["time"] == "Q1 2026")
        ].iloc[0]
        self.assertEqual(paid_search_q1["roi"], 2.0)
        self.assertEqual(paid_search_q1["spend"], 150.0)

    def test_tactic_trend_drops_activity_groups_with_all_missing_metrics(self) -> None:
        empty_tactic_rows = []
        for period in ("Q1 2025", "Q1 2026", "Q2 2026"):
            empty_tactic_rows.append(
                {
                    "country": "uk",
                    "kpi": "overall",
                    "detailed_kpi": "overall",
                    "business_unit_for_kpi": "APS",
                    "activity_group": "events",
                    "measure_group": "",
                    "measure": "",
                    "time": period,
                    "roi": None,
                    "spend": None,
                    "response": None,
                    "cpm": None,
                }
            )
        df = pd.concat(
            [make_wide_df(), pd.DataFrame(empty_tactic_rows)],
            ignore_index=True,
        )
        tab_result = filter_tab(
            TAB_CONFIGS["1.1"],
            {"outcome_fields": {"country": ["uk"], "business_unit_for_kpi": ["APS"]}},
            df,
        )

        result = calculate_chart(
            make_chart_spec(
                data_level="tactic",
                time_scope="trend",
                calculation={"operation": "weighted_roi_by_spend", "also_compute": []},
            ),
            tab_result,
            {
                "snapshot_current_period": "Q1 2026",
                "snapshot_prior_period": "Q1 2025",
                "trend_start_period": "Q1 2025",
                "trend_end_period": "Q2 2026",
            },
        )[0]

        self.assertIn("paid search", set(result.df["activity_group"]))
        self.assertNotIn("events", set(result.df["activity_group"]))

    def test_snapshot_tactic_applies_spend_sorting(self) -> None:
        tab_result = filter_tab(
            TAB_CONFIGS["1.1"],
            {"outcome_fields": {"country": ["uk"], "business_unit_for_kpi": ["APS"]}},
            make_wide_df(),
        )
        chart_payload = make_chart_spec(
            data_level="tactic",
            calculation={"operation": "weighted_roi_by_spend", "also_compute": []},
        ).model_dump()
        chart_payload["sorting"] = {"field": "spend", "direction": "desc"}
        chart_spec = ChartSpec.model_validate(chart_payload)

        result = calculate_chart(
            chart_spec,
            tab_result,
            {
                "snapshot_current_period": "Q1 2026",
                "snapshot_prior_period": "Q1 2025",
                "trend_start_period": "Q1 2025",
                "trend_end_period": "Q2 2026",
            },
        )[0]

        self.assertEqual(
            result.df["activity_group"].tolist(),
            ["paid social", "paid search"],
        )

    def test_snapshot_growth_tactic_applies_spend_change_sorting(self) -> None:
        df = make_wide_df()
        df.loc[
            (df["country"] == "uk")
            & (df["business_unit_for_kpi"] == "APS")
            & (df["activity_group"] == "paid search")
            & (df["time"] == "Q1 2026"),
            "spend",
        ] = 150.0
        df.loc[
            (df["country"] == "uk")
            & (df["business_unit_for_kpi"] == "APS")
            & (df["activity_group"] == "paid social")
            & (df["time"] == "Q1 2026"),
            "spend",
        ] = 270.0
        tab_result = filter_tab(
            TAB_CONFIGS["1.1"],
            {"outcome_fields": {"country": ["uk"], "business_unit_for_kpi": ["APS"]}},
            df,
        )
        chart_payload = make_chart_spec(
            data_level="tactic",
            calculation={"operation": "growth_rate", "also_compute": []},
        ).model_dump()
        chart_payload["sorting"] = {"field": "spend_change", "direction": "desc"}
        chart_spec = ChartSpec.model_validate(chart_payload)

        result = calculate_chart(
            chart_spec,
            tab_result,
            {
                "snapshot_current_period": "Q1 2026",
                "snapshot_prior_period": "Q1 2025",
                "trend_start_period": "Q1 2025",
                "trend_end_period": "Q2 2026",
            },
        )[0]

        self.assertEqual(
            result.df["activity_group"].tolist(),
            ["paid search", "paid social"],
        )
        self.assertAlmostEqual(result.df.iloc[0]["spend_growth_rate"], 0.5)

    def test_trend_result_rows_are_sorted_by_period_order(self) -> None:
        df = pd.concat(
            [
                make_wide_df(),
                pd.DataFrame(
                    [
                        {
                            "country": "uk",
                            "kpi": "overall",
                            "detailed_kpi": "overall",
                            "business_unit_for_kpi": "APS",
                            "activity_group": "paid search",
                            "measure_group": "",
                            "measure": "",
                            "time": "Q2 2025",
                            "roi": 3.0,
                            "spend": 110.0,
                            "response": 220.0,
                            "cpm": 10.0,
                        },
                        {
                            "country": "uk",
                            "kpi": "overall",
                            "detailed_kpi": "overall",
                            "business_unit_for_kpi": "APS",
                            "activity_group": "paid social",
                            "measure_group": "",
                            "measure": "",
                            "time": "Q2 2025",
                            "roi": 5.0,
                            "spend": 310.0,
                            "response": 620.0,
                            "cpm": 10.0,
                        },
                    ]
                ),
            ],
            ignore_index=True,
        )
        tab_result = filter_tab(
            TAB_CONFIGS["1.1"],
            {"outcome_fields": {"country": ["uk"], "business_unit_for_kpi": ["APS"]}},
            df,
        )

        result = calculate_chart(
            make_chart_spec(
                time_scope="trend",
                calculation={"operation": "weighted_roi_by_spend", "also_compute": []},
            ),
            tab_result,
            {
                "snapshot_current_period": "Q2 2026",
                "snapshot_prior_period": "Q2 2025",
                "trend_start_period": "Q1 2025",
                "trend_end_period": "Q2 2026",
            },
        )[0]

        self.assertEqual(
            result.df["time"].tolist(),
            ["Q1 2025", "Q2 2025", "Q1 2026", "Q2 2026"],
        )

    def test_grouped_line_bar_sorts_tactics_by_latest_period_roi_desc(self) -> None:
        df = make_wide_df()
        df.loc[
            (df["country"] == "uk")
            & (df["business_unit_for_kpi"] == "APS")
            & (df["activity_group"] == "paid search")
            & (df["time"] == "Q1 2026"),
            "roi",
        ] = 10.0
        df.loc[
            (df["country"] == "uk")
            & (df["business_unit_for_kpi"] == "APS")
            & (df["activity_group"] == "paid search")
            & (df["time"] == "Q2 2026"),
            "roi",
        ] = 1.0
        df.loc[
            (df["country"] == "uk")
            & (df["business_unit_for_kpi"] == "APS")
            & (df["activity_group"] == "paid social")
            & (df["time"] == "Q1 2026"),
            "roi",
        ] = 2.0
        df.loc[
            (df["country"] == "uk")
            & (df["business_unit_for_kpi"] == "APS")
            & (df["activity_group"] == "paid social")
            & (df["time"] == "Q2 2026"),
            "roi",
        ] = 9.0
        tab_result = filter_tab(
            TAB_CONFIGS["1.1"],
            {"outcome_fields": {"country": ["uk"], "business_unit_for_kpi": ["APS"]}},
            df,
        )
        chart_payload = make_chart_spec(
            data_level="tactic",
            time_scope="trend",
            calculation={"operation": "weighted_roi_by_spend", "also_compute": []},
        ).model_dump()
        chart_payload["visual_type"] = "grouped_line_bar"
        chart_payload["sorting"] = {"field": "roi", "direction": "desc"}
        chart_payload["axes"] = {
            "x": "activity_group",
            "series": "time",
            "y": ["roi", "spend"],
            "left_y": ["spend"],
            "right_y": ["roi"],
        }
        chart_spec = ChartSpec.model_validate(chart_payload)

        result = calculate_chart(
            chart_spec,
            tab_result,
            {
                "snapshot_current_period": "Q2 2026",
                "snapshot_prior_period": "Q2 2025",
                "trend_start_period": "Q1 2025",
                "trend_end_period": "Q2 2026",
            },
        )[0]

        self.assertEqual(
            result.df["activity_group"].drop_duplicates().tolist(),
            ["paid social", "paid search"],
        )
        self.assertEqual(
            result.df[result.df["activity_group"] == "paid social"]["time"].tolist(),
            ["Q1 2025", "Q1 2026", "Q2 2026"],
        )

    def test_long_metric_value_data_is_pivoted_deterministically(self) -> None:
        tab_result = filter_tab(
            TAB_CONFIGS["1.1"],
            {"outcome_fields": {"country": ["uk"], "business_unit_for_kpi": ["APS"]}},
            make_long_df(),
        )

        result = calculate_chart(
            make_chart_spec(calculation={"operation": "weighted_roi_by_spend", "also_compute": []}),
            tab_result,
            {
                "snapshot_current_period": "Q1 2026",
                "snapshot_prior_period": "Q1 2025",
                "trend_start_period": "Q1 2025",
                "trend_end_period": "Q2 2026",
            },
        )[0]

        self.assertEqual(result.df.iloc[0]["roi"], 2.0)
        self.assertEqual(result.df.iloc[0]["spend"], 100.0)


if __name__ == "__main__":
    unittest.main()
