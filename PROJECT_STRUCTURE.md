# 项目结构示意图

这个项目可以按一条主链路理解：

```text
visualgrid.xlsx
  -> RawChartRow
  -> ChartSpec
  -> filter + calculation
  -> ChartData
  -> Recharts renderer
```

LLM 只负责两件事：

- compile 阶段：把 `visualgrid.xlsx` 的一行 chart 配置翻译成 `ChartSpec`
- runtime 阶段：基于已经算好的 chart data 生成 insights narrative

数据过滤、计算、排序、ChartData 组装和图表渲染都由确定性代码完成。

## 根目录

```text
ask_genome_visualization/
├── visualgrid.xlsx              # dashboard 的主配置来源
├── requirement.md               # 项目需求和规则说明
├── PROJECT_STRUCTURE.md         # 当前文件
├── data/                        # CSV 数据源
├── backend/                     # FastAPI + pandas + LLM compile/narrative
├── frontend/                    # React + Recharts
├── scripts/                     # 辅助脚本
├── archive/                     # 历史资料/备份
├── archive_code/                # 历史代码/备份
└── .cache/                      # runtime cache，自动生成，不进 git
```

`.cache/chart_specs.json` 是后端 compile 后生成的持久化 ChartSpec cache。它用于跨 session 复用已解析过的 chart spec，删掉也没关系，重新 Compile Grid 会再生成。

## 后端结构

```text
backend/
├── app/
│   ├── main.py                  # FastAPI API 入口
│   ├── schemas.py               # 核心数据结构：ChartSpec / ChartData / TabResponse
│   ├── grid_parser.py           # 读取 visualgrid.xlsx
│   ├── llm_chart_compiler.py    # RawChartRow -> ChartSpec，含 hash cache
│   ├── compile_pipeline.py      # Compile Grid 主流程
│   ├── spec_validator.py        # ChartSpec 校验
│   ├── dashboard_config.py      # 生成前端 dropdown config
│   ├── tab_configs.py           # Tab 级硬编码规则
│   ├── tab_pipeline.py          # /api/tab runtime 主流程
│   ├── filter_engine.py         # dropdown/filter/facet 逻辑
│   ├── calculation_engine.py    # ROI、spend、growth rate、排序等计算
│   ├── narrative_generator.py   # insights prompt 和 narrative 生成
│   ├── deepseek_client.py       # DeepSeek API client
│   └── period_utils.py          # period 解析、排序、范围筛选
└── tests/                       # 后端测试
```

## 前端结构

```text
frontend/
├── src/
│   ├── App.tsx                  # 前端主状态：tab cache、dropdown、narrative async
│   ├── apiClient.ts             # API 请求封装
│   ├── config.ts                # 导出 fetchDashboardConfig
│   ├── types.ts                 # 前端数据类型
│   ├── layoutEngine.ts          # 按 section/chart_id 组织布局
│   ├── components/
│   │   ├── DropdownPanel.tsx    # dropdown UI 和可选组合禁用
│   │   ├── ChartRenderer.tsx    # 根据 visual_type 选择 renderer
│   │   └── renderers/
│   │       ├── CardsRenderer.tsx
│   │       ├── BarChartRenderer.tsx
│   │       ├── LineBarRenderer.tsx
│   │       ├── GroupedLineBarRenderer.tsx
│   │       ├── LineBarScatterSwitchRenderer.tsx
│   │       └── renderHelpers.ts
│   └── styles.css
└── tests/                       # 前端静态测试
```

## Compile Grid 流程

用户点击前端的 `Compile Grid` 后：

```text
POST /api/compile
  -> backend/app/main.py
  -> compile_pipeline.compile_grid()
  -> grid_parser.parse_grid()
       visualgrid.xlsx Charts sheet -> list[RawChartRow]
  -> llm_chart_compiler.compile_chart_specs()
       row_hash 未变 -> 复用 cache
       row_hash 变化/新增 -> 调 DeepSeek 生成 ChartSpec
       grid 删除 -> 删除 cache 中对应 chart
  -> spec_validator.validate_chart_specs()
  -> 写入内存 spec_cache 和 .cache/chart_specs.json
  -> 返回 CompileResponse
```

最重要文件：

- `backend/app/compile_pipeline.py`
- `backend/app/grid_parser.py`
- `backend/app/llm_chart_compiler.py`
- `backend/app/spec_validator.py`

## 页面加载和 dropdown 配置流程

页面第一次打开时：

