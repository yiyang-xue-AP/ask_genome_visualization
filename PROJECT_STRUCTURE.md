# Project Structure

The main data flow is:

```text
visualgrid.xlsx
  -> RawChartRow
  -> ChartSpec
  -> filter + calculate
  -> ChartData
  -> Recharts renderer
```

The LLM has two responsibilities:

- At compile time, translate each chart configuration row into a validated `ChartSpec`.
- At runtime, generate insights from already calculated chart data.

Filtering, calculations, sorting, response assembly, and rendering are implemented in code. See [README.md](README.md) for startup instructions and a brief guide to editing the grid.

## Repository layout

```text
ask_genome_visualization/
|-- README.md                    # Startup and grid editing guide
|-- PROJECT_STRUCTURE.md         # Architecture and implementation map
|-- visualgrid.xlsx              # Main dashboard configuration
|-- data/                        # Local CSV sources; excluded from Git
|-- supporting_files/            # Metric formatting configuration
|-- backend/                     # FastAPI, pandas, compilation, and insights
|-- frontend/                    # React, Vite, and Recharts
|-- scripts/                     # Local startup helpers
`-- .cache/                      # Generated runtime cache; excluded from Git
```

`data/` contains `bi_masking_llm_ready.csv`, `br_masking_llm_ready.csv`, and `total_masking_llm_ready.csv`. Source names map to these files in `backend/app/compile_pipeline.py`.

`.cache/chart_specs.json` stores compiled specs across sessions. Cache reuse requires matching row hashes and compiler versions. Deleting the file requires compiling the grid again.

## Backend

```text
backend/
|-- .env.example                 # DeepSeek key template
|-- requirements.txt             # Python dependencies
|-- app/
|   |-- main.py                  # FastAPI entry point and API routes
|   |-- schemas.py               # ChartSpec, ChartData, and API contracts
|   |-- grid_parser.py           # Read Charts and Config workbook sheets
|   |-- llm_chart_compiler.py    # RawChartRow -> ChartSpec and hash cache
|   |-- compile_pipeline.py      # Coordinate grid compilation
|   |-- spec_validator.py        # Validate specs against tab/data requirements
|   |-- dashboard_config.py      # Build dropdown and formatting configuration
|   |-- tab_configs.py           # Tab definitions and filter/time rules
|   |-- tab_pipeline.py          # Assemble runtime tab responses
|   |-- filter_engine.py         # Dropdown normalization, filtering, and facets
|   |-- calculation_engine.py    # Metric calculations, growth, and sorting
|   |-- narrative_generator.py   # Insight prompts and generated narratives
|   |-- deepseek_client.py       # DeepSeek client and API key lookup
|   `-- period_utils.py          # Period parsing, ordering, and range selection
`-- tests/                       # Backend unit and pipeline tests
```

`ChartSpec` describes how to build a chart: its identity, source, metrics, visual type, grouping level, axes, time scope, calculations, sorting, category bands, facets, and narrative instructions. `ChartData` contains the computed values and display metadata sent to the frontend.

Tab-level rules remain in `tab_configs.py`. Adding chart rows within supported tabs is a grid edit; introducing a new tab or filtering policy also requires updating these rules.

## Frontend

```text
frontend/
|-- package.json                 # Dependencies and dev/build scripts
|-- vite.config.ts               # Vite setup and /api proxy to port 8001
|-- src/
|   |-- App.tsx                  # Tab state/cache, dropdowns, and async insights
|   |-- apiClient.ts             # API requests and timeouts
|   |-- config.ts                # Re-export fetchDashboardConfig
|   |-- types.ts                 # Frontend data contracts
|   |-- layoutEngine.ts          # Group charts by section and chart ID
|   |-- components/
|   |   |-- DropdownPanel.tsx    # Filter selection and valid combinations
|   |   |-- ChartRenderer.tsx    # Select renderer by visual_type
|   |   `-- renderers/
|   |       |-- CardsRenderer.tsx
|   |       |-- BarChartRenderer.tsx
|   |       |-- LineBarRenderer.tsx
|   |       |-- GroupedLineBarRenderer.tsx
|   |       |-- LineBarScatterSwitchRenderer.tsx
|   |       |-- CategoryEncoding.tsx
|   |       `-- renderHelpers.ts
|   `-- styles.css
`-- tests/                       # Python-based static frontend checks
```

## Grid compilation

Clicking **Compile Grid** triggers:

```text
POST /api/compile
  -> main.py
  -> compile_pipeline.compile_grid()
  -> grid_parser.parse_grid()
       Charts sheet -> list[RawChartRow]
  -> llm_chart_compiler.compile_chart_specs()
       Unchanged row + matching compiler version -> reuse cached spec
       New or changed row -> ask DeepSeek for a ChartSpec
       Deleted row -> remove its cached spec
  -> publish spec_cache and save .cache/chart_specs.json
  -> spec_validator.validate_chart_specs()
  -> CompileResponse
