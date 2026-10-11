"""Bounded calculations over already selected, parsed data tables.

This module does no file I/O and never runs expressions, spreadsheet formulas,
code, processes, or network requests. Spreadsheet parsers must provide a cached
value, or None with a warning when that value is unavailable. A formula string
is an invalid numeric value; it is never interpreted here.

Null and blank cells are missing. Other invalid cells in a selected numeric
column fail the operation rather than being silently omitted. Equality filters
use literal strings/booleans/null; numeric filter values also match numeric text
from CSV files. Ordering filters compare numbers, and missing cells do not match.
"""
from __future__ import annotations

from decimal import (
    Context, Decimal, DivisionByZero, Inexact, InvalidOperation, Overflow,
    ROUND_HALF_EVEN, localcontext,
)
import math
import re


DATA_TOOL_NAME = "star_data_analyze"
MAX_DATASETS = 64
MAX_ROWS = 50_000
MAX_PROFILE_COLUMNS = 40
MAX_PROFILE_CELLS = 200_000
MAX_COLUMNS = 256
MAX_FILTERS = 4
MAX_GROUPS = 100
MAX_LABEL_CHARS = 200
MAX_SOURCE_CHARS = 2_048
MAX_NUMERIC_CHARS = 128
MAX_INTEGER_DIGITS = 100
MAX_DECIMAL_PLACES = 100
MAX_WARNINGS = 20
MAX_WARNING_CHARS = 1_000
MAX_RESULT_CHARS = 512
_SUM_PRECISION = MAX_INTEGER_DIGITS + MAX_DECIMAL_PLACES + 20
_CALC_CONTEXT = Context(
    prec=_SUM_PRECISION, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999,
    capitals=1, clamp=0, traps=[InvalidOperation, DivisionByZero, Overflow],
)
_OPERATIONS = {"count", "sum", "mean", "min", "max", "profile"}
_FILTER_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte"}
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


def data_tool_schema() -> dict:
    """OpenAI function definition; the gateway binds datasets independently."""
    scalar = {"type": ["string", "number", "boolean", "null"]}
    return {
        "type": "function",
        "function": {
            "name": DATA_TOOL_NAME,
            "description": (
                "Calculate exact count, sum, mean, min, max, or a bounded quality profile "
                "from an attached data table. Use exact dataset IDs and column names. "
                "Aggregates allow bounded filters and grouping; profile reports missing, "
                "numeric, text, boolean, and formula-looking cells without interpreting formulas. "
                "Calculations use Decimal; input warnings and partial evidence remain visible."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string", "minLength": 1, "maxLength": 256},
                    "operation": {"type": "string", "enum": sorted(_OPERATIONS)},
                    "column": {
                        "type": "string", "minLength": 1, "maxLength": MAX_LABEL_CHARS,
                        "description": "Exact numeric column for aggregate operations; optional for profile (otherwise profiles all columns). Omit for count.",
                    },
                    "group_by": {
                        "type": "string", "minLength": 1, "maxLength": MAX_LABEL_CHARS,
                        "description": "Optional exact column name. At most 100 distinct groups.",
                    },
                    "filters": {
                        "type": "array", "maxItems": MAX_FILTERS,
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string", "minLength": 1, "maxLength": MAX_LABEL_CHARS},
                                "op": {"type": "string", "enum": sorted(_FILTER_OPERATORS)},
                                "value": scalar,
                            },
                            "required": ["column", "op", "value"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["dataset_id", "operation"],
                "additionalProperties": False,
            },
        },
    }


def _label(value, label: str, maximum: int = MAX_LABEL_CHARS) -> str:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} must be a nonblank string of at most {maximum} characters")
    return value


def _scalar(value, label: str) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    raise ValueError(f"{label} must be a finite JSON scalar")


