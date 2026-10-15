"""Deterministic direct-path edges for STAR clock and owner corrections.

No live wall clock, network, GPU, owner profile or private keyring.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

from star import clock
from star import corrections as cr
from star.evals import load_catalog

FIXED = datetime(2026, 10, 13, 18, 5, tzinfo=timezone.utc)
EPOCH = FIXED.timestamp()


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED.astimezone(tz) if tz else FIXED


@pytest.fixture(autouse=True)
def fixed_time_and_empty_server_state(monkeypatch):
    monkeypatch.setattr(clock, "datetime", FrozenDateTime)
    monkeypatch.setattr(cr, "_now", lambda: "2026-10-13T18:05:00+00:00")
    clock.forget_server_clock()
    yield
    clock.forget_server_clock()


def test_local_now_preserves_injected_aware_datetime_and_never_needs_wall_clock():
    assert clock.local_now(FIXED) == FIXED
    naive = clock.local_now(datetime(2026, 10, 13, 18, 5))
    assert naive.tzinfo is not None
    assert clock.local_now().tzinfo is not None  # FrozenDateTime replaces now().


@pytest.mark.parametrize(("header", "expected"), [
    ("Tue, 13 Oct 2026 18:05:00 GMT", 0),
    ("Tue, 13 Oct 2026 18:20:00 GMT", 900),
    ("Tue, 13 Oct 2026 16:05:00 GMT", -7200),
], ids=["synchronized", "ahead", "behind"])
def test_observe_server_date_uses_injected_wall_and_monotonic_clocks(header, expected):
    clock.observe_server_date(header, now=EPOCH, monotonic=lambda: 100.0)
    assert clock.server_offset(monotonic=lambda: 101.0) == expected
    assert clock.server_offset(monotonic=lambda: 3701.0) is None
    assert clock.server_offset(monotonic=lambda: 3599.0) == expected
    clock.forget_server_clock()
    assert clock.server_offset(monotonic=lambda: 101.0) is None


@pytest.mark.parametrize("header", ["garbage", "", "Tue, 13 Oct 2026 18:20:00", None, 120])
def test_malformed_or_naive_http_date_never_replaces_known_clock(header):
    clock.observe_server_date("Tue, 13 Oct 2026 18:10:00 GMT",
                              now=EPOCH, monotonic=lambda: 0)
    clock.observe_server_date(header, now=EPOCH, monotonic=lambda: 1)
    assert clock.server_offset(monotonic=lambda: 2) == 300


def test_now_and_sent_lines_have_stable_fixed_instant_and_skew_threshold():
    assert "Tuesday 2026-10-13 18:05" in clock.now_line(FIXED, offset=0)
    assert "STAR Server" not in clock.now_line(FIXED, offset=90)
    assert "STAR Server clock reads 2026-10-13 18:07 UTC (+2 min)" in clock.now_line(
        FIXED, offset=120)
    assert clock.sent_line("2026-10-13T18:05:00+00:00").startswith("Now:")
    assert clock.sent_line("not a timestamp") == ""
    assert clock.sent_line("") == ""
    assert clock.sent_line("2026-10-13T18:05:00").startswith("Now:")


@pytest.mark.parametrize(("name", "offset"), [
    ("UTC", 0), ("uTc", 0), ("GMT", 0), ("UTC+05:30", 330),
    ("-03:15", -195),
], ids=["utc", "case-alias", "gmt-alias", "east", "west"])
def test_resolve_zone_known_names_and_fixed_offsets(name, offset):
    zone, label = clock.resolve_zone(name)
    assert int(FIXED.astimezone(zone).utcoffset().total_seconds() / 60) == offset
    assert label


@pytest.mark.parametrize("name", [None, "", "local", "my time"])
def test_resolve_zone_local_aliases_are_nonempty_and_use_frozen_now(name):
    zone, label = clock.resolve_zone(name)
    assert zone is not None and "owner" in label


@pytest.mark.parametrize("name", [
    "Neverland/Missing", "UTC+15:00", "UTC+01:60", "A" * 65,
])
def test_resolve_zone_rejects_invalid_names_and_offsets(name):
    with pytest.raises(clock.ClockError):
        clock.resolve_zone(name)


def test_resolve_zone_dst_boundary_and_case_insensitive_iana_lookup():
    try:
        ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        pytest.skip("IANA tzdata not installed")
    zone, label = clock.resolve_zone("america/new_york")
    assert label == "America/New_York"
    before = datetime(2026, 3, 8, 6, 59, tzinfo=timezone.utc).astimezone(zone)
    after = datetime(2026, 3, 8, 7, 1, tzinfo=timezone.utc).astimezone(zone)
    assert before.utcoffset() == timedelta(hours=-5)
    assert after.utcoffset() == timedelta(hours=-4)
    assert before.hour == 1 and after.hour == 3


@pytest.mark.parametrize(("prompt", "wanted"), [
    ("what day was 2026-10-13", True),
    ("time in Tokyo", True),
    ("how many weeks until next year", True),
    ("tell me about animation", False),
    ("what time is it", False),
    (None, False),
])
def test_clock_prompt_selection_is_deliberately_narrow(prompt, wanted):
    assert clock.wants_clock(prompt) is wanted


def test_run_clock_and_tool_result_reject_bad_inputs_and_broken_dependency(monkeypatch):
    assert clock.run_clock({"action": "now", "zones": ["UTC"]}, now=FIXED)["results"][0]["zone"] == "UTC"
    assert clock.run_clock({"action": "add", "time": "2026-10-13", "days": 1,
                            "from_zone": "UTC"}, now=FIXED)["result"]["time"].startswith("Wednesday")
    assert clock.run_clock({"action": "diff", "time": "2026-10-13",
                            "end": "2026-10-14", "from_zone": "UTC"},
                           now=FIXED)["total_days"] == 1
    result = clock.tool_result({"action": "convert", "time": "18:05",
                                "from_zone": "UTC", "zones": ["UTC+01:00"]}, now=FIXED)
    assert result["isError"] is False and json.loads(result["content"][0]["text"])["action"] == "convert"
    for bad in (None, [], {"action": "unknown"}, {"action": "now", "zones": ["UTC"] * 9},
                {"action": "add", "days": True}, {"action": "convert", "time": "55:99"}):
        assert clock.tool_result(bad, now=FIXED)["isError"] is True
    with pytest.raises(clock.ClockError, match="action"):
        clock.run_clock({"action": "bad"}, now=FIXED)
    def unavailable(_name):
        raise clock.ClockError("time-zone provider unavailable")
    monkeypatch.setattr(clock, "resolve_zone", unavailable)
    assert clock.tool_result({"action": "now"}, now=FIXED)["isError"] is True


@pytest.mark.parametrize(("correction", "expected"), [
    ("That API does not exist.", "invented API name"),
    ("Your answer got cut off.", "answer cut off"),
    ("There is a syntax error.", "self-check error left unrepaired"),
    ("You forgot the inventory check.", "required feature missing"),
    ("Sort order is wrong.", "wrong logic"),
])
def test_correction_cause_for_real_lexical_categories(correction, expected):
    assert cr.cause_for(correction) == expected


def test_scrub_bounds_newlines_private_addresses_and_wrong_type():
    address = ".".join(("192", "168", "5", "6"))
    cleaned = cr.scrub("  first\r\nsecond " + address, 80, one_line=True)
    assert cleaned == "first second <private-address>"
    assert cr.scrub("a\nb", 80) == "a\nb"
    assert cr.scrub("X" * 1200, 1000) == "X" * 1000
    assert cr.scrub(None, 12) == ""
    assert cr.scrub(42, 12) == "42"


def test_check_stub_only_creates_named_reviewable_patterns():
    named = cr.check_stub("Use task.wait instead of wait. Do not use spawn.", "")
    assert [c["scope"] for c in named["require"] + named["forbid"]] == ["code"] * 3
    assert re.search(named["require"][0]["re"], "task.wait(1)")
    assert re.search(named["forbid"][0]["re"], "wait(1)")
    assert not re.search(named["forbid"][0]["re"], "task.wait(1)")
    assert cr.check_stub("It felt off.", "") == {"require": [], "forbid": []}
    assert cr.check_stub("", "") == {"require": [], "forbid": []}


def _record(store: cr.CorrectionStore, ref: str, correction: str):
    return store.record(project="RobloxGame", source="app", ref=ref,
                        prompt="Write a Luau inventory.", answer="Use wait(1).",
                        correction=correction)


def test_correction_store_revisions_scoped_list_counts_and_withdraw(tmp_path):
    with_store = cr.CorrectionStore(tmp_path)
    try:
        item = _record(with_store, "msg-1", "Use task.wait instead of wait.")
        changed = _record(with_store, "msg-1", "Use task.spawn instead of spawn.")
        assert changed["id"] == item["id"]
        assert len(with_store.list("RobloxGame")) == 1
        assert with_store.counts("RobloxGame") == {"candidate": 1, "approved": 0, "dismissed": 0}
        with pytest.raises(ValueError, match="project"):
            with_store.get("OtherProject", item["id"])
        assert with_store.withdraw(project="RobloxGame", source="app", ref="msg-1") == 1
        assert with_store.withdraw(project="RobloxGame", source="app", ref="msg-1") == 0
        assert with_store.list("RobloxGame") == []
    finally:
        with_store.close()
    assert (tmp_path / "corrections.sqlite3").is_file()


def test_store_rejects_invalid_values_and_failing_secret_checker(tmp_path, monkeypatch):
    store = cr.CorrectionStore(tmp_path)
    try:
        for kw in (
            dict(source="unknown", ref="bad", prompt="hello", answer="a", correction="too many"),
            dict(source="app", ref="", prompt="hello", answer="a", correction="too many"),
            dict(source="app", ref="bad", prompt="", answer="a", correction="too many"),
            dict(source="app", ref="bad", prompt="hello", answer="a", correction="no"),
        ):
            with pytest.raises(ValueError):
                store.record(project="P", **kw)
        def broken(_value):
            raise RuntimeError("dependency unavailable")
        monkeypatch.setattr(cr, "has_secret", broken)
        with pytest.raises(RuntimeError, match="dependency"):
            _record(store, "will-not-save", "Please fix the server logic")
        assert store.list("RobloxGame") == []
    finally:
        store.close()


def test_task_for_and_write_suite_pass_the_real_catalog_validator(tmp_path):
    store = cr.CorrectionStore(tmp_path)
    try:
        item = _record(store, "msg-2", "Use task.wait instead of wait.")
        task = cr.task_for(item, "CR-0001")
        assert task["run_mode"] == "automated" and task["auto"]["forbid"]
        assert task["check_status"] == "patterns-from-correction"
        path = store.suite_path("RobloxGame")
        cr.write_suite(path, [task])
        catalog = load_catalog(path)
        assert len(catalog) == 1 and catalog[0].id == "CR-0001"
        human = _record(store, "msg-3", "The inventory should update visually.")
        assert cr.task_for(human, "CR-0002")["run_mode"] == "human"
        with pytest.raises(ValueError, match="run mode"):
            cr.write_suite(path, [{"id": "broken"}])
        assert load_catalog(path)[0].id == "CR-0001"
        assert path.with_name(path.name + ".part").is_file()  # invalid provisional file remains only in tmp_path
    finally:
        store.close()


def test_write_suite_refuses_protected_path_before_creating_files(tmp_path):
    forbidden = tmp_path / "evals" / "suite.json"
    with pytest.raises(ValueError, match="never written"):
        cr.write_suite(forbidden, [])
    assert not forbidden.parent.exists()
    with pytest.raises(ValueError, match="never written"):
        cr.write_suite(tmp_path / "holdout.json", [])


def test_owner_approval_gate_dismissal_and_handle_action_permissions(tmp_path):
    store = cr.CorrectionStore(tmp_path)
    try:
        first = _record(store, "m1", "Use task.wait instead of wait.")
        second = _record(store, "m2", "The output is incorrect.")
        with pytest.raises(PermissionError):
            store.approve("RobloxGame", first["id"])
        with pytest.raises(PermissionError):
            store.dismiss("RobloxGame", second["id"])
        approved = store.approve("RobloxGame", first["id"], human_approved=True)
        assert approved["status"] == "approved"
        dismissed = store.dismiss("RobloxGame", second["id"], human_approved=True)
        assert dismissed["status"] == "dismissed"
        assert len(store.as_failures("RobloxGame")) == 1
        assert store.withdraw(project="RobloxGame", source="app", ref="m1") == 0
    finally:
        store.close()
    status = cr.handle_action(tmp_path, "RobloxGame", "listCorrections", {})
    assert status["counts"] == {"candidate": 0, "approved": 1, "dismissed": 1}
    assert load_catalog(tmp_path / "corrections" / status["suite"])[0].id == "CR-0001"
    for action, body, error in (
        ("unsafeAction", {}, PermissionError),
        ("listCorrections", [], ValueError),
        ("reviewCorrection", {"op": "delete", "id": 1}, ValueError),
        ("reviewCorrection", {"op": "approve", "id": 1}, PermissionError),
    ):
        with pytest.raises(error):
            cr.handle_action(tmp_path, "RobloxGame", action, body)
