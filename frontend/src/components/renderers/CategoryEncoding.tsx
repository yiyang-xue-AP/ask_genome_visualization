import type { ChartData } from "../../types";
import {
  categoryColor,
  categoryLabelFromRecord,
  categoryLabels,
  categoryLegendItems,
  hasCategoryEncoding,
  isCategoryEncodedMetric,
} from "./renderHelpers";

export function CategoryLegend({ chart }: { chart: ChartData }) {
  const items = categoryLegendItems(chart);
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="category-legend" aria-label="Metric category legend">
      {items.map((item) => (
        <span className="category-legend-item" key={item.label}>
          <span
            className="category-legend-swatch"
            style={{ backgroundColor: item.color }}
          />
          {item.label}
        </span>
      ))}
    </div>
  );
}

export function categoryFill(
  chart: ChartData,
  record: Record<string, unknown> | undefined,
  fallback: string,
  metric?: string,
): string {
  if (!hasCategoryEncoding(chart)) {
    return fallback;
  }
  if (metric && !isCategoryEncodedMetric(chart, metric)) {
    return fallback;
  }
  return categoryColor(categoryLabelFromRecord(chart, record), categoryLabels(chart), fallback);
}

export function CategoryDot({
  chart,
  cx,
  cy,
  payload,
  fallbackStroke,
  metric,
}: {
  chart: ChartData;
  cx?: number;
  cy?: number;
  payload?: Record<string, unknown>;
  fallbackStroke: string;
  metric: string;
}) {
  if (
    typeof cx !== "number" ||
    typeof cy !== "number" ||
    !Number.isFinite(cx) ||
    !Number.isFinite(cy)
  ) {
    return null;
  }

  const fill = categoryFill(chart, payload, "#FFFFFF", metric);
  return (
    <circle
      cx={cx}
      cy={cy}
      fill={fill}
      r={3.5}
      stroke={fallbackStroke}
      strokeWidth={1.8}
    />
  );
}
