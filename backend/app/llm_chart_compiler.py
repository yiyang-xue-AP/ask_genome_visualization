"""DeepSeek-backed chart compiler with hash-diff caching."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from backend.app.deepseek_client import DeepSeekClient, JsonChatClient
from backend.app.schemas import ChartSpec, RawChartRow

ChartSpecCache = dict[str, dict[str, object]]
ChartCompiler = Callable[[RawChartRow], ChartSpec]
COMPILER_CACHE_VERSION = "2026-06-23-axis-role-priority-v2"
PERSISTENT_CACHE_SCHEMA_VERSION = 1

spec_cache: ChartSpecCache = {}


@dataclass(slots=True)
class ChartCompileResult:
    chart_specs: list[ChartSpec]
    recompiled_ids: list[str]
    cached_ids: list[str]
    deleted_ids: list[str]


def compile_chart_specs(
    rows: Sequence[RawChartRow],
    cache: ChartSpecCache | None = None,
    compiler: ChartCompiler | None = None,
    llm_client: JsonChatClient | None = None,
) -> ChartCompileResult:
    """Compile changed/new raw chart rows and reuse unchanged cached specs."""

    active_cache = spec_cache if cache is None else cache
    chart_specs: list[ChartSpec] = []
    recompiled_ids: list[str] = []
    cached_ids: list[str] = []
    current_ids: set[str] = set()
    active_compiler = compiler or (
        lambda row: deepseek_compile_chart_spec(row, llm_client=llm_client)
    )

    for row in rows:
        chart_id = _required_cell(row, "# Chart Item Num")
        if chart_id in current_ids:
            raise ValueError(f"Duplicate chart_id in grid: {chart_id}")
        current_ids.add(chart_id)

        cached = active_cache.get(chart_id)
        if (
            cached
            and cached.get("hash") == row.row_hash
            and cached.get("compiler_version") == COMPILER_CACHE_VERSION
        ):
            spec = cached["spec"]
            if not isinstance(spec, ChartSpec):
                raise TypeError(f"Cached spec for {chart_id} is not a ChartSpec")
            cached_ids.append(chart_id)
        else:
            spec = active_compiler(row)
            active_cache[chart_id] = {
                "hash": row.row_hash,
                "compiler_version": COMPILER_CACHE_VERSION,
                "spec": spec,
            }
            recompiled_ids.append(chart_id)

        chart_specs.append(spec)

    deleted_ids = [
        chart_id for chart_id in list(active_cache.keys()) if chart_id not in current_ids
    ]
    for chart_id in deleted_ids:
        del active_cache[chart_id]

    return ChartCompileResult(
        chart_specs=chart_specs,
        recompiled_ids=recompiled_ids,
        cached_ids=cached_ids,
        deleted_ids=deleted_ids,
    )


def load_spec_cache(cache_path: str | Path) -> ChartSpecCache:
    """Load persisted ChartSpecs from disk, ignoring stale or invalid entries."""

    path = Path(cache_path)
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict):
        return {}
    if payload.get("compiler_version") != COMPILER_CACHE_VERSION:
        return {}

    charts = payload.get("charts")
    if not isinstance(charts, dict):
        return {}

    loaded_cache: ChartSpecCache = {}
    for chart_id, entry in charts.items():
        if not isinstance(chart_id, str) or not isinstance(entry, dict):
            continue

        row_hash = entry.get("row_hash") or entry.get("hash")
        spec_payload = entry.get("spec")
        if not isinstance(row_hash, str) or spec_payload is None:
            continue

        try:
            spec = ChartSpec.model_validate(spec_payload)
        except ValueError:
            continue

        loaded_cache[chart_id] = {
            "hash": row_hash,
            "compiler_version": COMPILER_CACHE_VERSION,
            "spec": spec,
        }

    return loaded_cache


def save_spec_cache(cache: ChartSpecCache, cache_path: str | Path) -> None:
    """Persist valid ChartSpecs to disk for reuse across backend sessions."""

    path = Path(cache_path)
    charts: dict[str, dict[str, object]] = {}
    for chart_id, entry in sorted(cache.items()):
        spec = entry.get("spec")
        row_hash = entry.get("hash")
        compiler_version = entry.get("compiler_version")
        if not isinstance(chart_id, str):
            continue
        if not isinstance(spec, ChartSpec):
            continue
        if not isinstance(row_hash, str):
            continue
        if compiler_version != COMPILER_CACHE_VERSION:
            continue

        charts[chart_id] = {
            "row_hash": row_hash,
            "compiler_version": COMPILER_CACHE_VERSION,
            "spec": spec.model_dump(mode="json"),
        }

    payload = {
        "cache_schema_version": PERSISTENT_CACHE_SCHEMA_VERSION,
        "compiler_version": COMPILER_CACHE_VERSION,
        "charts": charts,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temp_path.replace(path)


def deepseek_compile_chart_spec(
    row: RawChartRow,
    llm_client: JsonChatClient | None = None,
) -> ChartSpec:
    """Ask DeepSeek to translate one raw chart row into a ChartSpec."""

    active_client = llm_client or DeepSeekClient()
    system_prompt = _compiler_system_prompt()
    user_prompt = _compiler_user_prompt(row)
    llm_output = active_client.chat_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    try:
        return _validate_llm_chart_spec_payload(llm_output)
    except ValidationError as exc:
        repaired_output = active_client.chat_json(
            system_prompt=system_prompt,
            user_prompt=_compiler_repair_user_prompt(row, llm_output, exc),
        )
        return _validate_llm_chart_spec_payload(repaired_output)


def _validate_llm_chart_spec_payload(payload: dict) -> ChartSpec:
    return ChartSpec.model_validate(_normalize_llm_chart_spec_payload(payload))


def _normalize_llm_chart_spec_payload(payload: dict) -> dict:
    """Repair harmless JSON-shape drift before strict schema validation."""

    if not isinstance(payload, dict):
        return payload

    normalized = dict(payload)
    axes = normalized.get("axes")
    if isinstance(axes, dict):
        normalized_axes = dict(axes)
        for axis_field in ("y", "left_y", "right_y"):
            if normalized_axes.get(axis_field) is None:
                normalized_axes[axis_field] = []
        normalized["axes"] = normalized_axes

    if normalized.get("validation_warnings") is None:
        normalized["validation_warnings"] = []

    return normalized


def _compiler_repair_user_prompt(
    row: RawChartRow,
    invalid_payload: dict,
    validation_error: ValidationError,
) -> str:
    return (
        _compiler_user_prompt(row)
        + " The previous ChartSpec JSON failed schema validation. Return one corrected "
        "ChartSpec JSON object only. Preserve the intended chart meaning, but fix the "
        "schema errors exactly. Validation errors: "
        f"{_validation_error_summary(validation_error)}. Previous invalid JSON: "
        f"{json.dumps(invalid_payload, ensure_ascii=False, sort_keys=True)}"
    )


def _validation_error_summary(validation_error: ValidationError) -> str:
    return json.dumps(
        validation_error.errors(include_url=False, include_input=False),
        ensure_ascii=False,
    )


def _compiler_system_prompt() -> str:
    schema_json = json.dumps(ChartSpec.model_json_schema(), ensure_ascii=False)
    return (
        "You are a deterministic schema translator. Convert one visualgrid.xlsx "
        "Charts row into exactly one ChartSpec JSON object. Output JSON only; "
        "the API caller uses response_format {\"type\":\"json_object\"}. Do not "
        "add fields outside the schema and do not write executable chart code. "
        "Use the schema enum values exactly as defined. "
        "Interpret the row by column role, with this priority: explicit Visual Type "
        "and category-in-chart text define the renderer and axes; Metric defines "
        "displayed and calculated metrics; Data Level defines portfolio versus tactic "
        "grouping; Analytical Intent defines snapshot versus trend time scope; "
        "Sorting defines sort field and direction; Calculation defines derived "
        "metrics and formulas; narrative columns only populate narrative_instruction. "
        "Do not let Chart Description, Chart title, or narrative wording override "
        "explicit Visual Type, category-in-chart, Data Level, Analytical Intent, "
        "Sorting, or Calculation columns. In particular, a word like trend in Chart "
        "Description does not by itself make axes.x time or time_scope trend. "
        "Use runtime data column names in axes, not display aliases: period/date/quarter "
        "values are stored in the data column time, and tactic/channel/activity labels "
        "are stored in activity_group. Sorting may use the schema field period, but "
        "axes.x and axes.series should use time for period-like dimensions and "
        "activity_group for tactic-like dimensions. "
        "Axis role rules: portfolio trend visuals use axes.x time. Tactic comparison, "
        "relationship, recent-change, switch, bar_chart, and line_bar_scatter_switch "
        "visuals use axes.x activity_group, even when the chart description mentions "
        "trend or change. Tactic over-time visuals should use grouped_line_bar with "
        "axes.x activity_group and axes.series time, rather than axes.x time, when "
        "tactics are the categories being compared. "
        "Renderer contract: cards display KPI metric values; line_bar uses a time "
        "x-axis with bar-like metrics such as spend/activity/response and line-like "
        "metrics such as roi/cpm; bar_chart uses a categorical x-axis, normally "
        "activity_group for tactic charts; grouped_line_bar uses a categorical x-axis "
        "plus a series dimension such as time/period; line_bar_scatter_switch supports "
        "the same combo encoding plus a scatter view. If a visual description names "
        "left and right y-axis assignments, populate axes.left_y and axes.right_y; "
        "axes.y must include every displayed y metric. If an axis role is ambiguous, "
        "choose the closest supported renderer contract and add a validation_warning. "
        "Metric mapping is semantic but bounded by the schema: ROI maps to roi, spend "
        "or cost allocation maps to spend unless the phrase means cost per response "
        "or cost per activity, which maps to cpm; response/conversions/bookings map "
        "to response when used as a metric; activity maps to activity. "
        "Calculation mapping is based only on the Calculation and Sorting columns. "
        "Use growth_rate only when Calculation explicitly requests growth/change-rate "
        "metrics, or when Sorting requests a *_change field. If Calculation is blank, "
        "NA, or missing and Sorting does not request a change field, use "
        "weighted_roi_by_spend with an empty also_compute list. Do not infer growth "
        "rate from chart descriptions, insight text, or general words like trend, "
        "increase, decrease, recent change, shifts, drivers, or impact. "
        "Portfolio data_level means group by selected outcome fields only. Tactic "
        "data_level means group by selected outcome fields plus activity_group. "
        "Generate chart_title from Chart title and Chart Description. Keep it concise, "
        "user-facing, and data-agnostic; do not include runtime dropdown values, facet "
        "values, or period values. Convert template-like titles into natural labels. "
        "Preserve narrative_instruction from the row without rewriting it. "
        "Put ambiguous mappings into validation_warnings instead of silently inventing "
        "a hidden assumption. The ChartSpec JSON schema is: "
        f"{schema_json}"
    )


def _compiler_user_prompt(row: RawChartRow) -> str:
    row_json = json.dumps(row.columns, ensure_ascii=False, sort_keys=True)
    return (
        "Translate this RawChartRow into ChartSpec using the schema and renderer "
        "contracts from the system prompt. Preserve narrative_instruction from "
        "'Instruction for Summary Narrative' without rewriting it. Generate "
        "chart_title from 'Chart title' and Chart Description. Derive axes from "
        "Visual Type, category in chart, Metric, and Analytical Intent. Derive "
        "time_scope from Analytical Intent: trend/over-time means trend; snapshot, "
        "comparison, relationship, current/prior, or recent-change analysis means "
        "snapshot unless the row explicitly asks for a time series. Derive "
        "calculation from Calculation and Sorting only: blank/NA Calculation plus "
        "non-change Sorting means weighted_roi_by_spend, not growth_rate. RawChartRow: "
        f"{row_json}"
    )


def _cell(row: RawChartRow, column: str) -> str | None:
    return row.columns.get(column)


def _required_cell(row: RawChartRow, column: str) -> str:
    value = _cell(row, column)
    if value is None or value == "":
        raise ValueError(f"Raw chart row is missing required column value: {column}")
    return value
