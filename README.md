# Ask Genome Visualization

A dashboard built with FastAPI, pandas, React, and Recharts, configured through `visualgrid.xlsx`.

## How to run

Start in the repository root using Windows PowerShell. 

Configure `DEEPSEEK_API_KEY` in your environment, or copy `backend/.env.example` to `backend/.env` and fill in the key. 

**Backend — terminal 1**

```powershell
.\scripts\run_backend.cmd
```

**Frontend — terminal 2**

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

For portable Node.js in `.tools/`, add its runtime directory to this terminal's `PATH` first.

Open <http://127.0.0.1:5173>. API documentation is at <http://127.0.0.1:8001/docs>. 

Required inputs: `visualgrid.xlsx`, `supporting_files/unit_sign_config.csv`, and `data/{bi,br,total}_masking_llm_ready.csv` (three files). The `data/` directory is excluded from Git.

The first page load compiles missing chart specs using DeepSeek; this can take several minutes. Specs are saved in `.cache/chart_specs.json` and reused across restarts. Click **Compile Grid** after workbook edits. Generated insights also use DeepSeek.

## How the grid drives charts

Each non-empty row in the workbook's **Charts** sheet defines one chart.

- **Add a chart:** copy a similar row, assign a unique `# Chart Item Num`, and keep tab/section identifiers consistent with its placement in a configured tab.
- **Delete a chart:** remove its row.
- **Apply changes:** save the workbook and click **Compile Grid**. Unchanged rows reuse compatible cached specs; new/changed rows are recompiled, and deleted charts are removed from the cache.

| Grid columns | What you can tune |
| --- | --- |
| `Source file`, `Metric` | Source (`bi`, `br`, `total`; one source per tab) and metrics (`roi`, `spend`, `response`, `cpm`, `activity`). |
| `Visual Type`, `Data Level`, `Analytical Intent` | Supported chart style, portfolio/tactic grouping, and snapshot/trend analysis. |
| `Calculation`, `Sorting` | Supported calculations such as weighted ROI and growth rates, plus sort metric and direction. |
| `Facet`, `category in chart` | Outcome-field facets and value bands using quantiles or explicit thresholds. |
| `Chart title`, `Instruction for Summary Narrative` | Chart titles and instructions for generated insights. |
| Page, tab, section, and chart identifiers | Chart placement and grouping within configured tabs. |

Supported visuals are cards, bar charts, line/bar charts, grouped line/bar charts, and a line/bar/scatter switch. The **Config** sheet supplies outcome-field display aliases; `supporting_files/unit_sign_config.csv` controls metric units and decimal precision. Dropdown selections control runtime filters and time periods.

A **ChartSpec** is a validated chart definition produced by DeepSeek from a grid row: source, metrics, axes, calculations, sorting, facets, and narrative instructions. The backend executes it against the CSV data to produce **ChartData** for rendering:

```text
Grid row -> DeepSeek -> ChartSpec -> filter + calculate -> ChartData -> Recharts
```

DeepSeek translates configuration and writes insights; filtering, calculations, and rendering use code. New tab/filter rules, renderer types, or calculations require code changes. See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for the implementation map.

### Key ChartSpec fields

These fields control the main chart behavior. Full definitions are in [schemas.py](backend/app/schemas.py).

| Field | Main options / purpose |
| --- | --- |
| `source` | `bi`, `br`, `total`; use one source per tab. |
| `metrics` | One or more of `roi`, `spend`, `response`, `cpm`, `activity`. |
| `visual_type` | `cards`, `bar_chart`, `line_bar`, `grouped_line_bar`, `line_bar_scatter_switch`. |
| `data_level` | `portfolio` or `tactic` grouping. |
| `time_scope` | `snapshot` or `trend`. |
| `axes` | X/series column names, commonly `time` or `activity_group`; Y/left-Y/right-Y lists select metrics. |
| `calculation` | `operation`: `weighted_roi_by_spend` or `growth_rate`; `also_compute` commonly adds `["growth_rate"]`. |
| `sorting` | A metric, its `*_change` field, or `period`, with direction `asc` or `desc`; `null` to omit. |
| `category_in_chart` | Optional `quantile` or `threshold` value bands, with a metric and labels; `null` to omit. |
| `chart_title` | Free-text display title. |
| `narrative_instruction` | Free-text instructions for insights; an empty string skips generation. |
