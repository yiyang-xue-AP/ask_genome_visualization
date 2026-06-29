import { useEffect, useState } from "react";

import type { DropdownState, PeriodDefault, PeriodGranularity } from "../types";

const MAX_VALUES_PER_OUTCOME_FIELD = 2;
const MAX_FACET_COMBINATION_PRODUCT = 6;

interface DropdownPanelProps {
  dropdownState: DropdownState;
  autoFilteredFields: string[];
  outcomeFieldOptions: Record<string, string[]>;
  outcomeFieldLabels: Record<string, string>;
  validOutcomeCombinations: Array<Record<string, string>>;
  availableOutcomeFieldOptions: Record<string, string[]>;
  metricOptions: string[];
  periodOptions: Partial<Record<PeriodGranularity, string[]>>;
  periodDefaults: Partial<Record<PeriodGranularity, PeriodDefault>>;
  onConfirm: (nextState: DropdownState) => void;
}

export function DropdownPanel({
  dropdownState,
  autoFilteredFields,
  outcomeFieldOptions,
  outcomeFieldLabels,
  validOutcomeCombinations,
  availableOutcomeFieldOptions,
  metricOptions,
  periodOptions,
  periodDefaults,
  onConfirm,
}: DropdownPanelProps) {
  const [draftDropdownState, setDraftDropdownState] = useState(dropdownState);

  useEffect(() => {
    setDraftDropdownState(dropdownState);
  }, [dropdownState]);

  const visibleOutcomeFields: string[] = [];
  for (const fieldName of Object.keys(outcomeFieldOptions)) {
    if (!autoFilteredFields.includes(fieldName)) {
      visibleOutcomeFields.push(fieldName);
    }
  }
  const activePeriodOptions = periodOptions[draftDropdownState.period_granularity] ?? [];
  const hasPendingChanges = !dropdownStatesEqual(dropdownState, draftDropdownState);
  const draftAvailableOutcomeFieldOptions = buildDraftAvailableOutcomeFieldOptions(
    visibleOutcomeFields,
    outcomeFieldOptions,
    availableOutcomeFieldOptions,
    validOutcomeCombinations,
    draftDropdownState.outcome_fields,
  );

  function updateState(partial: Partial<DropdownState>) {
    setDraftDropdownState((currentState) => ({ ...currentState, ...partial }));
  }

  function updateGranularity(nextGranularity: PeriodGranularity) {
    const defaults = periodDefaults[nextGranularity];
    updateState({
      period_granularity: nextGranularity,
      ...(defaults ?? {}),
    });
  }

  function toggleOutcomeValue(fieldName: string, value: string) {
    const currentValues = draftDropdownState.outcome_fields[fieldName] ?? [];
    if (disabledReason(fieldName, value) !== null) {
      return;
    }

    const nextValues = currentValues.includes(value)
      ? currentValues.filter((currentValue) => currentValue !== value)
      : [...currentValues, value];

    setDraftDropdownState({
      ...draftDropdownState,
      outcome_fields: {
        ...draftDropdownState.outcome_fields,
        [fieldName]: nextValues,
      },
    });
  }

  function disabledReason(fieldName: string, value: string): string | null {
    const currentValues = draftDropdownState.outcome_fields[fieldName] ?? [];
    if (currentValues.includes(value)) {
      return null;
    }

    const availableValues = draftAvailableOutcomeFieldOptions[fieldName] ?? [];
    if (!availableValues.includes(value)) {
      return "No data for current selection";
    }

    const nextValues = [...currentValues, value];
    if (nextValues.length > MAX_VALUES_PER_OUTCOME_FIELD) {
      return `Select up to ${MAX_VALUES_PER_OUTCOME_FIELD} values per field`;
    }

    const nextOutcomeFields = {
      ...draftDropdownState.outcome_fields,
      [fieldName]: nextValues,
    };
    const nextCombinationProduct = combinationProduct(nextOutcomeFields);
    if (nextCombinationProduct > MAX_FACET_COMBINATION_PRODUCT) {
      return `Facet combinations cannot exceed ${MAX_FACET_COMBINATION_PRODUCT}`;
    }

    return null;
  }

  function resetDraft() {
    setDraftDropdownState(dropdownState);
  }

  return (
    <aside className="dropdown-panel" aria-label="Dashboard controls">
      <div className="control-row">
        <label>
          <span>Metric</span>
          <select
            value={draftDropdownState.metric}
            onChange={(event) => updateState({ metric: event.target.value })}
          >
            {metricOptions.map((metric) => (
              <option key={metric} value={metric}>
                {metric.toUpperCase()}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Period Granularity</span>
          <select
            value={draftDropdownState.period_granularity}
            onChange={(event) =>
              updateGranularity(event.target.value as PeriodGranularity)
            }
          >
            {(["year", "half_year", "quarter", "month"] as PeriodGranularity[]).map(
              (granularity) => (
                <option
                  disabled={(periodOptions[granularity] ?? []).length === 0}
                  key={granularity}
                  value={granularity}
                >
                  {labelForGranularity(granularity)}
                </option>
              ),
            )}
          </select>
        </label>
      </div>

      <div className="control-grid">
        <PeriodSelect
          label="Snapshot Current"
          value={draftDropdownState.snapshot_current_period}
          options={activePeriodOptions}
          onChange={(value) => updateState({ snapshot_current_period: value })}
        />
        <PeriodSelect
          label="Snapshot Prior"
          value={draftDropdownState.snapshot_prior_period}
          options={activePeriodOptions}
          onChange={(value) => updateState({ snapshot_prior_period: value })}
        />
        <PeriodSelect
          label="Trend Start"
          value={draftDropdownState.trend_start_period}
          options={activePeriodOptions}
          onChange={(value) => updateState({ trend_start_period: value })}
        />
        <PeriodSelect
          label="Trend End"
          value={draftDropdownState.trend_end_period}
          options={activePeriodOptions}
          onChange={(value) => updateState({ trend_end_period: value })}
        />
      </div>

      <div className="outcome-controls">
        {visibleOutcomeFields.map((fieldName) => (
          <fieldset key={fieldName}>
            <legend>{outcomeFieldLabels[fieldName] ?? fieldName}</legend>
            <div className="checkbox-list">
              {outcomeFieldOptions[fieldName].map((value) => {
                const isChecked = (
                  draftDropdownState.outcome_fields[fieldName] ?? []
                ).includes(value);
                const reason = disabledReason(fieldName, value);
                const isDisabled = reason !== null && !isChecked;

                return (
                  <label
                    key={value}
                    className={`checkbox-row${isDisabled ? " unavailable" : ""}`}
                    title={isDisabled ? reason ?? undefined : undefined}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      disabled={isDisabled}
                      onChange={() => toggleOutcomeValue(fieldName, value)}
                    />
                    <span>{value}</span>
                  </label>
                );
              })}
            </div>
          </fieldset>
        ))}
      </div>

      <div className="dropdown-actions">
        <button
          className="secondary-button"
          disabled={!hasPendingChanges}
          type="button"
          onClick={resetDraft}
        >
          Reset
        </button>
        <button
          className="primary-button"
          disabled={!hasPendingChanges}
          type="button"
          onClick={() => onConfirm(draftDropdownState)}
        >
          Confirm
        </button>
      </div>
    </aside>
  );
}

function combinationProduct(outcomeFields: Record<string, string[]>): number {
  let product = 1;
  for (const values of Object.values(outcomeFields)) {
    if (values.length > 0) {
      product *= values.length;
    }
  }
  return product;
}

function buildDraftAvailableOutcomeFieldOptions(
  visibleOutcomeFields: string[],
  outcomeFieldOptions: Record<string, string[]>,
  availableOutcomeFieldOptions: Record<string, string[]>,
  validOutcomeCombinations: Array<Record<string, string>>,
  selectedOutcomeFields: Record<string, string[]>,
): Record<string, string[]> {
  if (validOutcomeCombinations.length === 0) {
    return availableOutcomeFieldOptions;
  }

  const availableOptions: Record<string, string[]> = {};
  for (const fieldName of Object.keys(outcomeFieldOptions)) {
    const matchingRecords = validOutcomeCombinations.filter((record) =>
      recordMatchesSelections(record, selectedOutcomeFields, fieldName),
    );
    const values = new Set(
      matchingRecords
        .map((record) => record[fieldName])
        .filter((value): value is string => typeof value === "string" && value !== ""),
    );
    availableOptions[fieldName] = outcomeFieldOptions[fieldName].filter((value) =>
      values.has(value),
    );
  }

  for (const fieldName of visibleOutcomeFields) {
    availableOptions[fieldName] = availableOptions[fieldName] ?? [];
  }
  return availableOptions;
}

function recordMatchesSelections(
  record: Record<string, string>,
  selectedOutcomeFields: Record<string, string[]>,
  excludedFieldName: string,
): boolean {
  for (const [fieldName, selectedValues] of Object.entries(selectedOutcomeFields)) {
    if (fieldName === excludedFieldName || selectedValues.length === 0) {
      continue;
    }
    if (!selectedValues.includes(record[fieldName])) {
      return false;
    }
  }
  return true;
}

function dropdownStatesEqual(left: DropdownState, right: DropdownState): boolean {
  return (
    left.metric === right.metric &&
    left.period_granularity === right.period_granularity &&
    left.snapshot_current_period === right.snapshot_current_period &&
    left.snapshot_prior_period === right.snapshot_prior_period &&
    left.trend_start_period === right.trend_start_period &&
    left.trend_end_period === right.trend_end_period &&
    JSON.stringify(normalizeOutcomeFields(left.outcome_fields)) ===
      JSON.stringify(normalizeOutcomeFields(right.outcome_fields))
  );
}

function normalizeOutcomeFields(
  outcomeFields: Record<string, string[]>,
): Record<string, string[]> {
  const normalized: Record<string, string[]> = {};
  for (const fieldName of Object.keys(outcomeFields).sort()) {
    normalized[fieldName] = [...outcomeFields[fieldName]].sort();
  }
  return normalized;
}

function PeriodSelect({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: string[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((period) => (
          <option key={period} value={period}>
            {period}
          </option>
        ))}
      </select>
    </label>
  );
}

function labelForGranularity(granularity: PeriodGranularity): string {
  const labels: Record<PeriodGranularity, string> = {
    year: "Year",
    half_year: "Half Year",
    quarter: "Quarter",
    month: "Month",
  };

  return labels[granularity];
}
