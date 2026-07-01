import type { ChartData, FacetData, MetricFormatConfig } from "../../types";

export function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      return "n/a";
    }
    return new Intl.NumberFormat("en-US", {
      maximumFractionDigits: 2,
    }).format(value);
  }
  return String(value);
}

export function formatMetricValue(
  metric: string,
  value: unknown,
  metricFormatConfig: MetricFormatConfig,
): string {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  if (typeof value !== "number") {
    return String(value);
  }
  if (!Number.isFinite(value)) {
    return "n/a";
  }

  if (metric === "growth_rate" || metric.endsWith("_growth_rate")) {
    return `${formatNumber(value * 100, 1)}%`;
  }

  const rule = metricFormatConfig[normalizeMetricKey(metric)];
  if (!rule) {
    return formatNumber(value, 2);
  }

  if (rule.unitSign === "$") {
    const sign = value < 0 ? "-" : "";
    return `${sign}$${formatNumber(Math.abs(value), rule.keepDigit)}`;
  }

  const formatted = formatNumber(value, rule.keepDigit);
  if (rule.unitSign === "%") {
    return `${formatted}%`;
  }
  if (rule.unitSign) {
    return `${rule.unitSign}${formatted}`;
  }
  return formatted;
}

export function metricValueFormatter(
  metric: string,
  metricFormatConfig: MetricFormatConfig,
): (value: unknown) => string {
  return (value: unknown) => formatMetricValue(metric, value, metricFormatConfig);
}

export function metricTooltipFormatter(metricFormatConfig: MetricFormatConfig) {
  return (
    value: unknown,
    name: unknown,
    item: { dataKey?: unknown },
  ): [string, string] => {
    const metric =
      typeof item.dataKey === "string" ? item.dataKey : normalizeMetricKey(name);
    return [formatMetricValue(metric, value, metricFormatConfig), String(name)];
  };
}

export function formatGrowthRate(value: number): string {
  return `${formatNumber(Math.abs(value) * 100, 1)}%`;
}

export function facetTitle(facet: FacetData): string {
  return facet.label || "all";
}

const categoryPalette = [
  "#047857",
  "#2563EB",
  "#D97706",
  "#DC2626",
  "#7C3AED",
  "#0891B2",
  "#475569",
];

export function hasCategoryEncoding(chart: ChartData): boolean {
  return Boolean(chart.category_in_chart?.labels?.length);
}

export function isCategoryEncodedMetric(chart: ChartData, metric: string): boolean {
  if (!hasCategoryEncoding(chart) || !chart.category_in_chart) {
    return false;
  }
  return metricBase(metric) === chart.category_in_chart.metric;
}

export function categoryLabels(chart: ChartData): string[] {
  return chart.category_in_chart?.labels ?? [];
}

export function categoryLabelField(chart: ChartData): string {
  return chart.category_in_chart?.label_field ?? "category_label";
}

export function categoryLabelFromRecord(
  chart: ChartData,
  record: Record<string, unknown> | undefined,
): string | null {
  if (!record) {
    return null;
  }
  const value = record[categoryLabelField(chart)];
  return value === null || value === undefined || value === "" ? null : String(value);
}

export function categoryColor(
  label: unknown,
  labels: string[],
  fallback = "#64748B",
): string {
  if (label === null || label === undefined || label === "") {
    return fallback;
  }
  const normalizedLabel = String(label);
  const index = labels.indexOf(normalizedLabel);
  if (index < 0) {
    return fallback;
  }
  return categoryPalette[index % categoryPalette.length];
}

export function categoryLegendItems(chart: ChartData): Array<{ label: string; color: string }> {
  const labels = categoryLabels(chart);
  return labels.map((label) => ({ label, color: categoryColor(label, labels) }));
}
export function isBarMetric(metric: string): boolean {
  return metric === "spend" || metric === "spend_growth_rate";
}

const metricColors: Record<string, string> = {
  roi: "#0F766E",
  spend: "#B45309",
  response: "#7C3AED",
  cpm: "#BE123C",
  activity: "#2563EB",
};

export function metricColor(metric: string): string | undefined {
  return metricColors[metricBase(metric)];
}

export function metricLabel(metric: string): string {
  const labels: Record<string, string> = {
    roi: "ROI",
    spend: "Spend",
    response: "Response",
    cpm: "CPM",
    activity: "Activity",
    roi_growth_rate: "ROI change rate",
    spend_growth_rate: "Spend change rate",
    response_growth_rate: "Response change rate",
    cpm_growth_rate: "CPM change rate",
    activity_growth_rate: "Activity change rate",
  };
  return labels[metric] ?? metric.replace(/_/g, " ");
}

function metricBase(metric: string): string {
  return metric.replace(/_growth_rate$/, "");
}

function normalizeMetricKey(value: unknown): string {
  return String(value)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function formatNumber(value: number, digits: number): string {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);
}

export function axisTickProps() {
  return {
    fill: "#475569",
    fontSize: 12,
  };
}

export function categoricalAxisProps() {
  return {
    angle: -24,
    height: 68,
    interval: 0 as const,
    minTickGap: 0,
    textAnchor: "end" as const,
  };
}

export function axisLineProps(color = "#94A3B8") {
  return {
    stroke: color,
    strokeWidth: 1,
  };
}