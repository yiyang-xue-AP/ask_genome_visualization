"""Read workbook configuration from visualgrid.xlsx without inference."""

import hashlib
import json
import re
from pathlib import Path

from openpyxl import load_workbook

from backend.app.schemas import RawChartRow

CONFIG_SHEET_NAME = "Config"
CHARTS_SHEET_NAME = "Charts"
CHART_ID_COLUMN = "# Chart Item Num"
ALIAS_FIELD_HEADERS = {
    "field",
    "field_name",
    "outcome_field",
    "outcome_field_name",
    "source_field",
    "column",
    "column_name",
    "data_field",
}
ALIAS_VALUE_HEADERS = {
    "alias",
    "field_alias",
    "label",
    "field_label",
    "dropdown_label",
    "display_label",
    "display_name",
}
ALIAS_KEY_PREFIXES = (
    "field_alias",
    "field_label",
    "outcome_field_alias",
    "outcome_field_label",
    "alias",
    "label",
)


def row_hash(row: dict[str, str | None]) -> str:
    """Compute a stable hash over all cell values in one grid row."""

    return hashlib.md5(
        json.dumps(row, sort_keys=True, default=str).encode(),
    ).hexdigest()


def _cell_to_raw_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _headers_from_row(values: tuple[object, ...]) -> list[str]:
    headers = [_cell_to_raw_string(value) for value in values]
    if any(header is None or header == "" for header in headers):
        raise ValueError("Charts sheet header row contains a blank column name")

    normalized_headers = [str(header) for header in headers]
    if len(normalized_headers) != len(set(normalized_headers)):
        raise ValueError("Charts sheet header row contains duplicate column names")

    if CHART_ID_COLUMN not in normalized_headers:
        raise ValueError(f"Charts sheet is missing required column {CHART_ID_COLUMN!r}")

    return normalized_headers


def parse_grid(grid_path: Path) -> list[RawChartRow]:
    """Parse the Charts sheet into raw rows while preserving cell text values."""

    workbook_path = Path(grid_path)
    if not workbook_path.exists():
        raise FileNotFoundError(f"Grid file not found: {workbook_path}")

    workbook = load_workbook(workbook_path, data_only=False, read_only=True)
    try:
        if CHARTS_SHEET_NAME not in workbook.sheetnames:
            raise ValueError(f"Grid file is missing sheet {CHARTS_SHEET_NAME!r}")

        sheet = workbook[CHARTS_SHEET_NAME]
        rows = sheet.iter_rows(values_only=True)
        try:
            header_values = next(rows)
        except StopIteration as exc:
            raise ValueError("Charts sheet is empty") from exc

        headers = _headers_from_row(header_values)
        raw_rows: list[RawChartRow] = []

        for values in rows:
            columns = {
                header: _cell_to_raw_string(values[index]) if index < len(values) else None
                for index, header in enumerate(headers)
            }
            if all(value is None for value in columns.values()):
                continue

            raw_rows.append(RawChartRow(columns=columns, row_hash=row_hash(columns)))

        return raw_rows
    finally:
        workbook.close()


def parse_config_aliases(grid_path: Path) -> dict[str, str]:
    """Parse optional dropdown field aliases from the Config sheet.

    Supported table format:
    Field Name | Alias
    country    | Country

    Supported key-value format:
    field_alias.country | Country
    """

    workbook_path = Path(grid_path)
    if not workbook_path.exists():
        raise FileNotFoundError(f"Grid file not found: {workbook_path}")

    workbook = load_workbook(workbook_path, data_only=True, read_only=True)
    try:
        if CONFIG_SHEET_NAME not in workbook.sheetnames:
            return {}

        sheet = workbook[CONFIG_SHEET_NAME]
        aliases: dict[str, str] = {}
        active_field_index: int | None = None
        active_alias_index: int | None = None

        for values in sheet.iter_rows(values_only=True):
            cells = [_cell_to_raw_string(value) for value in values]
            if not any(_clean_config_value(cell) for cell in cells):
                continue

            if _is_config_section_marker(cells):
                active_field_index = None
                active_alias_index = None

            header_indices = _config_alias_header_indices(cells)
            if header_indices is not None:
                active_field_index, active_alias_index = header_indices
                continue

            _parse_config_key_value_alias(cells, aliases)

            if active_field_index is None or active_alias_index is None:
                continue
            if max(active_field_index, active_alias_index) >= len(cells):
                continue

            field_name = _clean_config_value(cells[active_field_index])
            alias = _clean_config_value(cells[active_alias_index])
            if field_name and alias:
                aliases[field_name] = alias

        return aliases
    finally:
        workbook.close()


def _config_alias_header_indices(cells: list[str | None]) -> tuple[int, int] | None:
    normalized_cells = [_normalize_config_key(cell) for cell in cells]
    field_index = _first_matching_index(normalized_cells, ALIAS_FIELD_HEADERS)
    alias_index = _first_matching_index(normalized_cells, ALIAS_VALUE_HEADERS)
    if field_index is None or alias_index is None:
        return None
    if field_index == alias_index:
        return None
    return field_index, alias_index


def _first_matching_index(
    values: list[str],
    candidates: set[str],
) -> int | None:
    for index, value in enumerate(values):
        if value in candidates:
            return index
    return None


def _parse_config_key_value_alias(
    cells: list[str | None],
    aliases: dict[str, str],
) -> None:
    if len(cells) < 2:
        return

    key = _normalize_config_key(cells[0])
    alias = _clean_config_value(cells[1])
    if not key or not alias:
        return

    for prefix in ALIAS_KEY_PREFIXES:
        marker = f"{prefix}_"
        if key.startswith(marker) and len(key) > len(marker):
            aliases[key[len(marker) :]] = alias
            return


def _is_config_section_marker(cells: list[str | None]) -> bool:
    first_cell = _clean_config_value(cells[0] if cells else None)
    return bool(first_cell and first_cell.lower().startswith("section "))


def _clean_config_value(value: str | None) -> str:
    return "" if value is None else value.strip()


def _normalize_config_key(value: str | None) -> str:
    clean_value = _clean_config_value(value).lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", clean_value)
    return normalized.strip("_")
