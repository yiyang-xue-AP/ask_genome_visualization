"""Compile-time pipeline for visualgrid.xlsx."""

from pathlib import Path

from backend.app.deepseek_client import JsonChatClient
from backend.app.grid_parser import parse_grid
from backend.app.llm_chart_compiler import (
    ChartCompiler,
    compile_chart_specs,
    load_spec_cache,
    save_spec_cache,
    spec_cache,
)
from backend.app.schemas import CompileResponse
from backend.app.spec_validator import load_data_source_profiles, validate_chart_specs
from backend.app.tab_configs import TAB_CONFIGS

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DATA_PATHS = {
    "bi": PROJECT_ROOT / "data" / "bi_masking_llm_ready.csv",
    "br": PROJECT_ROOT / "data" / "br_masking_llm_ready.csv",
    "total": PROJECT_ROOT / "data" / "total_masking_llm_ready.csv",
}
DEFAULT_SPEC_CACHE_PATH = PROJECT_ROOT / ".cache" / "chart_specs.json"


def compile_grid(
    grid_path: str | Path,
    compiler: ChartCompiler | None = None,
    llm_client: JsonChatClient | None = None,
    cache_path: str | Path | None = DEFAULT_SPEC_CACHE_PATH,
) -> CompileResponse:
    """Run parser, LLM compiler, cache diff, and validator."""

    resolved_grid_path = _resolve_grid_path(grid_path)
    resolved_cache_path = _resolve_cache_path(cache_path) if cache_path is not None else None
    working_cache = (
        load_spec_cache(resolved_cache_path)
        if resolved_cache_path is not None
        else dict(spec_cache)
    )

    raw_rows = parse_grid(resolved_grid_path)
    compile_result = compile_chart_specs(
        raw_rows,
        cache=working_cache,
        compiler=compiler,
        llm_client=llm_client,
    )
    spec_cache.clear()
    spec_cache.update(working_cache)
    if resolved_cache_path is not None:
        save_spec_cache(working_cache, resolved_cache_path)

    data_profiles = load_data_source_profiles(DEFAULT_DATA_PATHS)
    validation_report = validate_chart_specs(
        compile_result.chart_specs,
        tab_specs=TAB_CONFIGS,
        data_profiles=data_profiles,
    )

    return CompileResponse(
        chart_specs=compile_result.chart_specs,
        validation_report=validation_report,
        recompiled_ids=compile_result.recompiled_ids,
        cached_ids=compile_result.cached_ids,
    )


def _resolve_grid_path(grid_path: str | Path) -> Path:
    path = Path(grid_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _resolve_cache_path(cache_path: str | Path) -> Path:
    path = Path(cache_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path
