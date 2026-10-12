"""Offline concurrent Studio observations: isolated routing and honest evidence."""
import asyncio
import json

import pytest

from star import studio, studio_parallel as farm
from tests.studio_fake import FakeStudio, text


class FakeSession:
    def __init__(self, ids=("studio-a", "studio-b", "studio-c"), *, delay=0.015):
        self.ids = tuple(ids)
        self.delay = delay
        self.calls = []
        self.running = set()
        self.started = asyncio.Event()
        self.peak = 0
        self.bad = None
        self.logs = {}
        self.read_counts = {}

    async def list_tools(self, cursor=None):
        return await FakeStudio().list_tools(cursor)

    async def call_tool(self, name, arguments):
        if name == "list_roblox_studios":
            return text({"studios": [{"id": sid, "name": sid} for sid in self.ids]})
        assert name in {"get_studio_state", "get_console_output"}, name
        assert set(arguments) == {"studio_id"}
        sid = arguments["studio_id"]
        assert sid in self.ids
        assert sid not in self.running, "A Studio was used by concurrent calls"
        self.running.add(sid)
        self.started.set()
        self.peak = max(self.peak, len(self.running))
        self.calls.append((name, sid))
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.bad == (sid, name, "timeout"):
                await asyncio.sleep(10)
            if self.bad == (sid, name, "exception"):
                raise RuntimeError("secret-key-and-private-host-in-exception")
            if self.bad == (sid, name, "rejected"):
                return {"isError": True, "content": [{"type": "text", "text": "private-token"}]}
            if self.bad == (sid, name, "large"):
                return {"content": [{"type": "text", "text": "a" * 100_000}]}
            if name == "get_console_output":
                self.read_counts[sid] = self.read_counts.get(sid, 0) + 1
            data = (json.dumps({"playState": "Edit"}) if name == "get_studio_state"
                    else self.logs.get(sid, ""))
            if name == "get_console_output" and sid in self.logs:
                data += f"\nSNAPSHOT {self.read_counts[sid]}"
            return {"isError": False, "content": [{"type": "text", "text": data}]}
        finally:
            self.running.remove(sid)


def run(coro):
    return asyncio.run(coro)


def test_real_async_overlap_without_two_calls_to_same_studio():
    session = FakeSession()
    report = run(farm.inspect(session, ["studio-a", "studio-b", "studio-c"],
                              rounds=3, max_parallel=2))
    assert session.peak == report.peak_concurrency == 2
    assert len(report.results) == 9
    assert all(item.status == "observed" and item.play_state == "Edit" for item in report.results)
    assert report.public()["gameplay_verified"] is False
    assert report.public()["model_trained"] is False
    assert report.public()["incomplete"] == 0
    assert report.public()["median_observation_ms"] >= 0
    assert len(session.calls) == 18  # 2 read-only tools per completed observation
    assert {name for name, _ in session.calls} == {"get_studio_state", "get_console_output"}


def test_explicit_selection_and_invalid_inputs_do_not_call_tools():
    session = FakeSession()
    invalid = [["studio-a", "studio-a"], ["studio-x"], [],
               ["studio-a\n"], ["studio-a", None], ["x"] * 9]
    for ids in invalid:
        with pytest.raises(ValueError):
            run(farm.inspect(session, ids))
    for opts in ({"rounds": 0}, {"rounds": True}, {"max_parallel": 0},
                 {"max_parallel": 9}, {"timeout_seconds": False},
                 {"timeout_seconds": -1}, {"target": "ssh-anywhere"}):
        with pytest.raises(ValueError):
            run(farm.inspect(session, ["studio-a"], **opts))
    assert session.calls == []


def test_one_connector_failure_does_not_hide_other_evidence_or_private_error():
    session = FakeSession()
    session.bad = ("studio-a", "get_console_output", "exception")
    report = run(farm.inspect(session, ["studio-a", "studio-b"], max_parallel=2)).public()
    assert report["incomplete"] == 1
    assert report["results"][0]["status"] == "unavailable"
    assert report["results"][0]["reason"] == "connector_error"
    assert report["results"][1]["status"] == "observed"
    assert "secret-key" not in json.dumps(report)
    assert "private-host" not in json.dumps(report)


