from __future__ import annotations

import unittest
from pathlib import Path


FRONTEND_ROOT = Path(__file__).resolve().parents[1]


def read_source(relative_path: str) -> str:
    return (FRONTEND_ROOT / relative_path).read_text(encoding="utf-8")


class FrontendStaticTests(unittest.TestCase):
    def test_api_client_uses_compile_and_tab_endpoints(self) -> None:
        source = read_source("src/apiClient.ts")

        self.assertIn("/dashboard-config", source)
        self.assertIn('"/compile"', source)
        self.assertIn("`/tab/${tabNum}`", source)
        self.assertIn("`/narrative/${chartId}`", source)
        self.assertIn("REQUEST_TIMEOUT_MS", source)
        self.assertIn("COMPILE_TIMEOUT_MS", source)
        self.assertIn("NARRATIVE_TIMEOUT_MS", source)
        self.assertIn("fetchWithTimeout", source)
        self.assertIn("Backend request timed out", source)
        self.assertIn("dropdown_state: dropdownState", source)
        self.assertIn("outcomeFieldOptions: payload.outcome_field_options", source)
        self.assertIn("outcomeFieldLabels: payload.outcome_field_labels ?? {}", source)
        self.assertIn(
            "outcomeFieldCombinationsByTab: payload.outcome_field_combinations_by_tab ?? {}",
            source,
        )
        self.assertIn("metricFormatConfig: mapMetricFormatConfig", source)

    def test_app_implements_tab_cache_rules(self) -> None:
        source = read_source("src/App.tsx")

        self.assertIn("useRef<Record<string, TabCacheEntry>>({})", source)
        self.assertIn("const autoCompileAttempted = useRef(false)", source)
        self.assertIn('const activeTabNumRef = useRef("")', source)
        self.assertIn('mode === "cache-first"', source)
        self.assertIn("const cachedEntry = tabCache.current[tabNum]", source)
        self.assertIn("tabCache.current[tabNum] = cacheEntry", source)
        self.assertIn("tabCache.current = {}", source)
        self.assertIn("shouldAutoCompile(error)", source)
        self.assertIn("await compileGrid()", source)
        self.assertIn("No compiled ChartSpecs found", source)
        self.assertIn('void loadTab(activeTabNum, nextDropdownState, "refresh")', source)
        self.assertIn("response.normalized_dropdown_state", source)
        self.assertIn("response.available_outcome_field_options", source)
        self.assertIn("setAvailableOutcomeFieldOptions", source)
        self.assertIn("outcomeFieldCombinationsByTab", source)
        self.assertIn("metricFormatConfig={dashboardConfig?.metricFormatConfig ?? {}}", source)
        self.assertIn("validOutcomeCombinations", source)
        self.assertIn("fetchNarrative(chart.chart_id, facets)", source)
        self.assertIn("pendingNarratives", source)
        self.assertIn("setPendingNarratives", source)
        self.assertIn("withoutKey(current, chart.chart_id)", source)
        self.assertIn("fetchDashboardConfig", source)
        self.assertIn("series: facet.series", source)
        self.assertIn("hasOwnProperty.call(cacheEntry.narratives, chart.chart_id)", source)
        self.assertIn("const requestTabNum = activeTabNum", source)
        self.assertIn("tabCache.current[requestTabNum]", source)
        self.assertIn("activeTabNumRef.current === requestTabNum", source)
        self.assertIn("latestEntry !== cacheEntry", source)
        self.assertIn("latestEntry.narratives[chart.chart_id]", source)
        self.assertIn("function handleDropdownConfirm", source)
        self.assertIn("onConfirm={handleDropdownConfirm}", source)
        self.assertNotIn('latestEntry.narratives[chart.chart_id] = "";', source)

    def test_dropdown_panel_hides_auto_filtered_fields_and_confirms_draft(self) -> None:
        source = read_source("src/components/DropdownPanel.tsx")

        self.assertIn("useState(dropdownState)", source)
        self.assertIn("draftDropdownState", source)
        self.assertIn("setDraftDropdownState", source)
        self.assertIn("hasPendingChanges", source)
        self.assertIn("!autoFilteredFields.includes(fieldName)", source)
        self.assertIn("outcomeFieldOptions", source)
        self.assertIn("outcomeFieldLabels", source)
        self.assertIn("outcomeFieldLabels[fieldName] ?? fieldName", source)
        self.assertIn("availableOutcomeFieldOptions", source)
        self.assertIn("validOutcomeCombinations", source)
        self.assertIn("buildDraftAvailableOutcomeFieldOptions", source)
        self.assertIn("recordMatchesSelections", source)
        self.assertIn("isDisabled", source)
        self.assertIn("MAX_VALUES_PER_OUTCOME_FIELD", source)
        self.assertIn("MAX_FACET_COMBINATION_PRODUCT", source)
        self.assertIn("combinationProduct", source)
        self.assertIn("periodOptions[draftDropdownState.period_granularity]", source)
        self.assertIn("periodDefaults[nextGranularity]", source)
        self.assertIn("onConfirm(draftDropdownState)", source)
        self.assertIn("dropdownStatesEqual", source)
        self.assertIn("Reset", source)
        self.assertIn("Confirm", source)
        self.assertNotIn('country: "Country"', source)

    def test_static_customer_config_was_removed(self) -> None:
        source = read_source("src/config.ts")

        self.assertIn("fetchDashboardConfig", source)
        self.assertNotIn("quarter 2 2026", source)
        self.assertNotIn("OUTCOME_FIELD_OPTIONS", source)
        self.assertNotIn("DEFAULT_DROPDOWN_STATE", source)

    def test_layout_engine_groups_by_section(self) -> None:
        source = read_source("src/layoutEngine.ts")

        self.assertIn("groupChartsBySection", source)
        self.assertIn("chart.section_num", source)
        self.assertIn("sectionCharts[0]?.section_name", source)
        self.assertIn('chartId.split(".").slice(0, 3).join(".")', source)
        self.assertIn("compareDottedIds", source)

    def test_chart_renderers_cover_required_visual_types(self) -> None:
        chart_renderer = read_source("src/components/ChartRenderer.tsx")
        bar_chart = read_source("src/components/renderers/BarChartRenderer.tsx")
        grouped_line_bar = read_source("src/components/renderers/GroupedLineBarRenderer.tsx")
        line_bar = read_source("src/components/renderers/LineBarRenderer.tsx")
        switch = read_source("src/components/renderers/LineBarScatterSwitchRenderer.tsx")
        cards = read_source("src/components/renderers/CardsRenderer.tsx")
        render_helpers = read_source("src/components/renderers/renderHelpers.ts")

        self.assertIn('chart.visual_type === "cards"', chart_renderer)
        self.assertIn("chart.chart_title || chart.chart_id", chart_renderer)
        self.assertIn("narrativePending", chart_renderer)
        self.assertIn("Insights are on the way", chart_renderer)
        self.assertIn("narrative-loading", chart_renderer)
        self.assertIn('chart.visual_type === "bar_chart"', chart_renderer)
        self.assertIn('chart.visual_type === "line_bar"', chart_renderer)
        self.assertIn('chart.visual_type === "grouped_line_bar"', chart_renderer)
        self.assertIn('chart.visual_type === "line_bar_scatter_switch"', chart_renderer)
        self.assertIn("shouldDisplayWarning", chart_renderer)
        self.assertIn("visibleWarnings", chart_renderer)
        self.assertIn("BarChartRenderer", chart_renderer)
        self.assertIn("GroupedLineBarRenderer", chart_renderer)
        self.assertIn("leftAxisMetrics", bar_chart)
        self.assertIn("rightAxisMetrics", bar_chart)
        self.assertIn("chart.left_y_axis_fields", bar_chart)
        self.assertIn("chart.right_y_axis_fields", bar_chart)
        self.assertIn('yAxisId="left"', bar_chart)
        self.assertIn('yAxisId="right"', bar_chart)
        self.assertIn('chart.x_axis_field ?? "activity_group"', bar_chart)
        self.assertIn("ComposedChart", line_bar)
        self.assertIn("Bar", line_bar)
        self.assertIn("Line", line_bar)
        self.assertIn('yAxisId="left"', line_bar)
        self.assertIn('yAxisId="right"', line_bar)
        self.assertIn('orientation="right"', line_bar)
        self.assertIn("categoricalAxisProps()", line_bar)
        self.assertIn("axisLineProps()", line_bar)
        self.assertIn("lineMetrics", line_bar)
        self.assertIn("barMetrics", line_bar)
        self.assertIn("buildGroupedData", grouped_line_bar)
        self.assertIn("chart.series_field", grouped_line_bar)
        self.assertIn('chart.x_axis_field ?? "activity_group"', grouped_line_bar)
        self.assertIn("leftAxisMetrics", grouped_line_bar)
        self.assertIn("rightAxisMetrics", grouped_line_bar)
        self.assertIn('yAxisId="left"', grouped_line_bar)
        self.assertIn('yAxisId="right"', grouped_line_bar)
        self.assertIn("Customized", grouped_line_bar)
        self.assertIn("GroupedLineOverlay", grouped_line_bar)
        self.assertIn("GroupedLineTooltip", grouped_line_bar)
        self.assertIn("name={mapping.seriesValue}", grouped_line_bar)
        self.assertIn("metricLabel(metric)", grouped_line_bar)
        self.assertIn("groupedPointX", grouped_line_bar)
        self.assertIn("groupedDataKey", grouped_line_bar)
        self.assertIn("periodSortKey", grouped_line_bar)
        self.assertIn("ScatterChart", switch)
        self.assertIn("setMode", switch)
        self.assertIn('yAxisId="left"', switch)
        self.assertIn('yAxisId="right"', switch)
        self.assertIn("categoricalAxisProps()", switch)
        self.assertIn("axisTickProps()", switch)
        self.assertIn("scatterXAxisKey", switch)
        self.assertIn("scatterYAxisKey", switch)
        self.assertIn("metricLabel(scatterXAxisKey)", switch)
        self.assertIn("metricLabel(scatterYAxisKey)", switch)
        self.assertIn("axisLineProps", render_helpers)
        self.assertIn("formatMetricValue", render_helpers)
        self.assertIn("metricValueFormatter", render_helpers)
        self.assertIn("metricTooltipFormatter", render_helpers)
        self.assertIn('rule.unitSign === "$"', render_helpers)
        self.assertIn('rule.unitSign === "%"', render_helpers)
        self.assertIn('metric.endsWith("_growth_rate")', render_helpers)
        self.assertIn("metricFormatConfig", chart_renderer)
        self.assertIn("metricValueFormatter", bar_chart)
        self.assertIn("metricValueFormatter", line_bar)
        self.assertIn("formatMetricValue", grouped_line_bar)
        self.assertIn("formatMetricValue", switch)
        self.assertIn("formatMetricValue", cards)
        self.assertIn("categoricalAxisProps", render_helpers)
        self.assertIn("facet.calc_result", cards)
        self.assertIn("kpi-card-list", cards)
        self.assertIn("GrowthBadge", cards)
        self.assertIn("growthValueForMetric", cards)
        self.assertNotIn("<dt>growth_rate</dt>", cards)

    def test_frontend_scope_excludes_llm_calls_and_data_calculation(self) -> None:
        combined_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (FRONTEND_ROOT / "src").rglob("*")
            if path.suffix in {".ts", ".tsx"}
        )

        forbidden = [
            "DeepSeek",
            "OpenAI",
            "chat.completions",
            "growth_rate =",
            "weighted_roi_by_spend",
        ]
        for token in forbidden:
            self.assertNotIn(token, combined_source)

        self.assertNotIn("facet.series.filter", combined_source)
        self.assertNotIn("chartData.filter", combined_source)


if __name__ == "__main__":
    unittest.main()
