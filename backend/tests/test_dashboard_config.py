from __future__ import annotations

import unittest

import pandas as pd

from backend.app.dashboard_config import build_dashboard_config


def make_config_source_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "country": "us",
                "kpi": "overall",
                "activity_group": "paid search",
                "time": "quarter 1 2026",
                "period_type": "quarter",
                "metric": "Gross Portfolio ROI",
                "value": 1.0,
            },
            {
                "country": "uk",
                "kpi": "overall",
                "activity_group": "paid search",
                "time": "quarter 2 2025",
                "period_type": "quarter",
                "metric": "Gross Portfolio Spend",
                "value": 100.0,
            },
            {
                "country": "uk",
                "kpi": "overall",
                "activity_group": "paid search",
                "time": "quarter 1 2025",
                "period_type": "quarter",
                "metric": "Gross Portfolio ROI",
                "value": 2.0,
            },
            {
                "country": "uk",
                "kpi": "overall",
                "activity_group": "paid search",
                "time": "quarter 2 2026",
                "period_type": "quarter",
                "metric": "Gross Portfolio ROI",
                "value": 3.0,
            },
            {
                "country": "uk",
                "kpi": "overall",
                "activity_group": "paid search",
                "time": "year 2025",
                "period_type": "year",
                "metric": "Gross Portfolio ROI",
                "value": 4.0,
            },
        ]
    )


def make_non_cartesian_source_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "country": "us",
                "kpi": "overall",
                "detailed_kpi": "overall",
                "business_unit_for_kpi": "portfolio",
                "activity_group": "paid search",
                "time": "quarter 1 2026",
                "period_type": "quarter",
                "metric": "Gross Portfolio ROI",
                "value": 1.0,
            },
            {
                "country": "uk",
                "kpi": "Bookings",
                "detailed_kpi": "enterprise bookings",
                "business_unit_for_kpi": "EMS",
                "activity_group": "paid search",
                "time": "quarter 1 2026",
                "period_type": "quarter",
                "metric": "Gross Portfolio ROI",
                "value": 2.0,
            },
            {
                "country": "uk",
                "kpi": "conversions",
                "detailed_kpi": "app conversions",
                "business_unit_for_kpi": "Platinum",
                "activity_group": "paid search",
                "time": "quarter 1 2026",
                "period_type": "quarter",
                "metric": "Gross Portfolio ROI",
                "value": 3.0,
            },
        ]
    )


class DashboardConfigTests(unittest.TestCase):
    def test_config_derives_options_and_defaults_from_source_data(self) -> None:
        config = build_dashboard_config(
            data_frames={"bi": make_config_source_df()},
            grid_path=None,
        )

        self.assertEqual(config.tabs[0].tab_num, "1.1")
        self.assertEqual(config.outcome_field_options["country"], ["uk", "us"])
        self.assertEqual(config.metric_options, ["roi", "spend"])
        self.assertEqual(
            config.metric_format_config["spend"].model_dump(),
            {"unit_sign": "$", "keep_digit": 2},
        )
        self.assertEqual(
            config.metric_format_config["margin_roi"].model_dump(),
            {"unit_sign": "$", "keep_digit": 2},
        )
        self.assertEqual(
            config.metric_format_config["roi"].model_dump(),
            config.metric_format_config["margin_roi"].model_dump(),
        )
        self.assertEqual(
            config.metric_format_config["sourceofchange"].model_dump(),
            config.metric_format_config["source_of_change"].model_dump(),
        )
        self.assertEqual(
            config.period_options["quarter"],
            [
                "quarter 1 2025",
                "quarter 2 2025",
                "quarter 1 2026",
                "quarter 2 2026",
            ],
        )
        self.assertEqual(
            config.default_dropdown_state.model_dump(),
            {
                "outcome_fields": {"country": ["uk"], "kpi": ["overall"]},
                "metric": "roi",
                "period_granularity": "quarter",
                "snapshot_current_period": "quarter 2 2026",
                "snapshot_prior_period": "quarter 2 2025",
                "trend_start_period": "quarter 1 2025",
                "trend_end_period": "quarter 2 2026",
            },
        )
        self.assertEqual(
            config.outcome_field_labels,
            {"country": "country", "kpi": "kpi"},
        )

    def test_default_dropdown_state_uses_one_valid_full_outcome_combination(self) -> None:
        config = build_dashboard_config(
            data_frames={"bi": make_non_cartesian_source_df()},
            grid_path=None,
        )

        self.assertEqual(
            config.default_dropdown_state.outcome_fields,
            {
                "country": ["uk"],
                "kpi": ["Bookings"],
                "detailed_kpi": ["enterprise bookings"],
                "business_unit_for_kpi": ["EMS"],
            },
        )
        self.assertIn("1.2", config.outcome_field_combinations_by_tab)
        self.assertIn(
            {
                "country": "uk",
                "kpi": "Bookings",
                "detailed_kpi": "enterprise bookings",
                "business_unit_for_kpi": "EMS",
            },
            config.outcome_field_combinations_by_tab["1.2"],
        )
        self.assertNotIn(
            {
                "country": "uk",
                "kpi": "overall",
                "detailed_kpi": "overall",
                "business_unit_for_kpi": "portfolio",
            },
            config.outcome_field_combinations_by_tab["1.2"],
        )

    def test_config_uses_outcome_field_aliases_when_configured(self) -> None:
        config = build_dashboard_config(
            data_frames={"bi": make_non_cartesian_source_df()},
            grid_path=None,
            outcome_field_aliases={
                "country": "Country",
                "detailed kpi": "Detailed KPI",
                "business_unit_for_kpi": "Business Unit",
            },
        )

        self.assertEqual(
            config.outcome_field_labels,
            {
                "country": "Country",
                "kpi": "kpi",
                "detailed_kpi": "Detailed KPI",
                "business_unit_for_kpi": "Business Unit",
            },
        )


if __name__ == "__main__":
    unittest.main()
