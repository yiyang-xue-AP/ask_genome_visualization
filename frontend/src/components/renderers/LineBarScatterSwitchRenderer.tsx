import { useState } from "react";
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipProps } from "recharts";

import type { ChartData, FacetData, MetricFormatConfig } from "../../types";
import { WarningList } from "../ChartRenderer";
import { CategoryDot, CategoryLegend, categoryFill } from "./CategoryEncoding";
import {
  axisLineProps,
  axisTickProps,
  categoricalAxisProps,
  categoryLabelFromRecord,
  displayValue,
  facetTitle,
  formatMetricValue,
  hasCategoryEncoding,
  isBarMetric,
  metricColor,
  metricLabel,
  metricValueFormatter,
} from "./renderHelpers";

interface LineBarScatterSwitchRendererProps {
  chart: ChartData;
  metricFormatConfig: MetricFormatConfig;
}

export function LineBarScatterSwitchRenderer({
  chart,
  metricFormatConfig,
}: LineBarScatterSwitchRendererProps) {
  const [mode, setMode] = useState<"combo" | "scatter">("combo");

  return (
    <div>
      <div className="segmented-control" aria-label="Chart mode">
        <button
          className={mode === "combo" ? "active" : ""}
          type="button"
          onClick={() => setMode("combo")}
        >
          Combo
        </button>
        <button
          className={mode === "scatter" ? "active" : ""}
          type="button"
          onClick={() => setMode("scatter")}
        >
          Scatter
        </button>
      </div>
      <div className="facet-grid chart-grid">
        {chart.facets.map((facet) => (
          <SwitchFacet
            key={facet.label}
            chart={chart}
            facet={facet}
            metricFormatConfig={metricFormatConfig}
            mode={mode}
          />
        ))}
      </div>
    </div>
  );
}

function SwitchFacet({
  chart,
  facet,
  metricFormatConfig,
  mode,
}: {
  chart: ChartData;
  facet: FacetData;
  metricFormatConfig: MetricFormatConfig;
  mode: "combo" | "scatter";
}) {
  return (
    <section className="facet-panel">
      <div className="facet-title">{facetTitle(facet)}</div>
      {facet.series.length === 0 ? (
        <div className="empty-state">No data</div>
      ) : mode === "scatter" ? (
        <ScatterView
          chart={chart}
          facet={facet}
          metricFormatConfig={metricFormatConfig}
        />
      ) : (
        <ComboView
          chart={chart}
          facet={facet}
          metricFormatConfig={metricFormatConfig}
        />
      )}
      {facet.warnings && facet.warnings.length > 0 ? (
        <WarningList warnings={facet.warnings} />
      ) : null}
    </section>
  );
}

function ComboView({
  chart,
  facet,
  metricFormatConfig,
}: {
  chart: ChartData;
  facet: FacetData;
  metricFormatConfig: MetricFormatConfig;
}) {
  const xAxisField = chart.x_axis_field ?? "activity_group";
  const lineMetrics = chart.y_axis_fields.filter((metric) => !isBarMetric(metric));
  const barMetrics = chart.y_axis_fields.filter(isBarMetric);
  const chartHeight = hasCategoryEncoding(chart) ? 238 : 260;

  return (
    <div className="chart-canvas">
      <ResponsiveContainer width="100%" height={chartHeight}>
        <ComposedChart data={facet.series} margin={{ bottom: 18, left: 4, right: 4 }}>
          <CartesianGrid stroke="#E5E7EB" />
          <XAxis
            axisLine={axisLineProps()}
            dataKey={xAxisField}
            tick={axisTickProps()}
            tickLine={axisLineProps("#CBD5E1")}
            {...categoricalAxisProps()}
          />
          {lineMetrics.length > 0 ? (
            <YAxis
              axisLine={axisLineProps(metricColor(lineMetrics[0]) ?? "#0F766E")}
              yAxisId="left"
              orientation="left"
              tick={axisTickProps()}
              tickFormatter={metricValueFormatter(
                lineMetrics[0],
                metricFormatConfig,
              )}
              tickLine={axisLineProps("#CBD5E1")}
              stroke={metricColor(lineMetrics[0]) ?? "#0F766E"}
              width={76}
            />
          ) : null}
          {barMetrics.length > 0 ? (
            <YAxis
              axisLine={axisLineProps(metricColor(barMetrics[0]) ?? "#B45309")}
              yAxisId="right"
              orientation="right"
              tick={axisTickProps()}
              tickFormatter={metricValueFormatter(
                barMetrics[0],
                metricFormatConfig,
              )}
              tickLine={axisLineProps("#CBD5E1")}
              stroke={metricColor(barMetrics[0]) ?? "#B45309"}
              width={82}
            />
          ) : null}
          <Tooltip
            content={
              <MetricCategoryTooltip
                chart={chart}
                metricFormatConfig={metricFormatConfig}
                metrics={chart.y_axis_fields}
                xAxisField={xAxisField}
              />
            }
          />
          <Legend />
          {barMetrics.map((metric) => (
            <Bar
              dataKey={metric}
              fill={metricColor(metric) ?? "#B45309"}
              key={metric}
              name={metricLabel(metric)}
              radius={[3, 3, 0, 0]}
              yAxisId="right"
            >
              {hasCategoryEncoding(chart)
                ? facet.series.map((record, index) => (
                    <Cell
                      fill={categoryFill(
                        chart,
                        record,
                        metricColor(metric) ?? "#B45309",
                        metric,
                      )}
                      key={`${metric}-${index}`}
                    />
                  ))
                : null}
            </Bar>
          ))}
          {lineMetrics.map((metric) => {
            const stroke = metricColor(metric) ?? "#0F766E";
            return (
              <Line
                dataKey={metric}
                dot={(props) => (
                  <CategoryDot
                    chart={chart}
                    cx={Number(props.cx)}
                    cy={Number(props.cy)}
                    fallbackStroke={stroke}
                    payload={props.payload as Record<string, unknown> | undefined}
                    metric={metric}
                  />
                )}
                key={metric}
                name={metricLabel(metric)}
                stroke={stroke}
                strokeWidth={2}
                type="monotone"
                yAxisId="left"
              />
            );
          })}
        </ComposedChart>
      </ResponsiveContainer>
      <CategoryLegend chart={chart} />
    </div>
  );
}

