import type { ChartData, FacetData, MetricFormatConfig } from "../../types";
import { WarningList } from "../ChartRenderer";
import {
  facetTitle,
  formatGrowthRate,
  formatMetricValue,
  metricLabel,
} from "./renderHelpers";

interface CardsRendererProps {
  chart: ChartData;
  metricFormatConfig: MetricFormatConfig;
}

export function CardsRenderer({ chart, metricFormatConfig }: CardsRendererProps) {
  return (
    <div className="facet-grid cards-grid">
      {chart.facets.map((facet) => (
        <KpiFacet
          key={facet.label}
          chart={chart}
          facet={facet}
          metricFormatConfig={metricFormatConfig}
        />
      ))}
    </div>
  );
}

function KpiFacet({
  chart,
  facet,
  metricFormatConfig,
}: {
  chart: ChartData;
  facet: FacetData;
  metricFormatConfig: MetricFormatConfig;
}) {
  return (
    <section className="facet-panel">
      <div className="facet-title">{facetTitle(facet)}</div>
      <dl className="kpi-card-list">
        {chart.y_axis_fields.map((metric) => (
          <div className="kpi-card" key={metric}>
            <dt>{metricLabel(metric)}</dt>
            <dd>{formatMetricValue(metric, facet.calc_result[metric], metricFormatConfig)}</dd>
            <GrowthBadge value={growthValueForMetric(facet, metric)} />
          </div>
        ))}
      </dl>
      {facet.warnings && facet.warnings.length > 0 ? (
        <WarningList warnings={facet.warnings} />
      ) : null}
    </section>
  );
}

function GrowthBadge({ value }: { value: unknown }) {
  if (typeof value !== "number") {
    return <span className="kpi-growth muted">n/a</span>;
  }

  const direction = value > 0 ? "positive" : value < 0 ? "negative" : "neutral";
  const arrow = value > 0 ? "▲" : value < 0 ? "▼" : "■";
  const percent = formatGrowthRate(value);

  return <span className={`kpi-growth ${direction}`}>{`${arrow} ${percent}`}</span>;
}

function growthValueForMetric(facet: FacetData, metric: string): unknown {
  const metricGrowthKey = `${metric}_growth_rate`;
  if (metricGrowthKey in facet.calc_result) {
    return facet.calc_result[metricGrowthKey];
  }
  if (metric === "roi" && "growth_rate" in facet.calc_result) {
    return facet.calc_result.growth_rate;
  }
  return null;
}

