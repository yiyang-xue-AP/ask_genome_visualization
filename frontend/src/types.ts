export interface FacetData {
  label: string;
  filters: Record<string, string>;
  series: Record<string, unknown>[];
  calc_result: Record<string, unknown>;
  warnings?: string[];
  formula_log?: string;
}

export interface ChartData {
  chart_id: string;
  chart_title?: string;
  section_num: string;
  section_name: string;
  visual_type: string;
  x_axis_field: string | null;
  series_field?: string | null;
  y_axis_fields: string[];
  left_y_axis_fields?: string[];
  right_y_axis_fields?: string[];
  auto_filtered_fields: string[];
  facets: FacetData[];
  warnings?: string[];
}

export interface TabCacheEntry {
  chartData: ChartData[];
  narratives: Record<string, string>;
  dropdownState: DropdownState;
  autoFilteredFields: string[];
  availableOutcomeFieldOptions: Record<string, string[]>;
}

export interface DropdownState {
  outcome_fields: Record<string, string[]>;
  metric: string;
  period_granularity: PeriodGranularity;
  snapshot_current_period: string;
  snapshot_prior_period: string;
  trend_start_period: string;
  trend_end_period: string;
}

export type PeriodGranularity = "year" | "half_year" | "quarter" | "month";

export interface PeriodDefault {
  snapshot_current_period: string;
  snapshot_prior_period: string;
  trend_start_period: string;
  trend_end_period: string;
}

export interface MetricFormatRule {
  unitSign: string;
  keepDigit: number;
}

export type MetricFormatConfig = Record<string, MetricFormatRule>;

export interface DashboardConfig {
  tabs: TabDefinition[];
  outcomeFieldOptions: Record<string, string[]>;
  outcomeFieldLabels: Record<string, string>;
  outcomeFieldCombinationsByTab: Record<string, Array<Record<string, string>>>;
  metricFormatConfig: MetricFormatConfig;
  metricOptions: string[];
  periodOptions: Partial<Record<PeriodGranularity, string[]>>;
  periodDefaults: Partial<Record<PeriodGranularity, PeriodDefault>>;
  defaultDropdownState: DropdownState;
}

export interface TabResponse {
  tab_num: string;
  auto_filtered_fields: string[];
  available_outcome_field_options?: Record<string, string[]>;
  normalized_dropdown_state?: DropdownState;
  charts: ChartData[];
}

export interface CompileResponse {
  chart_specs: unknown[];
  validation_report: unknown;
  recompiled_ids: string[];
  cached_ids: string[];
}

export interface NarrativeFacetRequest {
  label: string;
  calc_result: Record<string, unknown>;
  series: Record<string, unknown>[];
  formula_log: string;
}

export interface NarrativeResponse {
  narrative: string;
  data_references: Array<{
    facet: string;
    metric: string;
    value: unknown;
  }>;
}

export interface TabDefinition {
  tabNum: string;
  tabName: string;
}

export interface SectionDefinition {
  sectionNum: string;
  sectionName: string;
  charts: ChartData[];
}
