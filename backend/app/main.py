"""FastAPI application shell."""

from fastapi import FastAPI, HTTPException

from backend.app.compile_pipeline import DEFAULT_SPEC_CACHE_PATH, compile_grid
from backend.app.dashboard_config import build_dashboard_config
from backend.app.llm_chart_compiler import load_spec_cache, spec_cache
from backend.app.narrative_generator import generate_narrative
from backend.app.schemas import (
    CompileRequest,
    CompileResponse,
    DashboardConfigResponse,
    NarrativeRequest,
    NarrativeResponse,
    TabRequest,
    TabResponse,
)
from backend.app.tab_pipeline import build_tab_response

DEFAULT_GRID_PATH = "visualgrid.xlsx"


def create_app() -> FastAPI:
    """Create the backend application instance."""

    app = FastAPI(
        title="Ask Genome Visualization API",
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    @app.get("/api/dashboard-config", response_model=DashboardConfigResponse)
    def dashboard_config_endpoint() -> DashboardConfigResponse:
        try:
            return build_dashboard_config()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/compile", response_model=CompileResponse)
    def compile_endpoint(request: CompileRequest) -> CompileResponse:
        try:
            return compile_grid(request.grid_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/tab/{tab_num}", response_model=TabResponse)
    def tab_endpoint(tab_num: str, request: TabRequest) -> TabResponse:
        try:
            return _build_tab_response_from_persistent_cache(tab_num, request)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/narrative/{chart_id}", response_model=NarrativeResponse)
    def narrative_endpoint(
        chart_id: str,
        request: NarrativeRequest,
    ) -> NarrativeResponse:
        cached = spec_cache.get(chart_id)
        if cached is None:
            raise HTTPException(
                status_code=404,
                detail=f"No compiled ChartSpec found for chart_id: {chart_id}",
            )

        chart_spec = cached.get("spec")
        if chart_spec is None:
            raise HTTPException(
                status_code=404,
                detail=f"No compiled ChartSpec found for chart_id: {chart_id}",
            )

        try:
            return generate_narrative(chart_spec, request.facets)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


def _build_tab_response_from_persistent_cache(
    tab_num: str,
    request: TabRequest,
) -> TabResponse:
    _refresh_spec_cache_from_disk()
    return build_tab_response(tab_num, request)


def _refresh_spec_cache_from_disk() -> None:
    """Keep runtime ChartSpec cache honest with the persistent cache file."""

    if not DEFAULT_SPEC_CACHE_PATH.exists():
        spec_cache.clear()
        return

    disk_cache = load_spec_cache(DEFAULT_SPEC_CACHE_PATH)
    spec_cache.clear()
    spec_cache.update(disk_cache)


app = create_app()