def _numeric(value, label: str) -> Decimal | None:
    if value is None or (type(value) is str and not value.strip()):
        return None
    if type(value) is bool:
        raise ValueError(f"{label}: booleans are not numeric values")
    if type(value) not in (str, int, float):
        raise ValueError(f"{label}: expected a number or numeric string")
    if type(value) is float and not math.isfinite(value):
        raise ValueError(f"{label}: numeric values must be finite")
    try:
        text = str(value).strip()
    except ValueError as exc:
        raise ValueError(f"{label}: numeric value exceeds the supported size") from exc
    if text.startswith("="):
        raise ValueError(f"{label}: formulas are never recalculated; supply a cached value or null with a warning")
    if len(text) > MAX_NUMERIC_CHARS or not _NUMBER.fullmatch(text):
        raise ValueError(f"{label}: invalid or oversized numeric value")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"{label}: invalid numeric value") from exc
    if not number.is_finite():
        raise ValueError(f"{label}: numeric values must be finite")
    exponent = number.as_tuple().exponent
    if max(0, -exponent) > MAX_DECIMAL_PLACES or max(1, number.adjusted() + 1) > MAX_INTEGER_DIGITS:
        raise ValueError(f"{label}: numeric scale or magnitude exceeds the supported limit")
    return number


def _decimal_text(value: Decimal) -> str:
    if value.is_zero():
        return "0"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if len(text) > MAX_RESULT_CHARS:
        raise ValueError("Calculated value exceeds the output size limit")
    return text


def _dataset(datasets, dataset_id: str) -> dict:
    if type(datasets) is not list or len(datasets) > MAX_DATASETS:
        raise ValueError(f"Datasets must be a list of at most {MAX_DATASETS} attached tables")
    matches = [item for item in datasets if type(item) is dict and item.get("id") == dataset_id]
    if not matches:
        raise ValueError("Dataset id is not among the attached tables")
    if len(matches) != 1:
        raise ValueError("Dataset id is ambiguous")
    table = matches[0]
    _label(table.get("name"), "Dataset name")
    _label(table.get("source"), "Dataset source", MAX_SOURCE_CHARS)
    columns, rows = table.get("columns"), table.get("rows")
    if type(columns) is not list or not 1 <= len(columns) <= MAX_COLUMNS:
        raise ValueError(f"Dataset must have 1 to {MAX_COLUMNS} columns")
    for column in columns:
        _label(column, "Dataset column")
    if len(set(columns)) != len(columns):
        raise ValueError("Dataset column names must be unique")
    if type(rows) is not list or len(rows) > MAX_ROWS:
        raise ValueError(f"Dataset must contain at most {MAX_ROWS} rows")
    for row_index, row in enumerate(rows, start=1):
        if type(row) is not list or len(row) != len(columns):
            raise ValueError(f"Dataset row {row_index} does not match its columns")
        for cell in row:
            _scalar(cell, f"Dataset row {row_index} cell")
    warnings = table.get("warnings")
    if type(warnings) is not list or len(warnings) > 1_000 or any(type(item) is not str for item in warnings):
        raise ValueError("Dataset warnings must be a bounded list of strings")
    row_sources = table.get('row_sources')
    if row_sources is not None and (type(row_sources) is not list or len(row_sources) != len(rows)
            or any(type(source) is not str or len(source) > MAX_SOURCE_CHARS for source in row_sources)):
        raise ValueError('Row sources must identify each dataset row within the source-size limit')
    return table


def _column(columns: list[str], name, label: str) -> int:
    _label(name, label)
    try:
        return columns.index(name)
    except ValueError as exc:
        raise ValueError(f"{label} is not an exact column name in this dataset") from exc


