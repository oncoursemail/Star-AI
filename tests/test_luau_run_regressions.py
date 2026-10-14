"""Regression cases found while exercising sandbox results and admission."""
from pathlib import Path
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "knowledge"))
from starkb import luaurun


def test_successful_print_is_not_a_diagnostic(tmp_path):
    if sys.platform != "linux" or not shutil.which("prlimit"):
        pytest.skip("Linux prlimit is required for the real child probe")
    result = luaurun._execute(
        [sys.executable, "-I", "-S", "-c", 'print("code:2: this is only printed output")'],
        tmp_path, seconds=2, memory_mb=64)
    assert result["ok"] and not result["errors"]
    assert "only printed output" in result["output"]


def test_queue_deadline_still_applies_when_notified_late(monkeypatch):
    queue = luaurun.RunQueue(wait=1)
    queue._running = True
    now = [0.0]
    monkeypatch.setattr(luaurun.time, "monotonic", lambda: now[0])
    def late_notify(timeout):
        queue._running = False
        now[0] = 2.0
    monkeypatch.setattr(queue._condition, "wait", late_notify)
    with pytest.raises(luaurun.Busy, match="deadline"):
        with queue.slot("late"):
            pytest.fail("expired request admitted")
    assert not queue._clients and not queue._waiting


def test_existing_control_character_filter_is_unchanged():
    from star.doc_knowledge import clean_text
    hidden = ''.join(chr(i) for start, end in ((0x200b, 0x200f), (0x202a, 0x202e), (0x2066, 0x2069))
                     for i in range(start, end + 1))
    assert clean_text("left" + hidden + "right\n", 100) == "leftright\n"


def test_extreme_time_limit_is_a_validation_error():
    service = luaurun.RunService(enabled=True, runner=lambda *a, **k: pytest.fail("spawned"))
    status, reply = service.handle({"code": "return 1", "time_limit_s": 10**400}, "peer")
    assert status == 400 and reply["executed"] is False


def test_client_extreme_time_limit_sends_nothing():
    from star.luau_run_client import run
    with pytest.raises(ValueError):
        run(object(), "return 1", time_limit_s=10**400)


def test_out_of_range_printed_error_lines_are_ignored(tmp_path):
    if sys.platform != "linux" or not shutil.which("prlimit"):
        pytest.skip("Linux prlimit is required for the real child probe")
    result = luaurun._execute(
        [sys.executable, "-I", "-S", "-c",
         'import sys; print("code:0: ignored\\ncode:1000000: ignored\\ncode:2: kept"); sys.exit(1)'],
        tmp_path, seconds=2, memory_mb=64)
    assert not result["ok"]
    assert result["errors"] == [{"source": "code", "line": 2, "message": "kept"}]


def test_max_wall_time_does_not_raise_eval_cpu_cap(tmp_path):
    if sys.platform != "linux" or not shutil.which("prlimit"):
        pytest.skip("Linux prlimit is required for the real child probe")
    result = luaurun._execute(
        [sys.executable, "-I", "-S", "-c",
         'import resource; print(resource.getrlimit(resource.RLIMIT_CPU))'],
        tmp_path, seconds=10, memory_mb=64)
    assert result["ok"] and result["output"].strip() == "(8, 8)"
    assert result["limits"]["cpu_limit_s"] == 8


@pytest.mark.parametrize("value", [10**400, float("inf"), float("nan"), True, -1])
def test_malformed_usage_numbers_are_unavailable(value):
    import json
    import secrets
    import httpx
    from star.doc_knowledge import KnowledgeClient, KnowledgeUnavailable
    data = {"ok": True, "status": "pass", "executed": True, "output": "", "error": "",
            "errors": [], "exit_code": 0, "timed_out": False, "output_limited": False,
            "usage": {"wall_seconds": value, "cpu_seconds": 0,
                      "max_rss_bytes": 0, "output_bytes": 0}}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=json.dumps(data)))
    client = KnowledgeClient("https://knowledge.invalid", secrets.token_hex(24), transport)
    with pytest.raises(KnowledgeUnavailable):
        client.luau_run("return 1")


@pytest.mark.parametrize("code, tests", [
    ("assert = function() end; return 0", "assert(result == 1)"),
    ("return function() assert = function() end; return 0 end",
     "local value = result(); assert(value == 1)"),
])
def test_real_vm_code_cannot_replace_test_assert(code, tests):
    if not luaurun.available():
        pytest.skip("real standalone Luau needs STAR_LUAU_TOOLS, Linux prlimit and non-root")
    result = luaurun.run(code, tests)
    assert not result["ok"]
    assert result["errors"] and result["errors"][0]["source"] == "tests"