function ScatterView({
  chart,
  facet,
  metricFormatConfig,
}: {
  chart: ChartData;
  facet: FacetData;
  metricFormatConfig: MetricFormatConfig;
}) {
  const scatterXAxisKey =
    chart.y_axis_fields.find((metric) => isBarMetric(metric)) ?? "spend";
  const scatterYAxisKey =
    chart.y_axis_fields.find((metric) => !isBarMetric(metric)) ?? "roi";
  const scatterData = [...facet.series].sort(
    (left, right) =>
      numericValue(left[scatterXAxisKey]) - numericValue(right[scatterXAxisKey]),
  );
  const chartHeight = hasCategoryEncoding(chart) ? 238 : 260;

  return (
    <div className="chart-canvas">
      <ResponsiveContainer width="100%" height={chartHeight}>
        <ScatterChart margin={{ bottom: 18, left: 4, right: 8 }}>
          <CartesianGrid stroke="#E5E7EB" />
          <XAxis
            axisLine={axisLineProps()}
            dataKey={scatterXAxisKey}
            name={metricLabel(scatterXAxisKey)}
            tick={axisTickProps()}
            tickFormatter={metricValueFormatter(
              scatterXAxisKey,
              metricFormatConfig,
            )}
            tickLine={axisLineProps("#CBD5E1")}
            type="number"
          />
          <YAxis
            axisLine={axisLineProps()}
            dataKey={scatterYAxisKey}
            name={metricLabel(scatterYAxisKey)}
            tick={axisTickProps()}
            tickFormatter={metricValueFormatter(
              scatterYAxisKey,
              metricFormatConfig,
            )}
            tickLine={axisLineProps("#CBD5E1")}
            type="number"
            width={76}
          />
          <Tooltip
            content={
              <ScatterTooltip
                chart={chart}
                metricFormatConfig={metricFormatConfig}
                scatterXAxisKey={scatterXAxisKey}
                scatterYAxisKey={scatterYAxisKey}
              />
            }
            cursor={{ strokeDasharray: "3 3" }}
          />
          <Scatter
            data={scatterData}
            fill="#7C3AED"
            name={`${metricLabel(scatterYAxisKey)} by ${metricLabel(scatterXAxisKey)}`}
          >
            {hasCategoryEncoding(chart)
              ? scatterData.map((record, index) => (
                  <Cell
                    fill={categoryFill(chart, record, "#7C3AED", scatterYAxisKey)}
                    key={`scatter-${index}`}
                  />
                ))
              : null}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
      <CategoryLegend chart={chart} />
    </div>
  );
}

function MetricCategoryTooltip({
  active,
  payload,
  label,
  chart,
  metricFormatConfig,
  metrics,
  xAxisField,
}: TooltipProps<number | string, string> & {
  chart: ChartData;
  metricFormatConfig: MetricFormatConfig;
  metrics: string[];
  xAxisField: string;
}) {
  const row = payload?.[0]?.payload as Record<string, unknown> | undefined;
  if (!active || !row) {
    return null;
  }

  const categoryLabel = categoryLabelFromRecord(chart, row);
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">
        {displayValue(row[xAxisField] ?? label)}
      </div>
      {categoryLabel ? (
        <div>{metricLabel(chart.category_in_chart?.metric ?? "roi")} Level: {categoryLabel}</div>
      ) : null}
      {uniqueValues(metrics).map((metric) => (
        <div key={metric}>
          {metricLabel(metric)}: {formatMetricValue(metric, row[metric], metricFormatConfig)}
        </div>
      ))}
    </div>
  );
}

function ScatterTooltip({
  active,
  payload,
  chart,
  metricFormatConfig,
  scatterXAxisKey,
  scatterYAxisKey,
}: TooltipProps<number, string> & {
  chart: ChartData;
  metricFormatConfig: MetricFormatConfig;
  scatterXAxisKey: string;
  scatterYAxisKey: string;
}) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const row = payload[0].payload as Record<string, unknown>;
  const categoryLabel = categoryLabelFromRecord(chart, row);
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">
        {displayValue(row.activity_group ?? row.tactic ?? row.label)}
      </div>
      {categoryLabel ? (
        <div>{metricLabel(chart.category_in_chart?.metric ?? "roi")} Level: {categoryLabel}</div>
      ) : null}
      <div>
        {metricLabel(scatterXAxisKey)}: {" "}
        {formatMetricValue(
          scatterXAxisKey,
          row[scatterXAxisKey],
          metricFormatConfig,
        )}
      </div>
      <div>
        {metricLabel(scatterYAxisKey)}: {" "}
        {formatMetricValue(
          scatterYAxisKey,
          row[scatterYAxisKey],
          metricFormatConfig,
        )}
      </div>
    </div>
  );
}

function uniqueValues(values: string[]): string[] {
  const unique: string[] = [];
  for (const value of values) {
    if (!unique.includes(value)) {
      unique.push(value);
    }
  }
  return unique;
}

function numericValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : Number.POSITIVE_INFINITY;
}