def _filters(columns: list[str], filters) -> list[tuple[int, str, object]]:
    if type(filters) is not list or len(filters) > MAX_FILTERS:
        raise ValueError(f"Filters must be a list of at most {MAX_FILTERS} items")
    prepared = []
    for item in filters:
        if type(item) is not dict or set(item) != {"column", "op", "value"}:
            raise ValueError("Each filter must contain only column, op, and value")
        index = _column(columns, item["column"], "Filter column")
        op, value = item["op"], item["value"]
        if type(op) is not str or op not in _FILTER_OPERATORS:
            raise ValueError("Unsupported filter operation")
        _scalar(value, "Filter value")
        if type(value) is str and len(value) > MAX_WARNING_CHARS:
            raise ValueError("Filter string exceeds the supported size")
        if op in {"gt", "gte", "lt", "lte"} or type(value) in (int, float):
            value = _numeric(value, "Filter value")
            if value is None:
                raise ValueError("Numeric filter requires a nonmissing numeric value")
        prepared.append((index, op, value))
    return prepared


def _matches(row: list, prepared: list[tuple[int, str, object]], row_number: int) -> bool:
    for index, op, value in prepared:
        actual = row[index]
        if isinstance(value, Decimal):
            actual = _numeric(actual, f"Filter row {row_number}")
            if actual is None:
                # Missing values do not satisfy any numeric comparison, including ne.
                return False
        else:
            # Literal values must have the same JSON type: False is not zero.
            same = type(actual) is type(value) and actual == value
            if (op == "eq" and not same) or (op == "ne" and same):
                return False
            continue
        comparison = {
            "eq": actual == value, "ne": actual != value,
            "gt": actual > value, "gte": actual >= value,
            "lt": actual < value, "lte": actual <= value,
        }[op]
        if not comparison:
            return False
    return True


def _group_key(value) -> tuple:
    _scalar(value, "Group key")
    if type(value) is str:
        if len(value) > MAX_LABEL_CHARS:
            raise ValueError("Group key exceeds the output size limit")
        return ("string", value)
    if type(value) in (int, float):
        return ("number", _numeric(value, "Group key"))
    return (type(value).__name__, value)


def _bucket() -> dict:
    return {"selected_rows": 0, "used_rows": 0, "missing_rows": 0, "total": Decimal(0), "min": None, "max": None}


def _add(bucket: dict, value: Decimal | None, operation: str) -> None:
    bucket["selected_rows"] += 1
    if operation == "count":
        bucket["used_rows"] += 1
    elif value is None:
        bucket["missing_rows"] += 1
    else:
        bucket["used_rows"] += 1
        bucket["total"] += value
        bucket["min"] = value if bucket["min"] is None else min(bucket["min"], value)
        bucket["max"] = value if bucket["max"] is None else max(bucket["max"], value)


def _finish(bucket: dict, operation: str) -> dict:
    result = {key: bucket[key] for key in ("selected_rows", "used_rows", "missing_rows")}
    result["exact"] = True
    if operation == "count":
        result["value"] = bucket["selected_rows"]
    elif not bucket["used_rows"]:
        # There is no evidence for a numeric answer, including a zero sum.
        result["value"] = None
    else:
        if operation == "sum":
            value = bucket["total"]
        elif operation in {"min", "max"}:
            value = bucket[operation]
        else:
            # First try a generous precision sufficient for every terminating mean
            # in the bounded input domain. For a repeating decimal return a finite
            # representation, explicitly labelled rounded rather than exact.
            with localcontext(_CALC_CONTEXT) as context:
                context.prec = _SUM_PRECISION
                context.clear_flags()
                value = bucket["total"] / Decimal(bucket["used_rows"])
                if context.flags[Inexact]:
                    context.prec = max(50, max(1, value.adjusted() + 1) + 28)
                    context.clear_flags()
                    value = bucket["total"] / Decimal(bucket["used_rows"])
                    result["exact"] = False
                    result["rounding_precision"] = context.prec
        result["value"] = _decimal_text(value)
    return result


