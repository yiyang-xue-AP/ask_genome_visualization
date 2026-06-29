"""Compile-time validation for ChartSpec objects."""

from __future__ import annotations

import csv
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from backend.app.schemas import ChartSpec, TabSpec, ValidationReport
from backend.app.tab_configs import TAB_CONFIGS

SNAPSHOT_PRIOR_MESSAGE = (
    "snapshot: prior-year period not found, growth_rate suppressed, "
    "rendering current period only"
)
TREND_PERIOD_MESSAGE = "trend: fewer than 3 periods in dataset, chart will be hidden"


@dataclass(frozen=True, slots=True)
class DataSourceProfile:
    columns: set[str]
    distinct_period_count: int | None = None
    has_prior_year_period: bool | None = None


def load_data_source_profiles(
    data_paths: Mapping[str, Path],
) -> dict[str, DataSourceProfile]:
    """Read data source headers and period availability for validation only."""

    profiles: dict[str, DataSourceProfile] = {}
    for source, path in data_paths.items():
        profiles[source] = _load_single_profile(path)
    return profiles


def validate_chart_specs(
    specs: Sequence[ChartSpec],
    tab_specs: Mapping[str, TabSpec] | None = None,
    data_profiles: Mapping[str, DataSourceProfile] | None = None,
) -> ValidationReport:
    """Validate compiled chart specs against tab rules and data profiles."""

    active_tab_specs = TAB_CONFIGS if tab_specs is None else tab_specs
    chart_id_counts = Counter(spec.chart_id for spec in specs)
    reports = []

    for spec in specs:
        messages: list[str] = []
        is_error = False

        if chart_id_counts[spec.chart_id] > 1:
            is_error = True
            messages.append(f"chart_id {spec.chart_id!r} is duplicated in current grid")

        tab_spec = active_tab_specs.get(spec.tab.num)
        if tab_spec is None:
            is_error = True
            messages.append(f"tab.num {spec.tab.num!r} has no matching TabSpec")
        else:
            messages.extend(
                _validate_tab_filter_fields(tab_spec, spec, data_profiles),
            )
            if messages and any("is not present" in message for message in messages):
                is_error = True

        source_profile = None if data_profiles is None else data_profiles.get(spec.source)
        if data_profiles is not None and source_profile is None:
            is_error = True
            messages.append(f"source {spec.source!r} has no data profile")

        if source_profile is not None:
            time_error, time_messages = _validate_time_scope(spec, source_profile)
            messages.extend(time_messages)
            is_error = is_error or time_error

        messages.extend(spec.validation_warnings)

        if is_error:
            status = "error"
        elif messages:
            status = "warning"
        else:
            status = "ok"

        reports.append(
            {"chart_id": spec.chart_id, "status": status, "messages": messages},
        )

    ok = sum(1 for report in reports if report["status"] == "ok")
    warning = sum(1 for report in reports if report["status"] == "warning")
    error = sum(1 for report in reports if report["status"] == "error")

    return ValidationReport(
        total=len(specs),
        ok=ok,
        warning=warning,
        error=error,
        charts=reports,
    )


def _load_single_profile(path: Path) -> DataSourceProfile:
    periods: set[str] = set()
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return DataSourceProfile(columns=set())

        columns = set(reader.fieldnames)
        if "time" in columns:
            for row in reader:
                period = row.get("time")
                if period:
                    periods.add(period)

    return DataSourceProfile(
        columns=columns,
        distinct_period_count=len(periods) if periods else None,
        has_prior_year_period=_has_prior_year_pair(periods) if periods else None,
    )


def _validate_tab_filter_fields(
    tab_spec: TabSpec,
    spec: ChartSpec,
    data_profiles: Mapping[str, DataSourceProfile] | None,
) -> list[str]:
    if data_profiles is None:
        return []

    source_profile = data_profiles.get(spec.source)
    if source_profile is None:
        return []

    messages = []
    for condition in tab_spec.tactic_filter:
        if condition.field not in source_profile.columns:
            messages.append(
                f"tactic_filter field {condition.field!r} is not present in "
                f"source {spec.source!r}"
            )
    return messages


def _validate_time_scope(
    spec: ChartSpec,
    source_profile: DataSourceProfile,
) -> tuple[bool, list[str]]:
    if spec.time_scope == "snapshot" and source_profile.has_prior_year_period is False:
        return False, [SNAPSHOT_PRIOR_MESSAGE]

    if (
        spec.time_scope == "trend"
        and source_profile.distinct_period_count is not None
        and source_profile.distinct_period_count < 3
    ):
        return True, [TREND_PERIOD_MESSAGE]

    return False, []


def _has_prior_year_pair(periods: set[str]) -> bool:
    for period in periods:
        prior_period = _prior_year_period(period)
        if prior_period in periods:
            return True
    return False


def _prior_year_period(period: str) -> str | None:
    match = re.search(r"(\d{4})(?!.*\d)", period)
    if match is None:
        return None

    year = int(match.group(1))
    return f"{period[: match.start()]}{year - 1}{period[match.end() :]}"
