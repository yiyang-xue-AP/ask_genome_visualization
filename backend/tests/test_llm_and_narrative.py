from __future__ import annotations

import json
import unittest

from backend.app.deepseek_client import DeepSeekClient
from backend.app.grid_parser import row_hash
from backend.app.llm_chart_compiler import (
    COMPILER_CACHE_VERSION,
    compile_chart_specs,
)
from backend.app.narrative_generator import generate_narrative
from backend.app.schemas import ChartSpec, NarrativeFacetInput, RawChartRow


def make_raw_row(
    chart_id: str,
    metric: str = "ROI, Spend",
    sorting: str = "NA",
) -> RawChartRow:
    columns = {
        "Chart page Num": "1",
        "Chart page Name": "ROI / Efficiency",
        "High Level Tab Num": "1.1",
        "High Level Tab name": "Portfolio Overview",
        "Section Number": "1.1.1",
        "Section": "Aggregated Marketing ROI at Overall Portfolio level",
        "# Chart Item Num": chart_id,
        "Chart Description": "Aggregated Marketing ROI Snapshot at Portfolio Level",
        "Source file": "BI",
        "Metric": metric,
        "Analytical Intent": "KPI / Single Value",
        "Data Level": "portfolio",
        "Visual Type": "Cards",
        "Facet": "One facet per selected outcome field value",
        "category in chart": None,
        "Chart title": "values of outcome fields + Metric + time range",
        "Sorting": sorting,
        "Calculation": "weighted ROI by spend for all activity_group. Calculate growth rate",
        "Instruction for Summary Narrative": "Compare facets.",
        "comment": None,
    }
    return RawChartRow(columns=columns, row_hash=row_hash(columns))


def chart_spec_payload(
    chart_id: str,
    metrics: list[str] | None = None,
    visual_type: str = "cards",
) -> dict:
    selected_metrics = metrics or ["roi", "spend"]
    return {
        "chart_id": chart_id,
        "chart_description": "Aggregated Marketing ROI Snapshot at Portfolio Level",
        "chart_title": "Aggregated Portfolio ROI Snapshot",
        "page": {"num": 1, "name": "ROI / Efficiency"},
        "tab": {"num": "1.1", "name": "Portfolio Overview"},
        "section": {
            "num": "1.1.1",
            "name": "Aggregated Marketing ROI at Overall Portfolio level",
        },
        "source": "bi",
        "metrics": selected_metrics,
        "visual_type": visual_type,
        "data_level": "portfolio",
        "sorting": None,
        "calculation": {
            "operation": "weighted_roi_by_spend",
            "also_compute": ["growth_rate"],
        },
        "facet": {"enabled": True, "source_fields": "dropdown_outcome_fields"},
        "axes": {"x": None, "y": selected_metrics},
        "time_scope": "snapshot",
        "narrative_instruction": "Compare facets.",
        "validation_warnings": [],
    }


class FakeJsonClient:
    def __init__(self, outputs: list[dict]) -> None:
        self.outputs = list(outputs)
        self.calls: list[tuple[str, str]] = []

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        self.calls.append((system_prompt, user_prompt))
        if not self.outputs:
            raise AssertionError("FakeJsonClient has no output queued")
        return self.outputs.pop(0)


class DeepSeekClientTests(unittest.TestCase):
    def test_default_model_uses_v4_pro(self) -> None:
        client = DeepSeekClient(api_key="test-key")

        self.assertEqual(client.model, "deepseek-v4-pro")


