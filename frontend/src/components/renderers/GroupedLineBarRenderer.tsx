import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Customized,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

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
  metricValueFormatter,
} from "./renderHelpers";

interface GroupedLineBarRendererProps {
  chart: ChartData;
  metricFormatConfig: MetricFormatConfig;
}

type SeriesMapping = {
  dataKey: string;
  metric: string;
  seriesIndex: number;
  seriesValue: string;
};
type ScaleWithBandwidth = ((value: string | number) => number) & {
  bandwidth?: () => number;
};
type ChartAxisMap = Record<
  string,
  {
    scale?: ScaleWithBandwidth;
  }
>;
type ChartOffset = {
  left: number;
  width: number;
};
type CustomizedChartProps = {
  offset?: ChartOffset;
  xAxisMap?: ChartAxisMap;
  yAxisMap?: ChartAxisMap;
};
type OverlayPoint = {
  x: number;
  y: number;
  seriesIndex: number;
};
type TooltipEntry = {
  payload?: Record<string, unknown>;
};

export function GroupedLineBarRenderer({
  chart,
  metricFormatConfig,
}: GroupedLineBarRendererProps) {
  return (
    <div className="facet-grid chart-grid">
      {chart.facets.map((facet) => (
        <GroupedLineBarFacet
          key={facet.label}
          chart={chart}
          facet={facet}
          metricFormatConfig={metricFormatConfig}
        />
      ))}
    </div>
  );
}

