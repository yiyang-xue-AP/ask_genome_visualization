import type { ChartData, SectionDefinition } from "./types";

export function groupChartsBySection(charts: ChartData[]): SectionDefinition[] {
  const sectionMap: Record<string, ChartData[]> = {};

  for (const chart of charts) {
    const sectionNum = chart.section_num || sectionNumFromChartId(chart.chart_id);
    if (!sectionMap[sectionNum]) {
      sectionMap[sectionNum] = [];
    }
    sectionMap[sectionNum].push(chart);
  }

  const sectionNums = Object.keys(sectionMap);
  sectionNums.sort(compareDottedIds);

  const sections: SectionDefinition[] = [];
  for (const sectionNum of sectionNums) {
    const sectionCharts = sectionMap[sectionNum];
    sectionCharts.sort((left, right) => compareDottedIds(left.chart_id, right.chart_id));
    sections.push({
      sectionNum,
      sectionName: sectionCharts[0]?.section_name || sectionNum,
      charts: sectionCharts,
    });
  }

  return sections;
}

function sectionNumFromChartId(chartId: string): string {
  return chartId.split(".").slice(0, 3).join(".");
}

function compareDottedIds(left: string, right: string): number {
  const leftParts = left.split(".").map(Number);
  const rightParts = right.split(".").map(Number);
  const maxLength = Math.max(leftParts.length, rightParts.length);

  for (let index = 0; index < maxLength; index += 1) {
    const leftValue = leftParts[index] ?? 0;
    const rightValue = rightParts[index] ?? 0;
    if (leftValue !== rightValue) {
      return leftValue - rightValue;
    }
  }

  return 0;
}
