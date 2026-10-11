"""Independent expected-value cases for selected-table calculations."""
import csv
from decimal import Inexact, ROUND_DOWN, localcontext
from io import StringIO
import json

import pytest

from star.data_analysis import (
    DATA_TOOL_NAME, MAX_GROUPS, MAX_ROWS, MAX_WARNINGS,
    analyze, data_tool_schema,
)


def table(rows, columns=None, warnings=None):
    return [{"id": "data:one", "name": "orders.csv", "columns": columns or ["amount"],
             "rows": rows, "source": "orders.csv, rows 2 onward", "warnings": warnings or []}]


def request(operation, **extra):
    args = {"dataset_id": "data:one", "operation": operation}
    if operation != "count":
        args["column"] = "amount"
    return {**args, **extra}


def test_tool_schema_is_strict_and_exposes_no_expression_or_file_argument():
    schema = data_tool_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == DATA_TOOL_NAME == "star_data_analyze"
    parameters = schema["function"]["parameters"]
    assert parameters["required"] == ["dataset_id", "operation"]
    assert parameters["additionalProperties"] is False
    assert set(parameters["properties"]) == {"dataset_id", "operation", "column", "group_by", "filters"}
    json.dumps(schema, allow_nan=False)


@pytest.mark.parametrize("operation,expected", [("sum", "0.6"), ("mean", "0.2"), ("min", "0.1"), ("max", "0.3")])
def test_decimal_aggregates_have_independent_exact_values(operation, expected):
    result = analyze(table([["0.1"], [0.2], ["0.3"]]), request(operation))
    assert result["value"] == expected
    assert result["exact"] is True
    assert (result["selected_rows"], result["used_rows"], result["missing_rows"]) == (3, 3, 0)
    assert result["source"] == "orders.csv, rows 2 onward"


def test_decimal_sum_is_independent_of_callers_decimal_precision():
    with localcontext() as context:
        context.prec = 3
        result = analyze(table([["12345678901234567890.12345"], ["0.00005"]]), request("sum"))
        assert context.prec == 3
    assert result["value"] == "12345678901234567890.1235"


def test_negatives_missing_values_and_count_mean_differ():
    data = table([["-12.75"], ["4.25"], [None], [""], ["  "]])
    result = analyze(data, request("sum"))
    assert result["value"] == "-8.5"
    assert (result["selected_rows"], result["used_rows"], result["missing_rows"]) == (5, 2, 3)
    assert analyze(data, request("mean"))["value"] == "-4.25"
    assert analyze(data, request("min"))["value"] == "-12.75"
    assert analyze(data, request("max"))["value"] == "4.25"
    counted = analyze(data, request("count"))
    assert counted["value"] == 5 and counted["used_rows"] == 5 and counted["missing_rows"] == 0


def test_quoted_multiline_csv_table_and_conjunctive_filters():
    parsed = list(csv.reader(StringIO('label,amount,quantity\n"red, large",1.20,2\n"blue\nsmall",-0.20,3\n"red, large",2.30,4\n')))
    data = table(parsed[1:], columns=parsed[0])
    result = analyze(data, request("sum", filters=[
        {"column": "label", "op": "eq", "value": "red, large"},
        {"column": "quantity", "op": "gte", "value": 3},
    ]))
    assert result["value"] == "2.3" and result["selected_rows"] == 1
    assert analyze(data, request("count", filters=[{"column": "label", "op": "eq", "value": "blue\nsmall"}]))["value"] == 1


@pytest.mark.parametrize("op,expected", [("eq", 1), ("ne", 2), ("gt", 1), ("gte", 2), ("lt", 1), ("lte", 2)])
def test_numeric_filters_are_computed_over_numeric_csv_cells(op, expected):
    data = table([["1"], ["2"], ["3"], [None]])
    result = analyze(data, request("count", filters=[{"column": "amount", "op": op, "value": 2}]))
    assert result["value"] == expected


def test_literal_string_and_boolean_filters_do_not_coerce_categories():
    data = table([["01"], ["1"], [1], [True], [False], [0]])
    assert analyze(data, request("count", filters=[{"column": "amount", "op": "eq", "value": "01"}]))["value"] == 1
    assert analyze(data, request("count", filters=[{"column": "amount", "op": "eq", "value": False}]))["value"] == 1


def test_grouped_sums_and_counts_report_independent_row_totals():
    data = table([["A", "10.10"], ["B", "-4"], ["A", "0.20"], ["B", None], [None, "5"]], columns=["team", "amount"])
    result = analyze(data, request("sum", group_by="team"))
    assert result["value"] == "11.3"
    groups = result["groups"]
    assert [group["key"] for group in groups] == ["A", "B", None]
    assert [(group["value"], group["selected_rows"], group["used_rows"], group["missing_rows"]) for group in groups] == [
        ("10.3", 2, 2, 0), ("-4", 2, 1, 1), ("5", 1, 1, 0),
    ]
    counted = analyze(data, request("count", group_by="team"))
    assert [group["value"] for group in counted["groups"]] == [2, 2, 1]


def test_grouped_means_min_max_and_boolean_number_keys():
    data = table([["A", "2"], ["A", "4"], ["B", "9"]], columns=["team", "amount"])
    assert [group["value"] for group in analyze(data, request("mean", group_by="team"))["groups"]] == ["3", "9"]
    assert [group["value"] for group in analyze(data, request("min", group_by="team"))["groups"]] == ["2", "9"]
    assert [group["value"] for group in analyze(data, request("max", group_by="team"))["groups"]] == ["4", "9"]
    keys = analyze(table([[True], [1], [1.0], ["1"]]), request("count", group_by="amount"))["groups"]
    assert [(group["key"], group["value"]) for group in keys] == [(True, 1), (1, 2), ("1", 1)]


