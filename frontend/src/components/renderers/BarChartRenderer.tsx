import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TooltipProps } from "recharts";

import type { ChartData, FacetData, MetricFormatConfig } from "../../types";
import { WarningList } from "../ChartRenderer";
import { CategoryLegend, categoryFill } from "./CategoryEncoding";
import {
  axisLineProps,
  axisTickProps,
  categoricalAxisProps,
  categoryLabelFromRecord,
  displayValue,
  facetTitle,
  formatMetricValue,
  hasCategoryEncoding,
  metricColor,
  metricLabel,
  metricValueFormatter,
} from "./renderHelpers";

interface BarChartRendererProps {
  chart: ChartData;
  metricFormatConfig: MetricFormatConfig;
}

export function BarChartRenderer({
  chart,
  metricFormatConfig,
}: BarChartRendererProps) {
  return (
    <div className="facet-grid chart-grid">
      {chart.facets.map((facet) => (
        <BarChartFacet
          key={facet.label}
          chart={chart}
          facet={facet}
          metricFormatConfig={metricFormatConfig}
        />
      ))}
    </div>
  );
}

function BarChartFacet({
  chart,
  facet,
  metricFormatConfig,
}: {
  chart: ChartData;
  facet: FacetData;
  metricFormatConfig: MetricFormatConfig;
}) {
  const xAxisField = chart.x_axis_field ?? "activity_group";
  const leftAxisMetrics =
    chart.left_y_axis_fields && chart.left_y_axis_fields.length > 0
      ? chart.left_y_axis_fields
      : chart.y_axis_fields.filter(isLeftAxisMetric);
  const rightAxisMetrics =
    chart.right_y_axis_fields && chart.right_y_axis_fields.length > 0
      ? chart.right_y_axis_fields
      : chart.y_axis_fields.filter((metric) => !leftAxisMetrics.includes(metric));
  const chartHeight = hasCategoryEncoding(chart) ? 238 : 260;

  return (
    <section className="facet-panel">
      <div className="facet-title">{facetTitle(facet)}</div>
      {facet.series.length === 0 ? (
        <div className="empty-state">No data</div>
      ) : (
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
              {leftAxisMetrics.length > 0 ? (
                <YAxis
                  axisLine={axisLineProps(metricColor(leftAxisMetrics[0]) ?? "#0F766E")}
                  orientation="left"
                  stroke={metricColor(leftAxisMetrics[0]) ?? "#0F766E"}
                  tick={axisTickProps()}
                  tickFormatter={metricValueFormatter(
                    leftAxisMetrics[0],
                    metricFormatConfig,
                  )}
                  tickLine={axisLineProps("#CBD5E1")}
                  width={76}
                  yAxisId="left"
                />
              ) : null}
              {rightAxisMetrics.length > 0 ? (
                <YAxis
                  axisLine={axisLineProps(metricColor(rightAxisMetrics[0]) ?? "#7C3AED")}
                  orientation="right"
                  stroke={metricColor(rightAxisMetrics[0]) ?? "#7C3AED"}
                  tick={axisTickProps()}
                  tickFormatter={metricValueFormatter(
                    rightAxisMetrics[0],
                    metricFormatConfig,
                  )}
                  tickLine={axisLineProps("#CBD5E1")}
                  width={82}
                  yAxisId="right"
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
              {leftAxisMetrics.map((metric) => (
                <Bar
                  dataKey={metric}
                  fill={metricColor(metric) ?? "#0F766E"}
                  key={metric}
                  name={metricLabel(metric)}
                  radius={[3, 3, 0, 0]}
                  yAxisId="left"
                >
                  {hasCategoryEncoding(chart)
                    ? facet.series.map((record, index) => (
                        <Cell
                          fill={categoryFill(
                            chart,
                            record,
                            metricColor(metric) ?? "#0F766E",
                            metric,
                          )}
                          key={`${metric}-${index}`}
                        />
                      ))
                    : null}
                </Bar>
              ))}
              {rightAxisMetrics.map((metric) => (
                <Bar
                  dataKey={metric}
                  fill={metricColor(metric) ?? "#7C3AED"}
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
                            metricColor(metric) ?? "#7C3AED",
                            metric,
                          )}
                          key={`${metric}-${index}`}
                        />
                      ))
                    : null}
                </Bar>
              ))}
            </ComposedChart>
          </ResponsiveContainer>
          <CategoryLegend chart={chart} />
        </div>
      )}
      {facet.warnings && facet.warnings.length > 0 ? (
        <WarningList warnings={facet.warnings} />
      ) : null}
    </section>
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

function uniqueValues(values: string[]): string[] {
  const unique: string[] = [];
  for (const value of values) {
    if (!unique.includes(value)) {
      unique.push(value);
    }
  }
  return unique;
}

function isLeftAxisMetric(metric: string): boolean {
  return metric === "roi" || metric === "roi_growth_rate";
}
