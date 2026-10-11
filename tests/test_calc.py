"""Real calculator operations and bounded unsafe AST regression cases."""
import math

import pytest

from star.calc import calculate, convert, describe, evaluate, numerical_request


@pytest.mark.parametrize(("expression", "expected"), [
    ("1+2*3", 7), ("(1+2)*3", 9), ("1/3+1/6", "1/2"),
    ("2**10", 1024), ("9//2", 4), ("9%4", 1),
    ("-3+5", 2), ("3<4<5", True), ("4==5", False),
    ("sqrt(81)", 9), ("abs(-12)", 12), ("round(2.6)", 3),
    ("floor(2.9)", 2), ("ceil(2.1)", 3),
    ("min(3,1,2)", 1), ("max(3,1,2)", 3),
    ("sum([1,2,3])", 6), ("factorial(5)", 120),
    ("gcd(24,18)", 6), ("lcm(6,8)", 24),
    ("comb(5,2)", 10), ("perm(5,2)", 20),
    ("log2(8)", 3), ("log10(100)", 2),
    ("sin(0)", 0), ("cos(0)", 1), ("tan(0)", 0),
    ("asin(0)", 0), ("acos(1)", 0), ("atan(0)", 0),
    ("atan2(0,1)", 0), ("log(e)", 1), ("exp(0)", 1),
])
def test_expression_table(expression, expected):
    actual = evaluate(expression)
    if isinstance(expected, str):
        assert str(actual) == expected
    else:
        assert actual == pytest.approx(expected) if type(expected) is not bool else actual is expected


@pytest.mark.parametrize("expression", [
    "__import__('os').system('echo bad')", "open('file')", "eval('2+2')",
    "exec('pass')", "globals()", "locals()", "().__class__",
    "pi.__class__", "(1).__class__.__mro__", "[x for x in [1]]",
    "(lambda:1)()", "f'{1}'", "{'x':1}", "{1,2}",
    "1 if True else 2", "True", "None", "'hello'",
    "math.sqrt(4)", "getattr(1,'real')",
    "sum([1], start=2)", "a", "1;2",
])
def test_malicious_expressions_rejected(expression):
    with pytest.raises(ValueError):
        evaluate(expression)


@pytest.mark.parametrize("expression", [
    "x" * 513, "("*25+"1"+")"*25, "2**101",
    "factorial(1001)", "factorial(-1)", "1/0",
    "10**100**2", "exp(1000)", "sum([" + ",".join(["1"]*81) + "])",
])
def test_limits(expression):
    with pytest.raises(ValueError):
        evaluate(expression)


@pytest.mark.parametrize(("value", "source", "target", "expected"), [
    (100, "cm", "m", 1), (1, "km", "m", 1000),
    (1, "stud", "m", .28), (1, "lb", "kg", .45359237),
    (60, "min", "h", 1), (32, "f", "c", 0),
    (0, "c", "k", 273.15), (180, "deg", "rad", math.pi),
    (1, "KiB", "byte", 1024), (8, "bit", "byte", 1),
])
def test_conversions(value, source, target, expected):
    assert float(convert(value, source, target)) == pytest.approx(expected)


@pytest.mark.parametrize(("op", "result"), [
    ("mean", 2.5), ("median", 2.5), ("mode", 1),
    ("variance", 11 / 3), ("stdev", math.sqrt(11 / 3)),
])
def test_statistics(op, result):
    assert float(describe([1, 1, 3, 5], op)) == pytest.approx(result)


def test_calculate_dispatch_and_invalid_units():
    assert calculate({"expression": "1/3"}) == {"result": "1/3"}
    assert calculate({"operation": "convert", "value": 2, "from_unit": "stud", "to_unit": "m"}) == {"result": "14/25"}
    with pytest.raises(ValueError):
        convert(2, "kg", "seconds")
    with pytest.raises(ValueError):
        convert(-300, "c", "k")
    with pytest.raises(ValueError):
        describe([], "mean")
    with pytest.raises(ValueError):
        calculate({"expression": "2", "malicious": True})


@pytest.mark.parametrize(("prompt", "selected"), [
    ("Calculate 72 / 3", True), ("what is 4 + 8?", True),
    ("convert 14 studs to metres", True), ("mean of 2,3", True),
    ("Roblox 0.9.0 is released", False), ("please make UI", False),
])
def test_numeric_trigger(prompt, selected):
    assert numerical_request(prompt) is selected
