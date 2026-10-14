"""Start-up imports: heavy libraries load on first use, and behave exactly as a normal import.

The desktop imports `star.react_shell` before it can show a window. jsonschema, httpx and anyio
are not needed for that, so the modules on that path bind them with `star._lazy`; the first
validation, request or Studio session imports them.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from star._lazy import lazy_attr, lazy_module

ROOT = Path(__file__).resolve().parents[1]
DEFERRED = ("jsonschema", "httpx", "anyio")


def _loaded_after_import(module: str, tmp_path) -> list[str]:
    code = (f"import sys, json\nimport {module}\n"
            f"print(json.dumps([m for m in {DEFERRED!r} if m in sys.modules]))")
    env = {**os.environ, "APPDATA": str(tmp_path), "XDG_DATA_HOME": str(tmp_path)}
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True,
                         check=True, timeout=180)
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("module", ["star.react_shell", "star.desktop_core", "star.agent"])
def test_desktop_start_up_does_not_import_the_deferred_libraries(module, tmp_path):
    assert _loaded_after_import(module, tmp_path) == []


def test_lazy_module_is_the_real_module_on_first_use():
    proxy = lazy_module("json")
    assert proxy.dumps({"a": 1}) == json.dumps({"a": 1})
    assert proxy.JSONDecodeError is json.JSONDecodeError
    with pytest.raises(proxy.JSONDecodeError):
        proxy.loads("{")
    assert isinstance(json.JSONDecoder(), proxy.JSONDecoder)
    assert "dumps" in dir(proxy)
    assert "loaded" in repr(proxy)


def test_lazy_attr_calls_and_exposes_the_real_object():
    validator_class = lazy_attr("jsonschema", "Draft202012Validator")
    import jsonschema
    assert validator_class.check_schema == jsonschema.Draft202012Validator.check_schema
    validator = validator_class({"type": "object", "required": ["a"]})
    assert isinstance(validator, jsonschema.Draft202012Validator)
    assert validator.is_valid({"a": 1}) and not validator.is_valid({})


def test_monkeypatching_through_the_stand_in_patches_the_real_module(monkeypatch):
    import httpx
    from star import web_search
    sentinel = object()
    original = httpx.AsyncClient
    monkeypatch.setattr(web_search.httpx, "AsyncClient", sentinel)
    assert httpx.AsyncClient is sentinel and web_search.httpx.AsyncClient is sentinel
    monkeypatch.undo()
    assert httpx.AsyncClient is original


def test_http_error_types_still_match_through_the_stand_in():
    import httpx
    from star import roblox_cloud
    error = httpx.ConnectError("refused")
    assert isinstance(error, roblox_cloud.httpx.HTTPError)
    assert isinstance(error, roblox_cloud._not_sent())
    assert not isinstance(httpx.ReadTimeout("slow"), roblox_cloud._not_sent())
    try:
        raise error
    except roblox_cloud.httpx.HTTPError as caught:
        assert caught is error


def test_schema_checks_still_validate():
    from star import blender_bridge, map_plan, policy
    with pytest.raises(ValueError):
        blender_bridge.validate_scene({"name": "Scene", "objects": [], "unexpected": True})
    report = map_plan.dry_run({"not": "a plan"})
    assert report["ok"] is False and report["blockers"]
    registry = {"script_read": {"name": "script_read", "inputSchema": {
        "type": "object", "properties": {"studio_id": {"type": "string"}, "path": {"type": "string"}},
        "required": ["studio_id", "path"], "additionalProperties": False}}}
    policy.enforce("script_read", {"studio_id": "s1", "path": "Workspace.Script"}, registry, "s1", False)
    import jsonschema
    with pytest.raises(jsonschema.ValidationError):
        policy.enforce("script_read", {"studio_id": "s1"}, registry, "s1", False)