```text
GET /api/dashboard-config
  -> dashboard_config.build_dashboard_config()
  -> 读取 data CSV
  -> 推导 metric options
  -> 推导 period options/defaults
  -> 推导 outcome field options
  -> 读取 Config sheet 中的 outcome field alias
  -> 返回 DashboardConfig
```

最重要文件：

- `backend/app/dashboard_config.py`
- `backend/app/filter_engine.py`
- `frontend/src/App.tsx`
- `frontend/src/components/DropdownPanel.tsx`

## Tab 数据请求流程

用户加载 tab 或改变 dropdown 后：

```text
POST /api/tab/{tab_num}
  -> backend/app/main.py
  -> tab_pipeline.build_tab_response()
  -> 找到当前 tab 的 ChartSpec
  -> 读取对应 source data
  -> normalize_dropdown_state()
  -> build_available_outcome_field_options()
  -> filter_tab()
       tactic_filter
       auto_filter aggregate fields
       拆 facet slices
  -> calculate_chart()
       time slicing
       portfolio/tactic groupby
       weighted ROI
       growth rate
       sorting
  -> assemble ChartData
  -> 返回 TabResponse
```

最重要文件：

- `backend/app/tab_pipeline.py`
- `backend/app/filter_engine.py`
- `backend/app/calculation_engine.py`
- `backend/app/schemas.py`

## 前端渲染流程

前端拿到 `ChartData` 后：

```text
App.tsx
  -> groupChartsBySection()
  -> ChartRenderer
       visual_type === cards
       visual_type === bar_chart
       visual_type === line_bar
       visual_type === grouped_line_bar
       visual_type === line_bar_scatter_switch
  -> 对应 Recharts renderer
```

`ChartSpec` 里真正影响画图的字段主要是：

- `visual_type`
- `metrics`
- `axes.x`
- `axes.y`
- `axes.left_y`
- `axes.right_y`
- `axes.series`
- `data_level`
- `time_scope`
- `calculation`
- `sorting`
- `chart_title`

最重要文件：

- `frontend/src/App.tsx`
- `frontend/src/layoutEngine.ts`
- `frontend/src/components/ChartRenderer.tsx`
- `frontend/src/components/renderers/*`

## Insights narrative 流程

图表数据返回并渲染后，前端异步请求 narrative：

```text
App.tsx
  -> fetchNarrative(chart_id, facets)
  -> POST /api/narrative/{chart_id}
  -> narrative_generator.generate_narrative()
       使用 ChartSpec.narrative_instruction
       使用 FacetData.calc_result
       使用 FacetData.series
       使用 formula_log
  -> DeepSeek
  -> NarrativeResponse
  -> 写入前端 tabCache[tab_num].narratives[chart_id]
```

最重要文件：

- `frontend/src/App.tsx`
- `backend/app/narrative_generator.py`
- `backend/app/deepseek_client.py`

## 常见修改入口

如果你要改 grid 怎么被解析：

```text
backend/app/grid_parser.py
backend/app/llm_chart_compiler.py
```

如果你要改 ChartSpec schema：

```text
backend/app/schemas.py
backend/app/llm_chart_compiler.py
backend/app/spec_validator.py
frontend/src/types.ts
```

如果你要改 dropdown：

```text
backend/app/dashboard_config.py
backend/app/filter_engine.py
frontend/src/components/DropdownPanel.tsx
```

如果你要改数据计算：

```text
backend/app/calculation_engine.py
backend/app/tab_pipeline.py
```

如果你要改 chart 排序：

```text
backend/app/calculation_engine.py
```

如果你要加一种新图：

```text
backend/app/schemas.py            # VisualType enum
backend/app/llm_chart_compiler.py # prompt 中加入映射规则
backend/app/tab_pipeline.py       # 如需新 ChartData 字段，在这里组装
frontend/src/types.ts
frontend/src/components/ChartRenderer.tsx
frontend/src/components/renderers/NewRenderer.tsx
requirement.md
```

如果你要改 insights 风格：

```text
backend/app/narrative_generator.py
```

如果你要改 DeepSeek 模型或 API key 读取：

```text
backend/app/deepseek_client.py
```

## 最短阅读路线

如果只想快速看懂项目，按这个顺序读：

```text
1. requirement.md
2. backend/app/schemas.py
3. backend/app/main.py
4. backend/app/compile_pipeline.py
5. backend/app/llm_chart_compiler.py
6. backend/app/tab_pipeline.py
7. backend/app/filter_engine.py
8. backend/app/calculation_engine.py
9. frontend/src/App.tsx
10. frontend/src/components/ChartRenderer.tsx
11. frontend/src/components/renderers/*
```