function GroupedLineBarFacet({
  chart,
  facet,
  metricFormatConfig,
}: {
  chart: ChartData;
  facet: FacetData;
  metricFormatConfig: MetricFormatConfig;
}) {
  const xAxisField = chart.x_axis_field ?? "activity_group";
  const seriesField = chart.series_field ?? "time";
  const wideData = buildGroupedData(
    facet.series,
    xAxisField,
    seriesField,
    chart.y_axis_fields,
  );
  const leftAxisMetrics =
    chart.left_y_axis_fields && chart.left_y_axis_fields.length > 0
      ? chart.left_y_axis_fields
      : chart.y_axis_fields.filter(isBarMetric);
  const rightAxisMetrics =
    chart.right_y_axis_fields && chart.right_y_axis_fields.length > 0
      ? chart.right_y_axis_fields
      : chart.y_axis_fields.filter((metric) => !leftAxisMetrics.includes(metric));
  const barMappings = wideData.mappings.filter((mapping) => isBarMetric(mapping.metric));
  const lineMappings = wideData.mappings.filter((mapping) => !isBarMetric(mapping.metric));
  const lineMetrics = chart.y_axis_fields.filter((metric) => !isBarMetric(metric));
  const primaryLegendMetric = barMappings[0]?.metric;

  return (
    <section className="facet-panel">
      <div className="facet-title">{facetTitle(facet)}</div>
      {wideData.rows.length === 0 ? (
        <div className="empty-state">No data</div>
      ) : (
        <div className="chart-canvas">
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={wideData.rows} margin={{ bottom: 18, left: 4, right: 4 }}>
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
                  axisLine={axisLineProps(metricColor(leftAxisMetrics[0]) ?? "#B45309")}
                  orientation="left"
                  stroke={metricColor(leftAxisMetrics[0]) ?? "#B45309"}
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
                  axisLine={axisLineProps(metricColor(rightAxisMetrics[0]) ?? "#0F766E")}
                  orientation="right"
                  stroke={metricColor(rightAxisMetrics[0]) ?? "#0F766E"}
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
                  <GroupedLineTooltip
                    mappings={wideData.mappings}
                    metricFormatConfig={metricFormatConfig}
                    xAxisField={xAxisField}
                  />
                }
              />
              <Legend />
              {barMappings.map((mapping) => (
                <Bar
                  dataKey={mapping.dataKey}
                  fill={seriesColor(mapping.seriesIndex)}
                  key={mapping.dataKey}
                  legendType={
                    mapping.metric === primaryLegendMetric ? "rect" : "none"
                  }
                  name={mapping.seriesValue}
                  radius={[3, 3, 0, 0]}
                  yAxisId={axisIdForMetric(mapping.metric, leftAxisMetrics)}
                />
              ))}
              {lineMappings.map((mapping) => (
                <Line
                  activeDot={false}
                  dataKey={mapping.dataKey}
                  dot={false}
                  isAnimationActive={false}
                  key={`${mapping.dataKey}-domain`}
                  legendType="none"
                  stroke="transparent"
                  strokeOpacity={0}
                  yAxisId={axisIdForMetric(mapping.metric, leftAxisMetrics)}
                />
              ))}
              <Customized
                component={(props: CustomizedChartProps) => (
                  <GroupedLineOverlay
                    chartProps={props}
                    leftAxisMetrics={leftAxisMetrics}
                    lineMetrics={lineMetrics}
                    rows={wideData.rows}
                    seriesValues={wideData.seriesValues}
                    xAxisField={xAxisField}
                  />
                )}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
      {facet.warnings && facet.warnings.length > 0 ? (
        <WarningList warnings={facet.warnings} />
      ) : null}
    </section>
  );
}

function GroupedLineTooltip({
  active,
  payload,
  mappings,
  metricFormatConfig,
  xAxisField,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  mappings: SeriesMapping[];
  metricFormatConfig: MetricFormatConfig;
  xAxisField: string;
}) {
  const row = payload?.[0]?.payload;
  if (!active || !row) {
    return null;
  }

  const seriesValues = uniqueValues(mappings.map((mapping) => mapping.seriesValue));
  const metrics = uniqueValues(mappings.map((mapping) => mapping.metric));

  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">{displayValue(row[xAxisField])}</div>
      {seriesValues.map((seriesValue) => (
        <div key={seriesValue}>
          <strong>{seriesValue}</strong>
          {metrics.map((metric) => (
            <div key={`${seriesValue}-${metric}`}>
              {metricLabel(metric)}:{" "}
              {formatMetricValue(
                metric,
                row[groupedDataKey(metric, seriesValue)],
                metricFormatConfig,
              )}
            </div>
          ))}
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

function buildGroupedData(
  series: Record<string, unknown>[],
  xAxisField: string,
  seriesField: string,
  metrics: string[],
): {
  rows: Record<string, unknown>[];
  mappings: SeriesMapping[];
  seriesValues: string[];
} {
  const rowByCategory = new Map<string, Record<string, unknown>>();
  const seriesValues: string[] = [];
  const mappings: SeriesMapping[] = [];

  for (const record of series) {
    const category = stringValue(record[xAxisField]);
    const seriesValue = stringValue(record[seriesField]);
    if (!category || !seriesValue) {
      continue;
    }

    if (!rowByCategory.has(category)) {
      rowByCategory.set(category, { [xAxisField]: category });
    }
    if (!seriesValues.includes(seriesValue)) {
      seriesValues.push(seriesValue);
    }

    const row = rowByCategory.get(category);
    if (!row) {
      continue;
    }

    for (const metric of metrics) {
      const dataKey = groupedDataKey(metric, seriesValue);
      row[dataKey] = record[metric];
    }
  }

  const sortedSeriesValues = [...seriesValues].sort(compareSeriesValues);
  for (const metric of metrics) {
    sortedSeriesValues.forEach((seriesValue, seriesIndex) => {
      mappings.push({
        dataKey: groupedDataKey(metric, seriesValue),
        metric,
        seriesIndex,
        seriesValue,
      });
    });
  }

  return {
    rows: [...rowByCategory.values()],
    mappings,
    seriesValues: sortedSeriesValues,
  };
}

function GroupedLineOverlay({
  chartProps,
  leftAxisMetrics,
  lineMetrics,
  rows,
  seriesValues,
  xAxisField,
}: {
  chartProps: CustomizedChartProps;
  leftAxisMetrics: string[];
  lineMetrics: string[];
  rows: Record<string, unknown>[];
  seriesValues: string[];
  xAxisField: string;
}) {
  if (rows.length === 0 || seriesValues.length === 0) {
    return null;
  }

  return (
    <g className="grouped-line-overlay">
      {lineMetrics.map((metric) =>
        rows.map((row, rowIndex) => {
          const yScale = yScaleForMetric(chartProps.yAxisMap, metric, leftAxisMetrics);
          if (!yScale) {
            return null;
          }

          const points = seriesValues
            .map((seriesValue, seriesIndex) => {
              const value = numericValue(row[groupedDataKey(metric, seriesValue)]);
              if (value === null) {
                return null;
              }
              return {
                x: groupedPointX(
                  chartProps,
                  row,
                  rowIndex,
                  rows.length,
                  seriesIndex,
                  seriesValues.length,
                  xAxisField,
                ),
                y: yScale(value),
                seriesIndex,
              };
            })
            .filter(isOverlayPoint);

          if (points.length === 0) {
            return null;
          }

          return (
            <g key={`${metric}-${rowIndex}`}>
              {points.length > 1 ? (
                <path
                  d={linePath(points)}
                  fill="none"
                  stroke={metricColor(metric) ?? "#0F766E"}
                  strokeWidth={2}
                />
              ) : null}
              {points.map((point) => (
                <circle
                  cx={point.x}
                  cy={point.y}
                  fill="#FFFFFF"
                  key={`${metric}-${rowIndex}-${point.seriesIndex}`}
                  r={3}
                  stroke={metricColor(metric) ?? "#0F766E"}
                  strokeWidth={2}
                />
              ))}
            </g>
          );
        }),
      )}
    </g>
  );
}

function yScaleForMetric(
  yAxisMap: ChartAxisMap | undefined,
  metric: string,
  leftAxisMetrics: string[],
): ((value: number) => number) | null {
  const axisId = axisIdForMetric(metric, leftAxisMetrics);
  const scale = yAxisMap?.[axisId]?.scale;
  return typeof scale === "function" ? scale : null;
}

function groupedPointX(
  chartProps: CustomizedChartProps,
  row: Record<string, unknown>,
  rowIndex: number,
  rowCount: number,
  seriesIndex: number,
  seriesCount: number,
  xAxisField: string,
): number {
  const xAxis = firstAxis(chartProps.xAxisMap);
  const xScale = xAxis?.scale;
  const category = stringValue(row[xAxisField]);
  const fallbackCategoryWidth = chartProps.offset
    ? chartProps.offset.width / rowCount
    : 0;
  const categoryLeft =
    xScale && category
      ? xScale(category)
      : (chartProps.offset?.left ?? 0) + rowIndex * fallbackCategoryWidth;
  const categoryWidth = xScale?.bandwidth?.() ?? fallbackCategoryWidth;
  const groupWidth = categoryWidth * 0.6;
  const firstPointOffset =
    seriesCount > 1 ? categoryWidth / 2 - groupWidth / 2 : categoryWidth / 2;
  const step = seriesCount > 1 ? groupWidth / (seriesCount - 1) : 0;
  return categoryLeft + firstPointOffset + seriesIndex * step;
}

function firstAxis(axisMap: ChartAxisMap | undefined) {
  return axisMap ? Object.values(axisMap)[0] : undefined;
}

function linePath(points: OverlayPoint[]): string {
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x},${point.y}`)
    .join(" ");
}

function isOverlayPoint(point: OverlayPoint | null): point is OverlayPoint {
  return point !== null;
}

function numericValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function groupedDataKey(metric: string, seriesValue: string): string {
  return `${metric}__${seriesValue.replace(/[^a-zA-Z0-9]+/g, "_")}`;
}

function stringValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  return String(value);
}

function axisIdForMetric(metric: string, leftAxisMetrics: string[]): "left" | "right" {
  return leftAxisMetrics.includes(metric) ? "left" : "right";
}

function seriesColor(seriesIndex: number): string {
  const colors = ["#74A9CF", "#1F78B4", "#A6CEE3", "#0F766E", "#B45309", "#7C3AED"];
  return colors[seriesIndex % colors.length];
}

function compareSeriesValues(left: string, right: string): number {
  const leftKey = periodSortKey(left);
  const rightKey = periodSortKey(right);
  if (leftKey !== rightKey) {
    return leftKey - rightKey;
  }
  return left.localeCompare(right);
}

function periodSortKey(value: string): number {
  const yearMatch = value.match(/(20\d{2}|19\d{2})/);
  const year = yearMatch ? Number(yearMatch[1]) : 0;
  const quarterMatch = value.match(/quarter\s*(\d)|q\s*(\d)/i);
  const quarter = quarterMatch ? Number(quarterMatch[1] ?? quarterMatch[2]) : 0;
  return year * 10 + quarter;
}