class LlmCompilerTests(unittest.TestCase):
    def test_hash_diff_calls_llm_only_for_new_or_changed_rows(self) -> None:
        cache = {}
        rows = [make_raw_row("1.1.1.1"), make_raw_row("1.1.1.2")]
        client = FakeJsonClient(
            [
                chart_spec_payload("1.1.1.1"),
                chart_spec_payload("1.1.1.2"),
                chart_spec_payload("1.1.1.1", metrics=["roi", "response", "cpm"]),
            ]
        )

        first = compile_chart_specs(rows, cache=cache, llm_client=client)
        second = compile_chart_specs(rows, cache=cache, llm_client=client)
        changed = compile_chart_specs(
            [make_raw_row("1.1.1.1", metric="ROI, response, cpm")],
            cache=cache,
            llm_client=client,
        )

        self.assertEqual(first.recompiled_ids, ["1.1.1.1", "1.1.1.2"])
        self.assertEqual(second.cached_ids, ["1.1.1.1", "1.1.1.2"])
        self.assertEqual(changed.recompiled_ids, ["1.1.1.1"])
        self.assertEqual(changed.deleted_ids, ["1.1.1.2"])
        self.assertEqual(len(client.calls), 3)
        self.assertIn("response_format", client.calls[0][0] + client.calls[0][1])
        self.assertIn("bar_chart", client.calls[0][0])
        self.assertIn("grouped_line_bar", client.calls[0][0])
        self.assertIn("column role", client.calls[0][0])
        self.assertIn("Renderer contract", client.calls[0][0])
        self.assertIn("Use runtime data column names in axes", client.calls[0][0])
        self.assertIn("axes.series should use time", client.calls[0][0])
        self.assertIn("Axis role rules", client.calls[0][0])
        self.assertIn("Tactic comparison", client.calls[0][0])
        self.assertIn("axes.x activity_group", client.calls[0][0])
        self.assertIn("does not by itself make axes.x time", client.calls[0][0])
        self.assertIn("Generate chart_title", client.calls[0][0])
        self.assertIn("Do not infer growth rate", client.calls[0][0])

    def test_cache_recompiles_when_compiler_version_is_missing(self) -> None:
        old_spec = ChartSpec.model_validate(chart_spec_payload("1.1.1.1"))
        cache = {"1.1.1.1": {"hash": make_raw_row("1.1.1.1").row_hash, "spec": old_spec}}
        client = FakeJsonClient([chart_spec_payload("1.1.1.1")])

        result = compile_chart_specs(
            [make_raw_row("1.1.1.1")],
            cache=cache,
            llm_client=client,
        )

        self.assertEqual(result.recompiled_ids, ["1.1.1.1"])
        self.assertEqual(result.cached_ids, [])
        self.assertEqual(cache["1.1.1.1"]["compiler_version"], COMPILER_CACHE_VERSION)

    def test_blank_calculation_non_change_sorting_prompt_uses_weighted_operation(self) -> None:
        row = make_raw_row("1.1.2.2", metric="ROI, response, cpm", sorting="ROI desc")
        row.columns["Calculation"] = None
        row.columns["Chart Description"] = (
            "Marketing Tactics ROI recent change at overall Portfolio Level"
        )
        row.columns["Instruction for Summary Narrative"] = (
            "Analyze how Response and Cost influenced ROI shifts."
        )
        client = FakeJsonClient(
            [chart_spec_payload("1.1.2.2", ["roi", "response", "cpm"], "bar_chart")]
        )

        compile_chart_specs([row], cache={}, llm_client=client)

        self.assertIn(
            "blank/NA Calculation plus non-change Sorting means weighted_roi_by_spend",
            client.calls[0][1],
        )

    def test_nullable_axis_lists_are_normalized_without_retry(self) -> None:
        payload = chart_spec_payload("1.1.1.1")
        payload["axes"]["left_y"] = None
        payload["axes"]["right_y"] = None
        payload["validation_warnings"] = None
        client = FakeJsonClient([payload])

        result = compile_chart_specs(
            [make_raw_row("1.1.1.1")],
            cache={},
            llm_client=client,
        )

        spec = result.chart_specs[0]
        self.assertEqual(spec.axes.left_y, [])
        self.assertEqual(spec.axes.right_y, [])
        self.assertEqual(spec.validation_warnings, [])
        self.assertEqual(len(client.calls), 1)

    def test_invalid_llm_output_retries_once_with_validation_details(self) -> None:
        invalid_payload = chart_spec_payload("1.1.1.1")
        invalid_payload["visual_type"] = "combo"
        client = FakeJsonClient(
            [
                invalid_payload,
                chart_spec_payload("1.1.1.1"),
            ]
        )

        result = compile_chart_specs(
            [make_raw_row("1.1.1.1")],
            cache={},
            llm_client=client,
        )

        self.assertEqual(result.chart_specs[0].visual_type, "cards")
        self.assertEqual(len(client.calls), 2)
        self.assertIn("failed schema validation", client.calls[1][1])
        self.assertIn("Previous invalid JSON", client.calls[1][1])

    def test_llm_output_controls_visual_type(self) -> None:
        client = FakeJsonClient(
            [chart_spec_payload("1.1.2.2", ["roi", "response", "cpm"], "bar_chart")]
        )

        result = compile_chart_specs(
            [make_raw_row("1.1.2.2", metric="ROI, response, cpm")],
            cache={},
            llm_client=client,
        )

        self.assertEqual(result.chart_specs[0].visual_type, "bar_chart")

    def test_llm_output_controls_grouped_line_bar_axes(self) -> None:
        payload = chart_spec_payload(
            "1.1.2.4",
            ["roi", "spend"],
            "grouped_line_bar",
        )
        payload["data_level"] = "tactic"
        payload["time_scope"] = "trend"
        payload["axes"] = {
            "x": "activity_group",
            "series": "time",
            "y": ["roi", "spend"],
            "left_y": ["spend"],
            "right_y": ["roi"],
        }
        client = FakeJsonClient([payload])

        result = compile_chart_specs(
            [make_raw_row("1.1.2.4")],
            cache={},
            llm_client=client,
        )

        spec = result.chart_specs[0]
        self.assertEqual(spec.visual_type, "grouped_line_bar")
        self.assertEqual(spec.axes.x, "activity_group")
        self.assertEqual(spec.axes.series, "time")
        self.assertEqual(spec.axes.left_y, ["spend"])
        self.assertEqual(spec.axes.right_y, ["roi"])

    def test_llm_output_is_validated_against_chart_spec_schema(self) -> None:
        client = FakeJsonClient([{"chart_id": "1.1.1.1"}])

        with self.assertRaises(Exception):
            compile_chart_specs(
                [make_raw_row("1.1.1.1")],
                cache={},
                llm_client=client,
            )