def _warnings(raw: list[str], results: list[dict]) -> list[str]:
    warnings = []
    for warning in raw:
        if len(warnings) >= MAX_WARNINGS:
            break
        bounded = warning if len(warning) <= MAX_WARNING_CHARS else warning[:MAX_WARNING_CHARS - 14] + " [... clipped]"
        if bounded not in warnings:
            warnings.append(bounded)
    extra = []
    if len(raw) > MAX_WARNINGS:
        extra.append("Additional source warnings were omitted from this bounded result.")
    if any(not result["exact"] for result in results):
        extra.append("Some means have repeating decimal expansions and are explicitly marked rounded; see rounding_precision.")
    if any(result["value"] is None for result in results):
        extra.append("No numeric value was available for at least one aggregate; its result is null, not an inferred zero.")
    # Reserve space for the operation's own limitations instead of hiding them
    # behind a long list of parser warnings.
    return warnings[:MAX_WARNINGS - len(extra)] + extra



def _profile(table: dict, column: str | None) -> dict:
    """Inspect bounded table shape and mixed types without executing formula text.

    A profile is observational: type_assessment is a heuristic based on parsed
    cells, not a declared database schema. Never include raw string samples.
    """
    columns, rows = table["columns"], table["rows"]
    if column is None:
        if len(columns) > MAX_PROFILE_COLUMNS:
            raise ValueError(f"Profiling more than {MAX_PROFILE_COLUMNS} columns requires an exact column")
        selected = list(enumerate(columns))
    else:
        selected = [(_column(columns, column, "Profile column"), column)]
    if len(rows) * len(selected) > MAX_PROFILE_CELLS:
        raise ValueError(
            f"Profile exceeds {MAX_PROFILE_CELLS} cells; select one column or a smaller attached table"
        )

    profiles = []
    for index, name in selected:
        missing = numeric = text = boolean = formula = invalid_numeric = 0
        minimum = maximum = None
        for row_number, row in enumerate(rows, start=1):
            value = row[index]
            if value is None or (type(value) is str and not value.strip()):
                missing += 1
                continue
            if type(value) is bool:
                boolean += 1
                continue
            if type(value) is str and value.lstrip().startswith("="):
                formula += 1
                continue
            numeric_like = type(value) in (int, float) or (
                type(value) is str and len(value.strip()) <= MAX_NUMERIC_CHARS
                and _NUMBER.fullmatch(value.strip()) is not None
            )
            if not numeric_like:
                text += 1
                continue
            try:
                number = _numeric(value, f"Profile column {name}, row {row_number}")
            except ValueError:
                invalid_numeric += 1
                continue
            if number is None:
                missing += 1
                continue
            numeric += 1
            minimum = number if minimum is None else min(minimum, number)
            maximum = number if maximum is None else max(maximum, number)
        categories = (
            (["numeric"] if numeric else [])
            + (["text"] if text or formula else [])
            + (["boolean"] if boolean else [])
            + (["out_of_range_numeric"] if invalid_numeric else [])
        )
        profiles.append({
            "column": name,
            "type_assessment": "empty" if not categories else categories[0] if len(categories) == 1 else "mixed",
            "missing_rows": missing,
            "numeric_rows": numeric,
            "text_rows": text,
            "boolean_rows": boolean,
            "formula_text_rows": formula,
            "invalid_numeric_rows": invalid_numeric,
            "numeric_min": None if minimum is None else _decimal_text(minimum),
            "numeric_max": None if maximum is None else _decimal_text(maximum),
        })

    extra = []
    if any(item["type_assessment"] == "mixed" for item in profiles):
        extra.append("Mixed columns cannot be treated as fully numeric without inspecting source cells.")
    if any(item["formula_text_rows"] for item in profiles):
        extra.append("Formula-looking text was counted only; STAR did not evaluate spreadsheet formulas.")
    if any(item["invalid_numeric_rows"] for item in profiles):
        extra.append("Some numeric-looking cells exceed accepted size or precision bounds.")
    source_warnings = _warnings(table["warnings"], [{"exact": True, "value": 0}])
    return {
        "dataset_id": table["id"], "dataset_name": table["name"], "operation": "profile",
        "column": column, "source": table["source"], "input_rows": len(rows),
        "total_columns": len(columns), "profiled_columns": len(profiles),
        "profiles": profiles, "counts_exact": True,
        "warnings": source_warnings[:MAX_WARNINGS - len(extra)] + extra,
        "notice": "Observed types are heuristic; missing source rows and spreadsheet formula caches are not inferred.",
    }


