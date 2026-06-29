import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
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
  facetTitle,
  metricColor,
  metricLabel,
  metricTooltipFormatter,
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

  return (
    <section className="facet-panel">
      <div className="facet-title">{facetTitle(facet)}</div>
      {facet.series.length === 0 ? (
        <div className="empty-state">No data</div>
      ) : (
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
              <Tooltip formatter={metricTooltipFormatter(metricFormatConfig)} />
              <Legend />
              {leftAxisMetrics.map((metric) => (
                <Bar
                  dataKey={metric}
                  fill={metricColor(metric) ?? "#0F766E"}
                  key={metric}
                  name={metricLabel(metric)}
                  radius={[3, 3, 0, 0]}
                  yAxisId="left"
                />
              ))}
              {rightAxisMetrics.map((metric) => (
                <Bar
                  dataKey={metric}
                  fill={metricColor(metric) ?? "#7C3AED"}
                  key={metric}
                  name={metricLabel(metric)}
                  radius={[3, 3, 0, 0]}
                  yAxisId="right"
                />
              ))}
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

function isLeftAxisMetric(metric: string): boolean {
  return metric === "roi" || metric === "roi_growth_rate";
}