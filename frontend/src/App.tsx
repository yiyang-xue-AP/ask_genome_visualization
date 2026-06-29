import { useCallback, useEffect, useRef, useState } from "react";

import {
  compileGrid,
  fetchNarrative,
  fetchTabData,
} from "./apiClient";
import { ChartRenderer } from "./components/ChartRenderer";
import { DropdownPanel } from "./components/DropdownPanel";
import { fetchDashboardConfig } from "./config";
import { groupChartsBySection } from "./layoutEngine";
import type {
  ChartData,
  DashboardConfig,
  DropdownState,
  TabCacheEntry,
} from "./types";

type LoadMode = "cache-first" | "refresh";

export function App() {
  const tabCache = useRef<Record<string, TabCacheEntry>>({});
  const autoCompileAttempted = useRef(false);
  const activeTabNumRef = useRef("");
  const [dashboardConfig, setDashboardConfig] = useState<DashboardConfig | null>(null);
  const [activeTabNum, setActiveTabNum] = useState("");
  const [dropdownState, setDropdownState] = useState<DropdownState | null>(null);
  const [chartData, setChartData] = useState<ChartData[]>([]);
  const [narratives, setNarratives] = useState<Record<string, string>>({});
  const [pendingNarratives, setPendingNarratives] = useState<Record<string, true>>({});
  const [autoFilteredFields, setAutoFilteredFields] = useState<string[]>([]);
  const [availableOutcomeFieldOptions, setAvailableOutcomeFieldOptions] =
    useState<Record<string, string[]> | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const applyCacheEntry = useCallback((entry: TabCacheEntry) => {
    setChartData(entry.chartData);
    setDropdownState(entry.dropdownState);
    setAutoFilteredFields(entry.autoFilteredFields);
    setAvailableOutcomeFieldOptions(entry.availableOutcomeFieldOptions);
    setNarratives(entry.narratives);
    setPendingNarratives({});
  }, []);

  const loadTab = useCallback(
    async (tabNum: string, nextDropdownState: DropdownState, mode: LoadMode) => {
      if (mode === "cache-first") {
        const cachedEntry = tabCache.current[tabNum];
        if (cachedEntry) {
          applyCacheEntry(cachedEntry);
          return;
        }
      }

      setIsLoading(true);
      setErrorMessage(null);
      try {
        const response = await fetchTabData(tabNum, nextDropdownState).catch(
          async (error) => {
            if (shouldAutoCompile(error) && !autoCompileAttempted.current) {
              autoCompileAttempted.current = true;
              await compileGrid();
              return fetchTabData(tabNum, nextDropdownState);
            }
            throw error;
          },
        );
        const normalizedDropdownState =
          response.normalized_dropdown_state ?? nextDropdownState;
        const nextAvailableOutcomeFieldOptions =
          response.available_outcome_field_options ?? {};
        const cacheEntry: TabCacheEntry = {
          chartData: response.charts,
          narratives: {},
          dropdownState: normalizedDropdownState,
          autoFilteredFields: response.auto_filtered_fields,
          availableOutcomeFieldOptions: nextAvailableOutcomeFieldOptions,
        };

        tabCache.current[tabNum] = cacheEntry;
        setChartData(response.charts);
        setNarratives({});
        setPendingNarratives({});
        setDropdownState(normalizedDropdownState);
        setAutoFilteredFields(response.auto_filtered_fields);
        setAvailableOutcomeFieldOptions(nextAvailableOutcomeFieldOptions);
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Request failed");
      } finally {
        setIsLoading(false);
      }
    },
    [applyCacheEntry],
  );

  useEffect(() => {
    activeTabNumRef.current = activeTabNum;
  }, [activeTabNum]);

  useEffect(() => {
    async function loadInitialConfig() {
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const config = await fetchDashboardConfig();
        const initialTabNum = config.tabs[0]?.tabNum ?? "";
        setDashboardConfig(config);
        activeTabNumRef.current = initialTabNum;
        setActiveTabNum(initialTabNum);
        setDropdownState(config.defaultDropdownState);
        setAvailableOutcomeFieldOptions(config.outcomeFieldOptions);

        if (initialTabNum) {
          await loadTab(initialTabNum, config.defaultDropdownState, "refresh");
        }
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Config request failed");
      } finally {
        setIsLoading(false);
      }
    }

    void loadInitialConfig();
  }, [loadTab]);

  useEffect(() => {
    const cacheEntry = tabCache.current[activeTabNum];
    if (!cacheEntry || chartData.length === 0) {
      return;
    }

    for (const chart of chartData) {
      if (Object.prototype.hasOwnProperty.call(cacheEntry.narratives, chart.chart_id)) {
        continue;
      }

      const facets = chart.facets.map((facet) => ({
        label: facet.label,
        calc_result: facet.calc_result,
        series: facet.series,
        formula_log: facet.formula_log ?? "",
      }));

      const requestTabNum = activeTabNum;
      setPendingNarratives((current) => ({ ...current, [chart.chart_id]: true }));
      void fetchNarrative(chart.chart_id, facets)
        .then((response) => {
          const latestEntry = tabCache.current[requestTabNum];
          if (latestEntry !== cacheEntry) {
            return;
          }

          latestEntry.narratives[chart.chart_id] = response.narrative;
          if (activeTabNumRef.current === requestTabNum) {
            setNarratives({ ...latestEntry.narratives });
            setPendingNarratives((current) => withoutKey(current, chart.chart_id));
          }
        })
        .catch(() => {
          const latestEntry = tabCache.current[requestTabNum];
          if (latestEntry !== cacheEntry) {
            return;
          }
          if (activeTabNumRef.current === requestTabNum) {
            setPendingNarratives((current) => withoutKey(current, chart.chart_id));
          }
        });
    }
  }, [activeTabNum, chartData]);

  function handleTabSelect(tabNum: string) {
    if (dropdownState === null) {
      return;
    }
    activeTabNumRef.current = tabNum;
    setActiveTabNum(tabNum);
    const cachedEntry = tabCache.current[tabNum];
    if (cachedEntry) {
      applyCacheEntry(cachedEntry);
      return;
    }
    void loadTab(tabNum, dropdownState, "refresh");
  }

  function handleDropdownConfirm(nextDropdownState: DropdownState) {
    setDropdownState(nextDropdownState);
    void loadTab(activeTabNum, nextDropdownState, "refresh");
  }

  async function handleCompile() {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      await compileGrid();
      autoCompileAttempted.current = true;
      const config = await fetchDashboardConfig();
      const nextActiveTabNum = activeTabNum || config.tabs[0]?.tabNum || "";
      const nextDropdownState = resolveDropdownState(dropdownState, config);
      setDashboardConfig(config);
      activeTabNumRef.current = nextActiveTabNum;
      setActiveTabNum(nextActiveTabNum);
      setDropdownState(nextDropdownState);
      setAvailableOutcomeFieldOptions(config.outcomeFieldOptions);
      tabCache.current = {};
      if (nextActiveTabNum) {
        await loadTab(nextActiveTabNum, nextDropdownState, "refresh");
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Compile failed");
    } finally {
      setIsLoading(false);
    }
  }

  const sections = groupChartsBySection(chartData);
  const tabs = dashboardConfig?.tabs ?? [];
  const activeTab = tabs.find((tab) => tab.tabNum === activeTabNum) ?? tabs[0];

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1>ROI / Efficiency</h1>
          <p>{activeTab?.tabName ?? "Loading configuration"}</p>
        </div>
        <button className="primary-button" type="button" onClick={handleCompile}>
          Compile Grid
        </button>
      </header>

      <nav className="tab-list" aria-label="Dashboard tabs">
        {tabs.map((tab) => (
          <button
            className={tab.tabNum === activeTabNum ? "active" : ""}
            key={tab.tabNum}
            type="button"
            onClick={() => handleTabSelect(tab.tabNum)}
          >
            {tab.tabName}
          </button>
        ))}
      </nav>

      {dashboardConfig && dropdownState ? (
        <DropdownPanel
          autoFilteredFields={autoFilteredFields}
          dropdownState={dropdownState}
          metricOptions={dashboardConfig.metricOptions}
          availableOutcomeFieldOptions={
            availableOutcomeFieldOptions ?? dashboardConfig.outcomeFieldOptions
          }
          outcomeFieldLabels={dashboardConfig.outcomeFieldLabels}
          validOutcomeCombinations={
            dashboardConfig.outcomeFieldCombinationsByTab[activeTabNum] ?? []
          }
          outcomeFieldOptions={dashboardConfig.outcomeFieldOptions}
          periodDefaults={dashboardConfig.periodDefaults}
          periodOptions={dashboardConfig.periodOptions}
          onConfirm={handleDropdownConfirm}
        />
      ) : null}

      {errorMessage ? <div className="error-banner">{errorMessage}</div> : null}
      {isLoading ? <div className="loading-bar">Loading</div> : null}

      <div className="dashboard-layout">
        {sections.length === 0 && !isLoading ? (
          <div className="empty-state">No chart data</div>
        ) : null}
        {sections.map((section) => (
          <section className="dashboard-section" key={section.sectionNum}>
            <div className="section-heading">
              <span>{section.sectionNum}</span>
              <h2>{section.sectionName}</h2>
            </div>
            <div className="chart-list">
              {section.charts.map((chart) => (
                <ChartRenderer
                  chart={chart}
                  key={chart.chart_id}
                  metricFormatConfig={dashboardConfig?.metricFormatConfig ?? {}}
                  narrativePending={Boolean(pendingNarratives[chart.chart_id])}
                  narrative={narratives[chart.chart_id]}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
    </main>
  );
}

function shouldAutoCompile(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  return error.message.includes("No compiled ChartSpecs found");
}

function withoutKey<TValue>(
  record: Record<string, TValue>,
  keyToRemove: string,
): Record<string, TValue> {
  const nextRecord = { ...record };
  delete nextRecord[keyToRemove];
  return nextRecord;
}

function resolveDropdownState(
  currentState: DropdownState | null,
  config: DashboardConfig,
): DropdownState {
  if (currentState === null) {
    return config.defaultDropdownState;
  }

  const periodOptions = config.periodOptions[currentState.period_granularity] ?? [];
  const hasValidPeriods = [
    currentState.snapshot_current_period,
    currentState.snapshot_prior_period,
    currentState.trend_start_period,
    currentState.trend_end_period,
  ].every((period) => periodOptions.includes(period));

  const hasValidMetric = config.metricOptions.includes(currentState.metric);
  if (!hasValidPeriods || !hasValidMetric) {
    return config.defaultDropdownState;
  }

  const outcomeFields: DropdownState["outcome_fields"] = {};
  for (const [fieldName, selectedValues] of Object.entries(currentState.outcome_fields)) {
    const validValues = new Set(config.outcomeFieldOptions[fieldName] ?? []);
    const retainedValues = selectedValues.filter((value) => validValues.has(value));
    if (retainedValues.length > 0) {
      outcomeFields[fieldName] = retainedValues;
    }
  }

  return {
    ...currentState,
    outcome_fields: outcomeFields,
  };
}