@pytest.mark.parametrize("failure,status,reason", [
    ("rejected", "invalid_evidence", "connector_rejected"),
    ("large", "invalid_evidence", "invalid_content"),
    ("timeout", "timed_out", "deadline"),
])
def test_bounded_evidence_and_independent_timeouts(failure, status, reason):
    session = FakeSession(delay=0)
    session.bad = ("studio-a", "get_console_output", failure)
    report = run(farm.inspect(session, ["studio-a", "studio-b"], timeout_seconds=0.025))
    assert report.results[0].status == status
    assert report.results[0].reason == reason
    assert report.results[1].status == "observed"
    assert "private-token" not in json.dumps(report.public())


def test_tools_missing_fails_closed_before_observing(monkeypatch):
    async def bad_tools(_session):
        return [{"name": "execute_luau"}, {"name": "get_studio_state"}]
    monkeypatch.setattr(studio, "list_tools", bad_tools)
    session = FakeSession()
    with pytest.raises(ValueError, match="read-only"):
        run(farm.inspect(session, ["studio-a"]))
    assert session.calls == []


def test_repeat_errors_produce_unapproved_candidate_but_no_raw_logs():
    session = FakeSession(ids=("studio-a",), delay=0)
    session.logs["studio-a"] = "Error: private-project-name\nWARNING: secret-passphrase\nnormal"
    report = run(farm.inspect(session, ["studio-a"], rounds=4)).public()
    assert [item["console_alert_lines"] for item in report["results"]] == [2] * 4
    assert [item["console_lines"] for item in report["results"]] == [4] * 4
    assert all(item["console_sha256"] for item in report["results"])
    assert report["learning_candidates"] == [{
        "studio_id": "studio-a", "status": "candidate", "source": "studio_mcp_read_only",
        "requires_human_review": True,
        "description": ("Console warning/error patterns appeared in 4 of 4 independent read-only "
                        "observations with changing output snapshots; inspect Studio output "
                        "before approving a lesson."),
        "rounds": [1, 2, 3, 4]}]
    encoded = json.dumps(report)
    assert "private-project-name" not in encoded
    assert "secret-passphrase" not in encoded


def test_no_learning_from_one_alarm_or_failed_observations():
    session = FakeSession(ids=("studio-a",), delay=0)
    session.logs["studio-a"] = "No warnings"
    report = run(farm.inspect(session, ["studio-a"], rounds=1))
    assert farm.candidate_findings(report) == []
    with pytest.raises(ValueError):
        farm.candidate_findings(report, minimum_observations=1)


def test_external_cancellation_is_not_reported_as_success():
    async def scenario():
        session = FakeSession(delay=10)
        task = asyncio.create_task(farm.inspect(session, ["studio-a", "studio-b"], max_parallel=2))
        # Wait until a real observation starts; a fixed sleep races on busy Windows CI.
        await asyncio.wait_for(session.started.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not session.running
    run(scenario())


def test_report_save_explicit_local_file_only(tmp_path):
    path = tmp_path / "observations" / "report.json"
    farm._save_report(path, {"status": "observed"})
    assert json.loads(path.read_text()) == {"status": "observed"}
    assert not path.with_name("report.json.tmp").exists()


def test_unchanged_log_does_not_create_spurious_learning_candidate():
    session = FakeSession(ids=("studio-a",), delay=0)
    session.logs["studio-a"] = "Warning: only one old warning"
    # Simulate an MCP console that returns an identical buffered log every round.
    async def constant_tool(name, arguments):
        if name == "list_roblox_studios":
            return text({"studios": [{"id": sid, "name": sid} for sid in session.ids]})
        if name == "get_studio_state":
            content = json.dumps({"playState": "Edit"})
        else:
            content = session.logs[arguments["studio_id"]]
        return {"content": [{"type": "text", "text": content}]}
    session.call_tool = constant_tool
    report = run(farm.inspect(session, ["studio-a"], rounds=5))
    assert len(report.results) == 5
    assert all(item.status == "observed" for item in report.results)
    assert len({item.console_sha256 for item in report.results}) == 1
    assert farm.candidate_findings(report) == []
