from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import Workbook

from backend.app.compile_pipeline import compile_grid
from backend.app.grid_parser import row_hash, parse_config_aliases, parse_grid
from backend.app.llm_chart_compiler import compile_chart_specs, spec_cache
from backend.app.schemas import ChartSpec, RawChartRow
from backend.app.spec_validator import DataSourceProfile, validate_chart_specs
from backend.app.tab_configs import TAB_CONFIGS


REPO_ROOT = Path(__file__).resolve().parents[2]
GRID_PATH = REPO_ROOT / "visualgrid.xlsx"
TEST_TMP_ROOT = Path("C:/tmp")


def make_raw_row(chart_id: str, **overrides: str | None) -> RawChartRow:
    columns: dict[str, str | None] = {
        "Chart page Num": "1",
        "Chart page Name": "ROI / Efficiency",
        "High Level Tab Num": "1.1",
        "High Level Tab name": "Portfolio Overview",
        "Section Number": "1.1.1",
        "Section": "Aggregated Marketing ROI at Overall Portfolio level",
        "# Chart Item Num": chart_id,
        "Chart Description": "Aggregated Marketing ROI at Portfolio level",
        "Source file": "BI",
        "Metric": "ROI, Spend",
        "Analytical Intent": "Trend",
        "Data Level": "portfolio",
        "Visual Type": "ROI - Line; Spend - Bar ",
        "Facet": "One facet per selected outcome field value",
        "category in chart": None,
        "Chart title": "values of outcome fields + Metric + time range",
        "Sorting": "period",
        "Calculation": "weighted ROI by spend for all activity_group.",
        "Instruction for Summary Narrative": "Identify trend type.",
        "comment": None,
    }
    columns.update(overrides)
    return RawChartRow(columns=columns, row_hash=row_hash(columns))


def make_chart_spec(
    chart_id: str = "1.1.1.1",
    tab_num: str = "1.1",
    time_scope: str = "snapshot",
    metrics: list[str] | None = None,
    validation_warnings: list[str] | None = None,
) -> ChartSpec:
    selected_metrics = metrics or ["roi", "spend"]
    return ChartSpec(
        chart_id=chart_id,
        chart_description="Aggregated Marketing ROI Snapshot at Portfolio Level",
        page={"num": 1, "name": "ROI / Efficiency"},
        tab={"num": tab_num, "name": "Portfolio Overview"},
        section={
            "num": "1.1.1",
            "name": "Aggregated Marketing ROI at Overall Portfolio level",
        },
        source="bi",
        metrics=selected_metrics,
        visual_type="cards",
        data_level="portfolio",
        sorting=None,
        calculation={"operation": "weighted_roi_by_spend", "also_compute": []},
        facet={"enabled": True, "source_fields": "dropdown_outcome_fields"},
        axes={"x": None, "y": selected_metrics},
        time_scope=time_scope,
        narrative_instruction="",
        validation_warnings=validation_warnings or [],
    )


def fake_compiler(row: RawChartRow) -> ChartSpec:
    metric_text = row.columns["Metric"] or ""
    metrics = []
    for token in metric_text.split(","):
        normalized = token.strip().lower()
        if normalized:
            metrics.append(normalized)
    return make_chart_spec(
        chart_id=row.columns["# Chart Item Num"] or "missing",
        metrics=metrics or ["roi"],
    )


class ParserTests(unittest.TestCase):
    def test_parse_grid_reads_charts_rows_and_preserves_cell_values(self) -> None:
        rows = parse_grid(GRID_PATH)

        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[0].columns["# Chart Item Num"], "1.1.1.1")
        self.assertEqual(rows[0].columns["High Level Tab Num"], "1.1")
        self.assertIsNone(rows[0].columns["category in chart"])
        self.assertEqual(rows[0].row_hash, row_hash(rows[0].columns))

    def test_parse_config_aliases_reads_optional_alias_table(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=TEST_TMP_ROOT) as temp_dir:
            grid_path = Path(temp_dir) / "visualgrid.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Config"
            sheet.append(["SECTION 2 - Outcome Field Aliases"])
            sheet.append(["Field Name", "Alias"])
            sheet.append(["country", "Country"])
            sheet.append(["business_unit_for_kpi", "Business Unit"])
            workbook.save(grid_path)
            workbook.close()

            aliases = parse_config_aliases(grid_path)

        self.assertEqual(
            aliases,
            {
                "country": "Country",
                "business_unit_for_kpi": "Business Unit",
            },
        )

    def test_parse_config_aliases_reads_key_value_rows(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=TEST_TMP_ROOT) as temp_dir:
            grid_path = Path(temp_dir) / "visualgrid.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Config"
            sheet.append(["field_alias.detailed_kpi", "Detailed KPI"])
            workbook.save(grid_path)
            workbook.close()

            aliases = parse_config_aliases(grid_path)

        self.assertEqual(aliases, {"detailed_kpi": "Detailed KPI"})

    def test_row_hash_is_stable_and_changes_with_cell_value(self) -> None:
        row = {"# Chart Item Num": "1.1.1.1", "Metric": "ROI, Spend"}
        same_row_different_order = {"Metric": "ROI, Spend", "# Chart Item Num": "1.1.1.1"}
        changed_row = {"# Chart Item Num": "1.1.1.1", "Metric": "ROI"}

        self.assertEqual(row_hash(row), row_hash(same_row_different_order))
        self.assertNotEqual(row_hash(row), row_hash(changed_row))


