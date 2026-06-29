import {
  Bar,
  CartesianGrid,
  ComposedChart,
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
  facetTitle,
  isBarMetric,
  metricColor,
  metricLabel,
  metricTooltipFormatter,
  metricValueFormatter,
} from "./renderHelpers";

interface LineBarRendererProps {
  chart: ChartData;
  metricFormatConfig: MetricFormatConfig;
}

export function LineBarRenderer({
  chart,
  metricFormatConfig,
}: LineBarRendererProps) {
  return (
    <div className="facet-grid chart-grid">
      {chart.facets.map((facet) => (
        <LineBarFacet
          key={facet.label}
          chart={chart}
          facet={facet}
          metricFormatConfig={metricFormatConfig}
        />
      ))}
    </div>
  );
}

function LineBarFacet({
  chart,
  facet,
  metricFormatConfig,
}: {
  chart: ChartData;
  facet: FacetData;
  metricFormatConfig: MetricFormatConfig;
}) {
  const xAxisField = chart.x_axis_field ?? "time";
  const lineMetrics = chart.y_axis_fields.filter((metric) => !isBarMetric(metric));
  const barMetrics = chart.y_axis_fields.filter(isBarMetric);

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
      )}
      {facet.warnings && facet.warnings.length > 0 ? (
        <WarningList warnings={facet.warnings} />
      ) : null}
    </section>
  );
}