import type { ChartData, MetricFormatConfig } from "../types";
import { BarChartRenderer } from "./renderers/BarChartRenderer";
import { CardsRenderer } from "./renderers/CardsRenderer";
import { GroupedLineBarRenderer } from "./renderers/GroupedLineBarRenderer";
import { LineBarRenderer } from "./renderers/LineBarRenderer";
import { LineBarScatterSwitchRenderer } from "./renderers/LineBarScatterSwitchRenderer";

interface ChartRendererProps {
  chart: ChartData;
  metricFormatConfig: MetricFormatConfig;
  narrative?: string;
  narrativePending?: boolean;
}

export function ChartRenderer({
  chart,
  metricFormatConfig,
  narrative,
  narrativePending,
}: ChartRendererProps) {
  let renderer;
  if (chart.visual_type === "cards") {
    renderer = <CardsRenderer chart={chart} metricFormatConfig={metricFormatConfig} />;
  } else if (chart.visual_type === "bar_chart") {
    renderer = <BarChartRenderer chart={chart} metricFormatConfig={metricFormatConfig} />;
  } else if (chart.visual_type === "line_bar") {
    renderer = <LineBarRenderer chart={chart} metricFormatConfig={metricFormatConfig} />;
  } else if (chart.visual_type === "grouped_line_bar") {
    renderer = <GroupedLineBarRenderer chart={chart} metricFormatConfig={metricFormatConfig} />;
  } else if (chart.visual_type === "line_bar_scatter_switch") {
    renderer = <LineBarScatterSwitchRenderer chart={chart} metricFormatConfig={metricFormatConfig} />;
  } else {
    renderer = <UnsupportedChart chart={chart} metricFormatConfig={metricFormatConfig} />;
  }

  return (
    <article className="chart-block">
      <div className="chart-heading">
        <h3>{chart.chart_title || chart.chart_id}</h3>
        <span>{chart.visual_type}</span>
      </div>
      {chart.warnings && chart.warnings.length > 0 ? (
        <WarningList warnings={chart.warnings} />
      ) : null}
      {narrative ? <p className="narrative-text">{narrative}</p> : null}
      {!narrative && narrativePending ? (
        <p className="narrative-loading">Insights are on the way...</p>
      ) : null}
      {renderer}
    </article>
  );
}

function UnsupportedChart({ chart }: ChartRendererProps) {
  return <div className="empty-state">Unsupported chart type: {chart.visual_type}</div>;
}

export function WarningList({ warnings }: { warnings: string[] }) {
  const visibleWarnings = warnings.filter(shouldDisplayWarning);
  if (visibleWarnings.length === 0) {
    return null;
  }

  return (
    <ul className="warning-list">
      {visibleWarnings.map((warning, index) => (
        <li key={`${warning}-${index}`}>{warning}</li>
      ))}
    </ul>
  );
}

function shouldDisplayWarning(warning: string): boolean {
  return !/^[a-z_]*growth_rate: prior value is missing or zero$/i.test(warning);
}