class CompilerCacheTests(unittest.TestCase):
    def test_cache_reuses_unchanged_rows_and_recompiles_changed_rows(self) -> None:
        cache = {}
        first_row = make_raw_row("1.1.1.1")
        second_row = make_raw_row("1.1.1.2")

        first_result = compile_chart_specs(
            [first_row, second_row],
            cache=cache,
            compiler=fake_compiler,
        )
        self.assertEqual(first_result.recompiled_ids, ["1.1.1.1", "1.1.1.2"])
        self.assertEqual(first_result.cached_ids, [])

        second_result = compile_chart_specs(
            [first_row, second_row],
            cache=cache,
            compiler=fake_compiler,
        )
        self.assertEqual(second_result.recompiled_ids, [])
        self.assertEqual(second_result.cached_ids, ["1.1.1.1", "1.1.1.2"])

        changed_first_row = make_raw_row("1.1.1.1", Metric="ROI, response, cpm")
        third_result = compile_chart_specs(
            [changed_first_row],
            cache=cache,
            compiler=fake_compiler,
        )

        self.assertEqual(third_result.recompiled_ids, ["1.1.1.1"])
        self.assertEqual(third_result.cached_ids, [])
        self.assertEqual(third_result.deleted_ids, ["1.1.1.2"])
        self.assertEqual(set(cache.keys()), {"1.1.1.1"})
        self.assertEqual(third_result.chart_specs[0].metrics, ["roi", "response", "cpm"])

    def test_compile_grid_uses_cache_for_unchanged_visualgrid(self) -> None:
        spec_cache.clear()

        first_result = compile_grid(
            "visualgrid.xlsx",
            compiler=fake_compiler,
            cache_path=None,
        )
        second_result = compile_grid(
            "visualgrid.xlsx",
            compiler=fake_compiler,
            cache_path=None,
        )

        self.assertEqual(len(first_result.chart_specs), 12)
        self.assertEqual(len(first_result.recompiled_ids), 12)
        self.assertEqual(second_result.recompiled_ids, [])
        self.assertEqual(len(second_result.cached_ids), 12)

    def test_compile_grid_reuses_persistent_cache_after_memory_reset(self) -> None:
        def compiler_that_should_not_run(row: RawChartRow) -> ChartSpec:
            raise AssertionError(f"Compiler should not run for {row.columns}")

        TEST_TMP_ROOT.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=TEST_TMP_ROOT) as temp_dir:
            cache_path = Path(temp_dir) / "chart_specs.json"
            spec_cache.clear()

            first_result = compile_grid(
                "visualgrid.xlsx",
                compiler=fake_compiler,
                cache_path=cache_path,
            )
            spec_cache.clear()
            second_result = compile_grid(
                "visualgrid.xlsx",
                compiler=compiler_that_should_not_run,
                cache_path=cache_path,
            )

        self.assertEqual(len(first_result.recompiled_ids), 12)
        self.assertEqual(second_result.recompiled_ids, [])
        self.assertEqual(len(second_result.cached_ids), 12)

    def test_compile_grid_failure_does_not_publish_partial_cache(self) -> None:
        original_spec = make_chart_spec("1.1.1.1")
        spec_cache.clear()
        spec_cache["1.1.1.1"] = {
            "hash": "previous-hash",
            "compiler_version": "previous-version",
            "spec": original_spec,
        }
        calls = {"count": 0}

        def failing_compiler(row: RawChartRow) -> ChartSpec:
            calls["count"] += 1
            if calls["count"] == 2:
                raise ValueError("synthetic compile failure")
            return make_chart_spec(row.columns["# Chart Item Num"] or "missing")

        with self.assertRaisesRegex(ValueError, "synthetic compile failure"):
            compile_grid(
                "visualgrid.xlsx",
                compiler=failing_compiler,
                cache_path=None,
            )

        self.assertEqual(list(spec_cache.keys()), ["1.1.1.1"])
        self.assertIs(spec_cache["1.1.1.1"]["spec"], original_spec)


class ValidatorTests(unittest.TestCase):
    def test_validator_reports_ok_warning_and_error_statuses(self) -> None:
        data_profiles = {
            "bi": DataSourceProfile(
                columns={"measure_group", "measure", "time"},
                distinct_period_count=4,
                has_prior_year_period=True,
            )
        }
        specs = [
            make_chart_spec("1.1.1.1"),
            make_chart_spec(
                "1.1.1.2",
                validation_warnings=["visual_type was mapped by mock compiler"],
            ),
            make_chart_spec("1.1.1.3", tab_num="9.9"),
        ]

        report = validate_chart_specs(
            specs,
            tab_specs=TAB_CONFIGS,
            data_profiles=data_profiles,
        )

        self.assertEqual(report.ok, 1)
        self.assertEqual(report.warning, 1)
        self.assertEqual(report.error, 1)
        self.assertEqual(report.charts[2].status, "error")
        self.assertIn("has no matching TabSpec", report.charts[2].messages[0])

    def test_validator_checks_period_requirements(self) -> None:
        data_profiles = {
            "bi": DataSourceProfile(
                columns={"measure_group", "measure", "time"},
                distinct_period_count=2,
                has_prior_year_period=False,
            )
        }
        specs = [
            make_chart_spec("1.1.1.1", time_scope="snapshot"),
            make_chart_spec("1.1.1.2", time_scope="trend"),
        ]

        report = validate_chart_specs(
            specs,
            tab_specs=TAB_CONFIGS,
            data_profiles=data_profiles,
        )

        self.assertEqual(report.warning, 1)
        self.assertEqual(report.error, 1)
        self.assertIn("prior-year period not found", report.charts[0].messages[0])
        self.assertIn("fewer than 3 periods", report.charts[1].messages[0])


if __name__ == "__main__":
    unittest.main()