def test_repeating_mean_is_explicitly_rounded_not_claimed_exact():
    result = analyze(table([["1"], ["0"], ["0"]]), request("mean"))
    assert result["value"] == "0." + "3" * 50
    assert result["exact"] is False and result["rounding_precision"] == 50
    assert any("rounded" in warning for warning in result["warnings"])


def test_calculation_uses_its_own_context_and_preserves_callers_traps():
    with localcontext() as context:
        context.prec = 3
        context.rounding = ROUND_DOWN
        context.traps[Inexact] = True
        result = analyze(table([["2"], ["0"], ["0"]]), request("mean"))
        assert context.prec == 3 and context.rounding == ROUND_DOWN and context.traps[Inexact]
    assert result["value"] == "0." + "6" * 49 + "7"
    assert result["exact"] is False


@pytest.mark.parametrize("operation", ["sum", "mean", "min", "max"])
def test_all_missing_or_empty_numeric_aggregate_is_null(operation):
    for rows in ([], [[None], [" "]]):
        result = analyze(table(rows), request(operation))
        assert result["value"] is None and result["used_rows"] == 0
        assert result["missing_rows"] == len(rows)
        assert any("null" in warning for warning in result["warnings"])


def test_cached_formula_values_are_used_and_missing_caches_remain_missing():
    result = analyze(table([["5.5"], [None]], warnings=["Sheet1!A3 has no cached formula value; formulas were not recalculated."]), request("sum"))
    assert result["value"] == "5.5" and result["missing_rows"] == 1
    assert "not recalculated" in result["warnings"][0]
    with pytest.raises(ValueError, match="formulas are never recalculated"):
        analyze(table([["=SUM(A1:A2)"]]), request("sum"))


@pytest.mark.parametrize("cell", [True, False, float("nan"), float("inf"), float("-inf"), "NaN", "Infinity", "-Infinity", "a", "1,000", "1e1000000", "1e-1000000"])
def test_invalid_numeric_cells_fail_instead_of_disappearing(cell):
    with pytest.raises(ValueError):
        analyze(table([[cell]]), request("sum"))


@pytest.mark.parametrize("arguments", [
    {}, [], {"dataset_id": "data:one"}, request("SUM"), request("sum; import os"),
    request("count", column="amount"), request("sum", column="Amount"), request("sum", column=None),
    request("sum", path="../private.csv"), request("sum", expression="__import__('os').system('anything')"),
    request("sum", group_by="missing"), request("sum", filters=None),
    request("sum", filters=[{"column": "amount", "op": "eval", "value": 1}]),
    request("sum", filters=[{"column": "amount", "op": "eq", "value": []}]),
    request("sum", filters=[{"column": "amount", "op": "eq", "value": 1, "extra": True}]),
    request("sum", filters=[{"column": "amount", "op": "gt", "value": True}]),
    request("sum", filters=[{"column": "amount", "op": "gt", "value": None}]),
    request("sum", filters=[{"column": "amount", "op": "gt", "value": float("nan")}]),
])
def test_malformed_or_injected_arguments_are_refused(arguments):
    with pytest.raises(ValueError):
        analyze(table([[1]]), arguments)


def test_unknown_dataset_and_duplicate_identity_fail_without_reading_files():
    with pytest.raises(ValueError, match="not among"):
        analyze(table([[1]]), request("sum", dataset_id="../../other-project/private.csv"))
    data = table([[1]])
    with pytest.raises(ValueError, match="ambiguous"):
        analyze(data + data, request("sum"))


def test_limits_refuse_partial_group_or_row_answers():
    with pytest.raises(ValueError, match="group limit"):
        analyze(table([[str(index)] for index in range(MAX_GROUPS + 1)]), request("count", group_by="amount"))
    with pytest.raises(ValueError, match="rows"):
        analyze(table([[1]] * (MAX_ROWS + 1)), request("count"))
    with pytest.raises(ValueError, match="at most 4"):
        analyze(table([[1]]), request("count", filters=[{"column": "amount", "op": "eq", "value": 1}] * 5))
    with pytest.raises(ValueError, match="Group key"):
        analyze(table([["x" * 201]]), request("count", group_by="amount"))


def test_output_warnings_are_bounded_and_rounding_warning_is_preserved():
    result = analyze(table([["1"], ["0"], ["0"]], warnings=["w" * 2_000 + str(index) for index in range(30)]), request("mean"))
    assert len(result["warnings"]) <= MAX_WARNINGS
    assert all(len(warning) <= 1_000 for warning in result["warnings"])
    assert any("rounded" in warning for warning in result["warnings"])
    assert any("omitted" in warning for warning in result["warnings"])
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("change", [
    {"columns": ["amount", "amount"], "rows": [[1, 2]]},
    {"rows": [[1, 2]]}, {"rows": [[{"secret": "not a scalar"}]]},
    {"warnings": "not a list"}, {"source": "x" * 2_049},
])
def test_malformed_tables_are_refused(change):
    data = table([[1]])
    data[0].update(change)
    with pytest.raises(ValueError):
        analyze(data, request("sum"))
