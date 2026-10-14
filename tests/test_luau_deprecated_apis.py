"""Default-off, source-grounded deprecated Roblox API lint tests (no Studio/network)."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from star.luau_lint import Finding, lint

ROOT = Path(__file__).resolve().parents[1]

BODY_RULES = (
    ("BodyVelocity", "deprecated-body-velocity", "LinearVelocity"),
    ("BodyGyro", "deprecated-body-gyro", "AlignOrientation"),
    ("BodyPosition", "deprecated-body-position", "AlignPosition"),
    ("BodyForce", "deprecated-body-force", "VectorForce"),
)
RAY_RULES = (
    ("FindPartOnRay", "deprecated-find-part-on-ray", "Raycast"),
    ("FindPartOnRayWithIgnoreList", "deprecated-find-part-on-ray-ignore", "ExcludeInstances"),
    ("FindPartOnRayWithWhitelist", "deprecated-find-part-on-ray-whitelist", "IncludeInstances"),
)
NEW_RULES = frozenset(rule for _, rule, _ in BODY_RULES + RAY_RULES)


def new_findings(code: str, **kwargs) -> list[Finding]:
    return [f for f in lint(code, deprecated_apis=True, external=False, **kwargs)
            if f.rule_id in NEW_RULES]


@pytest.mark.parametrize(("class_name", "rule", "replacement"), BODY_RULES)
def test_body_mover_three_firing_examples(class_name: str, rule: str, replacement: str):
    examples = (
        f'local mover = Instance.new("{class_name}")',
        f"local mover = Instance.new('{class_name}', workspace)",
        f'-- setup\nlocal mover = Instance\n . new (\n  "{class_name}" )',
    )
    for code in examples:
        hits = new_findings(code)
        assert len(hits) == 1, (code, hits)
        assert hits[0].rule_id == rule
        assert hits[0].severity == "warning"
        assert replacement in hits[0].suggested_fix


@pytest.mark.parametrize(("class_name", "rule", "replacement"), BODY_RULES)
def test_body_mover_four_clean_examples(class_name: str, rule: str, replacement: str):
    examples = (
        f'local mover = Instance.new("{replacement}")',
        f'-- Instance.new("{class_name}")\nlocal note = [[Instance.new("{class_name}")]]',
        f'local Factory = {{new = function() end}}\nFactory.new("{class_name}")',
        f'local Instance = {{new = function() end}}\nInstance.new("{class_name}")',
    )
    for code in examples:
        assert not new_findings(code), code


@pytest.mark.parametrize(("method", "rule", "replacement"), RAY_RULES)
def test_ray_method_three_firing_examples(method: str, rule: str, replacement: str):
    examples = (
        f'workspace:{method}(ray)',
        f'local result = workspace : {method} (ray, {{character}})',
        f'-- normal call below\nlocal hit = workspace:{method}(ray, nil)',
    )
    for code in examples:
        hits = new_findings(code)
        assert len(hits) == 1, (code, hits)
        assert hits[0].rule_id == rule
        assert hits[0].severity == "warning"
        assert replacement in hits[0].suggested_fix


@pytest.mark.parametrize(("method", "rule", "replacement"), RAY_RULES)
def test_ray_method_six_clean_examples(method: str, rule: str, replacement: str):
    examples = (
        f'custom:{method}(ray)',
        f'local workspace = {{ {method} = function() end }}\nworkspace:{method}(ray)',
        f'function cast(workspace)\n    return workspace:{method}(ray)\nend',
        f'local text = [[workspace:{method}(ray)]]\n-- workspace:{method}(ray)',
        'local hit = workspace:Raycast(origin, direction, params)',
        f'local object = {{ workspace = {{}} }}\nobject.workspace:{method}(ray)',
    )
    for code in examples:
        assert not new_findings(code), code


@pytest.mark.parametrize("code", [
    "local function f(Instance)\nreturn Instance.new('BodyVelocity')\nend",
    "Instance = {new = function() end}\nInstance.new('BodyForce')",
    "workspace = {FindPartOnRay = function() end}\nworkspace:FindPartOnRay(ray)",
    "local a, Instance = {}, {new=function() end}\nInstance.new('BodyGyro')",
    "local a, workspace = {}, {FindPartOnRay=function() end}\nworkspace:FindPartOnRay(ray)",
    'local s = [==[Instance.new("BodyVelocity") workspace:FindPartOnRay(ray)]==]',
    '--[=[ Instance.new("BodyVelocity") workspace:FindPartOnRay(ray) ]=]',
])
def test_shadowing_comments_and_long_strings_are_inert(code: str):
    assert not new_findings(code), code


def test_findings_are_opt_in_and_source_line_is_preserved():
    code = 'local s = "BodyForce"\n-- workspace:FindPartOnRay(ray)\nInstance.new("BodyForce")\nworkspace:FindPartOnRay(ray)'
    assert lint(code, external=False) == lint(code, deprecated_apis=False, external=False)
    assert new_findings(code) == [
        Finding("deprecated-body-force", 3, "BodyForce is a deprecated Roblox body mover.",
                "Use VectorForce with the appropriate attachment/constraint setup.", "warning"),
        Finding("deprecated-find-part-on-ray", 4, "workspace:FindPartOnRay is deprecated.",
                "Use workspace:Raycast(ray.Origin, ray.Direction, params); inspect the RaycastResult.",
                "warning"),
    ]


def test_every_literal_in_existing_luau_lint_tests_has_unmodified_default():
    # Includes all 12 original positive/negative pairs, comment/string cases,
    # idiomatic scripts and edge inputs in tests/test_luau_lint.py. Extract
    # literals from unchanged pre-feature tests to avoid cherry-picked fixtures.
    module = ast.parse((ROOT / "tests" / "test_luau_lint.py").read_text(encoding="utf-8"))
    snippets = [n.value for n in ast.walk(module)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert len(snippets) >= 60
    for snippet in snippets:
        assert lint(snippet, external=False) == lint(
            snippet, deprecated_apis=False, external=False), repr(snippet)


def test_all_checked_in_roblox_examples_have_no_deprecation_rule():
    paths = sorted(path for folder in (
        ROOT / "examples" / "roblox",
        ROOT / "examples" / "roblox-templates",
        ROOT / "examples" / "roblox-test-place",
    ) for path in folder.rglob("*") if path.suffix in (".lua", ".luau"))
    assert paths, "The repository Roblox example corpus must not silently disappear"
    for path in paths:
        assert not new_findings(path.read_text(encoding="utf-8")), path


def test_invalid_input_still_rejected_when_opted_in():
    with pytest.raises(TypeError, match="code must be str"):
        lint(None, deprecated_apis=True, external=False)
