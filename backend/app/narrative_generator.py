"""DeepSeek-backed narrative generation."""

from __future__ import annotations

import json
from collections.abc import Sequence

from backend.app.deepseek_client import DeepSeekClient, JsonChatClient
from backend.app.schemas import (
    ChartSpec,
    NarrativeFacetInput,
    NarrativeResponse,
)


def generate_narrative(
    chart_spec: ChartSpec,
    facets: Sequence[NarrativeFacetInput],
    llm_client: JsonChatClient | None = None,
) -> NarrativeResponse:
    """Generate a cross-facet narrative from already calculated results."""

    instruction = chart_spec.narrative_instruction.strip()
    if not instruction:
        return NarrativeResponse(narrative="", data_references=[])

    active_client = llm_client or DeepSeekClient()
    llm_output = active_client.chat_json(
        system_prompt=_narrative_system_prompt(),
        user_prompt=_narrative_user_prompt(instruction, facets),
    )
    return NarrativeResponse.model_validate(llm_output)


def _narrative_system_prompt() -> str:
    schema_json = json.dumps(NarrativeResponse.model_json_schema(), ensure_ascii=False)
    return (
        "You are a senior marketing effectiveness analyst writing insight-first "
        "executive commentary. Base every conclusion only on the numbers provided. "
        "Identify patterns, outliers, tradeoffs, trend inflections, divergences "
        "between facets, and efficiency implications. Lead with the 'so what' "
        "instead of restating the data. Use a small number of specific values only "
        "as evidence. Do not list every metric, do not narrate the chart left to "
        "right, and do not invent causes, actions, data, or calculations that are "
        "not supported by the input. If the data is too thin for an insight, say "
        "what can be observed and what remains inconclusive. Output JSON only and "
        "match this schema: "
        f"{schema_json}"
    )


def _narrative_user_prompt(
    instruction: str,
    facets: Sequence[NarrativeFacetInput],
) -> str:
    results_by_dimension = {
        facet.label: facet.calc_result for facet in facets
    }
    chart_data_by_dimension = {
        facet.label: facet.series for facet in facets
    }
    formula_logs = {
        facet.label: facet.formula_log for facet in facets if facet.formula_log
    }
    payload = {
        "task": instruction,
        "writing_guidelines": [
            "Write one concise insight paragraph, usually 1-3 sentences.",
            "Start with the main insight or implication, not a raw value.",
            "Compare facets, periods, or tactics when the data allows it.",
            "Call out efficiency patterns such as high ROI with lower spend, spend growth without ROI lift, or diverging ROI/spend trajectories.",
            "Use only enough numbers to substantiate the insight; avoid a metric-by-metric readout.",
            "Do not invent causal explanations. Phrase unsupported drivers as areas to investigate, not facts.",
        ],
        "results_by_dimension": results_by_dimension,
        "chart_data_by_dimension": chart_data_by_dimension,
        "formula_used": formula_logs,
        "output_json": {
            "narrative": "string",
            "data_references": [
                {"facet": "string", "metric": "string", "value": "number or string"}
            ],
        },
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