def analyze(datasets: list[dict], arguments: dict) -> dict:
    """Analyze one attached dataset; invalid requests/data raise ValueError.

    Arguments are dataset_id, operation, optional column, group_by, and filters.
    The aggregate value is an integer for count, a decimal string otherwise, or
    null if no selected row contains a numeric value. Each result reports rows
    selected, used, and missing. Grouping adds at most MAX_GROUPS result objects
    in first-occurrence order and also returns the aggregate across all groups.
    """
    if type(arguments) is not dict or not {"dataset_id", "operation"} <= set(arguments):
        raise ValueError("Arguments must contain dataset_id and operation")
    if set(arguments) - {"dataset_id", "operation", "column", "group_by", "filters"}:
        raise ValueError("Unknown data-analysis argument")
    dataset_id = _label(arguments["dataset_id"], "Dataset id", 256)
    operation = arguments["operation"]
    if type(operation) is not str or operation not in _OPERATIONS:
        raise ValueError("Unsupported data-analysis operation")
    table = _dataset(datasets, dataset_id)
    columns = table["columns"]
    if operation == "profile":
        if "filters" in arguments or "group_by" in arguments:
            raise ValueError("Profile does not accept filters or grouping; select a specific column instead")
        return _profile(table, arguments.get("column"))
    numeric_column = None
    if operation == "count":
        if "column" in arguments:
            raise ValueError("Count counts filtered rows; omit the numeric column")
    else:
        numeric_column = _column(columns, arguments.get("column"), "Numeric column")
    group_column = _column(columns, arguments["group_by"], "Group column") if "group_by" in arguments else None
    prepared = _filters(columns, arguments.get("filters", []))
    total, groups, row_locations = _bucket(), {}, []
    with localcontext(_CALC_CONTEXT) as context:
        context.prec = _SUM_PRECISION
        context.clear_flags()
        for row_number, row in enumerate(table["rows"], start=1):
            if not _matches(row, prepared, row_number):
                continue
            value = None if numeric_column is None else _numeric(row[numeric_column], f"Numeric column, row {row_number}")
            _add(total, value, operation)
            if table.get('row_sources') is not None and len(row_locations) < 8:
                location = table['row_sources'][row_number - 1]
                row_locations.append(location if len(location) <= 200 else location[:186] + ' [... clipped]')
            if group_column is not None:
                key = _group_key(row[group_column])
                if key not in groups:
                    if len(groups) >= MAX_GROUPS:
                        raise ValueError(f"Grouping exceeds the {MAX_GROUPS}-group limit; filter the dataset first")
                    groups[key] = (row[group_column], _bucket())
                _add(groups[key][1], value, operation)
        if context.flags[Inexact]:
            raise ValueError("Calculation exceeded exact arithmetic bounds")
    summary = _finish(total, operation)
    group_results = [{"key": key, **_finish(bucket, operation)} for key, bucket in groups.values()]
    result = {
        "dataset_id": dataset_id, "dataset_name": table["name"], "operation": operation,
        "column": arguments.get("column"), "group_by": arguments.get("group_by"),
        "filters": arguments.get('filters', []),
        "source": table["source"], "input_rows": len(table["rows"]),
        **summary, "warnings": _warnings(table["warnings"], [summary, *group_results]),
    }
    if group_column is not None:
        result["groups"] = group_results
    if table.get('row_sources') is not None:
        result['row_evidence'] = {'locations': row_locations,
                                  'additional_selected_rows': total['selected_rows'] - len(row_locations)}
    return result