```

The response includes specs, validation results, and the IDs of recompiled and reused charts. The frontend clears its tab cache and reloads the active tab after compilation. When specs are missing on initial page load, the frontend also attempts compilation automatically.

## Dashboard configuration

On initial page load:

```text
GET /api/dashboard-config
  -> dashboard_config.build_dashboard_config()
  -> read source CSV data
  -> derive metric options, periods/defaults, and outcome-field options
  -> derive valid outcome-field combinations for each tab
  -> read display aliases from the workbook's Config sheet
  -> read units and precision from supporting_files/unit_sign_config.csv
  -> DashboardConfigResponse
```

The frontend uses this response to populate dropdowns and select a valid initial state.

## Tab data requests

Loading a tab or confirming dropdown changes triggers:

```text
POST /api/tab/{tab_num}
  -> main.py refreshes spec_cache from the persistent cache
  -> tab_pipeline.build_tab_response()
  -> select the tab's ChartSpecs and load source data
  -> normalize_dropdown_state()
  -> build_available_outcome_field_options()
  -> filter_tab()
       Apply tactic filters and aggregate-field rules
       Split data into facet slices
  -> calculate_chart()
       Select time periods and group portfolio/tactic data
       Calculate metrics and growth rates
       Apply sorting
  -> assemble ChartData and apply category bands
  -> TabResponse
```

The response includes charts, warnings, normalized dropdown state, available outcome-field options, and automatically filtered fields.

## Chart rendering

```text
App.tsx
  -> layoutEngine.groupChartsBySection()
  -> ChartRenderer
       cards                   -> CardsRenderer
       bar_chart               -> BarChartRenderer
       line_bar                -> LineBarRenderer
       grouped_line_bar        -> GroupedLineBarRenderer
       line_bar_scatter_switch -> LineBarScatterSwitchRenderer
  -> Recharts / KPI cards
```

The main spec fields affecting the result are `visual_type`, `metrics`, `axes.x`, `axes.y`, `axes.left_y`, `axes.right_y`, `axes.series`, `data_level`, `time_scope`, `calculation`, `sorting`, `category_in_chart`, and `chart_title`. The backend converts these into the `ChartData` consumed by renderers.

## Insight generation

After chart data loads, the frontend requests insights asynchronously:

```text
App.tsx
  -> apiClient.fetchNarrative(chart_id, facets)
  -> POST /api/narrative/{chart_id}
  -> narrative_generator.generate_narrative()
       Use ChartSpec.narrative_instruction
       Include each facet's calc_result, series, and formula_log
  -> DeepSeek
  -> NarrativeResponse
  -> tabCache[tab_num].narratives[chart_id]
```

`deepseek_client.py` looks for a non-empty `DEEPSEEK_API_KEY` in the process environment, the root `.env`, then `backend/.env`, in that order.

## Where to make changes

| Change | Main files |
| --- | --- |
| Add, delete, or tune a supported chart | `visualgrid.xlsx`, then Compile Grid |
| Change grid parsing or interpretation | `backend/app/grid_parser.py`, `backend/app/llm_chart_compiler.py` |
| Change ChartSpec contracts | `backend/app/schemas.py`, `backend/app/llm_chart_compiler.py`, `backend/app/spec_validator.py`, `frontend/src/types.ts` |
| Add tabs or change tab rules | `backend/app/tab_configs.py` |
| Change dropdown behavior | `backend/app/dashboard_config.py`, `backend/app/filter_engine.py`, `frontend/src/components/DropdownPanel.tsx` |
| Change calculations or sorting | `backend/app/calculation_engine.py`, `backend/app/tab_pipeline.py` |
| Add a renderer type | `backend/app/schemas.py`, `backend/app/llm_chart_compiler.py`, `backend/app/tab_pipeline.py`, `frontend/src/types.ts`, `frontend/src/components/ChartRenderer.tsx`, and a renderer in `frontend/src/components/renderers/` |
| Change metric units or precision | `supporting_files/unit_sign_config.csv` |
| Change insight style | `backend/app/narrative_generator.py` |
| Change the DeepSeek model or key lookup | `backend/app/deepseek_client.py` |

## Suggested reading order

1. `README.md`
2. `backend/app/schemas.py`
3. `backend/app/main.py`
4. `backend/app/compile_pipeline.py`
5. `backend/app/llm_chart_compiler.py`
6. `backend/app/tab_pipeline.py`
7. `backend/app/filter_engine.py`
8. `backend/app/calculation_engine.py`
9. `frontend/src/App.tsx`
10. `frontend/src/components/ChartRenderer.tsx` and `renderers/`