class NarrativeTests(unittest.TestCase):
    def test_empty_instruction_returns_empty_narrative_without_llm_call(self) -> None:
        chart_spec = ChartSpec.model_validate(
            {**chart_spec_payload("1.1.1.1"), "narrative_instruction": ""}
        )
        client = FakeJsonClient(
            [{"narrative": "Should not be used", "data_references": []}]
        )

        response = generate_narrative(chart_spec, [], llm_client=client)

        self.assertEqual(response.narrative, "")
        self.assertEqual(response.data_references, [])
        self.assertEqual(len(client.calls), 0)

    def test_narrative_sends_all_facets_in_one_llm_request(self) -> None:
        chart_spec = ChartSpec.model_validate(chart_spec_payload("1.1.1.1"))
        facets = [
            NarrativeFacetInput(
                label="uk",
                calc_result={"roi": 1.2, "growth_rate": 0.1},
                series=[
                    {"time": "Q1 2025", "roi": 1.0, "spend": 100.0},
                    {"time": "Q2 2025", "roi": 1.2, "spend": 110.0},
                ],
                formula_log="weighted_roi_by_spend + growth_rate",
            ),
            NarrativeFacetInput(
                label="us",
                calc_result={"roi": 0.9, "growth_rate": -0.05},
                series=[
                    {"time": "Q1 2025", "roi": 1.0, "spend": 90.0},
                    {"time": "Q2 2025", "roi": 0.9, "spend": 95.0},
                ],
                formula_log="weighted_roi_by_spend + growth_rate",
            ),
        ]
        client = FakeJsonClient(
            [
                {
                    "narrative": "UK outperformed US.",
                    "data_references": [
                        {"facet": "uk", "metric": "roi", "value": 1.2},
                        {"facet": "us", "metric": "roi", "value": 0.9},
                    ],
                }
            ]
        )

        response = generate_narrative(chart_spec, facets, llm_client=client)
        system_prompt = client.calls[0][0]
        user_payload = json.loads(client.calls[0][1])

        self.assertEqual(response.narrative, "UK outperformed US.")
        self.assertEqual(len(client.calls), 1)
        self.assertIn("insight-first", system_prompt)
        self.assertIn("Lead with the 'so what'", system_prompt)
        self.assertIn("do not invent causes", system_prompt)
        self.assertIn("writing_guidelines", user_payload)
        self.assertIn(
            "Start with the main insight or implication, not a raw value.",
            user_payload["writing_guidelines"],
        )
        self.assertIn(
            "Use only enough numbers to substantiate the insight; avoid a metric-by-metric readout.",
            user_payload["writing_guidelines"],
        )
        self.assertIn("uk", user_payload["results_by_dimension"])
        self.assertIn("us", user_payload["results_by_dimension"])
        self.assertEqual(user_payload["results_by_dimension"]["uk"]["roi"], 1.2)
        self.assertEqual(
            user_payload["chart_data_by_dimension"]["uk"][1]["time"],
            "Q2 2025",
        )
        self.assertEqual(user_payload["chart_data_by_dimension"]["us"][0]["spend"], 90.0)


if __name__ == "__main__":
    unittest.main()
