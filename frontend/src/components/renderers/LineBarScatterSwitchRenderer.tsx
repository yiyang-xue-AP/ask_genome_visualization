import { useState } from "react";
import {
  Bar,
  CartesianGrid,
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
import {
  axisLineProps,
  axisTickProps,
  categoricalAxisProps,
  displayValue,
  facetTitle,
  formatMetricValue,
  isBarMetric,
  metricColor,
  metricLabel,
  metricTooltipFormatter,
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

  return (
    <div className="chart-canvas">
      <ResponsiveContainer width="100%" height={260}>
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
          <Tooltip formatter={metricTooltipFormatter(metricFormatConfig)} />
          <Legend />
          {barMetrics.map((metric) => (
            <Bar
              dataKey={metric}
              fill={metricColor(metric) ?? "#B45309"}
              key={metric}
              name={metricLabel(metric)}
              radius={[3, 3, 0, 0]}
              yAxisId="right"
            />
          ))}
          {lineMetrics.map((metric) => (
            <Line
              dataKey={metric}
              dot={{ r: 3 }}
              key={metric}
              name={metricLabel(metric)}
              stroke={metricColor(metric) ?? "#0F766E"}
              strokeWidth={2}
              type="monotone"
              yAxisId="left"
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
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

  return (
    <div className="chart-canvas">
      <ResponsiveContainer width="100%" height={260}>
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
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

function ScatterTooltip({
  active,
  payload,
  metricFormatConfig,
  scatterXAxisKey,
  scatterYAxisKey,
}: TooltipProps<number, string> & {
  metricFormatConfig: MetricFormatConfig;
  scatterXAxisKey: string;
  scatterYAxisKey: string;
}) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const row = payload[0].payload as Record<string, unknown>;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">
        {displayValue(row.activity_group ?? row.tactic ?? row.label)}
      </div>
      <div>
        {metricLabel(scatterXAxisKey)}:{" "}
        {formatMetricValue(
          scatterXAxisKey,
          row[scatterXAxisKey],
          metricFormatConfig,
        )}
      </div>
      <div>
        {metricLabel(scatterYAxisKey)}:{" "}
        {formatMetricValue(
          scatterYAxisKey,
          row[scatterYAxisKey],
          metricFormatConfig,
        )}
      </div>
    </div>
  );
}

function numericValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : Number.POSITIVE_INFINITY;
}