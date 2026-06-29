import type {
  CompileResponse,
  DashboardConfig,
  DropdownState,
  NarrativeFacetRequest,
  NarrativeResponse,
  MetricFormatConfig,
  PeriodGranularity,
  PeriodDefault,
  TabResponse,
} from "./types";

const API_BASE = "/api";
const REQUEST_TIMEOUT_MS = 30000;
const COMPILE_TIMEOUT_MS = 600000;
const NARRATIVE_TIMEOUT_MS = 120000;

interface DashboardConfigApiResponse {
  tabs: Array<{ tab_num: string; tab_name: string }>;
  outcome_field_options: Record<string, string[]>;
  outcome_field_labels?: Record<string, string>;
  outcome_field_combinations_by_tab?: Record<string, Array<Record<string, string>>>;
  metric_format_config?: Record<string, { unit_sign: string; keep_digit: number }>;
  metric_options: string[];
  period_options: Partial<Record<PeriodGranularity, string[]>>;
  period_defaults: Partial<Record<PeriodGranularity, PeriodDefault>>;
  default_dropdown_state: DropdownState;
}

async function postJson<TResponse>(
  path: string,
  payload: unknown,
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<TResponse> {
  const response = await fetchWithTimeout(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  }, timeoutMs);

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<TResponse>;
}

export async function fetchDashboardConfig(): Promise<DashboardConfig> {
  const response = await fetchWithTimeout(`${API_BASE}/dashboard-config`);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  const payload = (await response.json()) as DashboardConfigApiResponse;
  return {
    tabs: payload.tabs.map((tab) => ({
      tabNum: tab.tab_num,
      tabName: tab.tab_name,
    })),
    outcomeFieldOptions: payload.outcome_field_options,
    outcomeFieldLabels: payload.outcome_field_labels ?? {},
    outcomeFieldCombinationsByTab: payload.outcome_field_combinations_by_tab ?? {},
    metricFormatConfig: mapMetricFormatConfig(payload.metric_format_config),
    metricOptions: payload.metric_options,
    periodOptions: payload.period_options,
    periodDefaults: payload.period_defaults,
    defaultDropdownState: payload.default_dropdown_state,
  };
}

function mapMetricFormatConfig(
  config: DashboardConfigApiResponse["metric_format_config"],
): MetricFormatConfig {
  const mapped: MetricFormatConfig = {};
  for (const [metric, rule] of Object.entries(config ?? {})) {
    mapped[metric] = {
      unitSign: rule.unit_sign,
      keepDigit: rule.keep_digit,
    };
  }
  return mapped;
}
async function fetchWithTimeout(
  input: RequestInfo | URL,
  init: RequestInit = {},
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(input, {
      ...init,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Backend request timed out. Please restart the backend server.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export function compileGrid(gridPath = "visualgrid.xlsx"): Promise<CompileResponse> {
  return postJson<CompileResponse>(
    "/compile",
    { grid_path: gridPath },
    COMPILE_TIMEOUT_MS,
  );
}

export function fetchTabData(
  tabNum: string,
  dropdownState: DropdownState,
): Promise<TabResponse> {
  return postJson<TabResponse>(`/tab/${tabNum}`, {
    dropdown_state: dropdownState,
  });
}

export function fetchNarrative(
  chartId: string,
  facets: NarrativeFacetRequest[],
): Promise<NarrativeResponse> {
  return postJson<NarrativeResponse>(
    `/narrative/${chartId}`,
    { facets },
    NARRATIVE_TIMEOUT_MS,
  );
}
