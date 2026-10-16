"""Offline deterministic contract tests for live STAR worker status."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from star.discord_bot.work_status import (
    WorkSettings, classify_work_question, format_work_report, parse_work_report, read_work_report,
)

NOW = datetime(2026, 10, 15, 23, 0, tzinfo=timezone.utc)


def receipt(**changes):
    record = {
        "version": 1, "updated_at": "2026-10-15T22:59:30Z",
        "workers": [
            {
                "id": "brain1-coder", "kind": "coding", "state": "working",
                "task": "Fix Luau module type false positives",
                "last_step": "Reproduced the failure with six fixtures",
                "next_step": "Run the regression suite",
                "done": 4, "total": 9, "updated_at": "2026-10-15T22:59:10Z",
            },
            {
                "id": "night-school", "kind": "studying", "state": "working",
                "task": "Study Roblox DataStore race conditions",
                "last_step": "Parsed official documentation",
                "next_step": "Write verified practice answers",
                "done": 2, "total": 6, "updated_at": "2026-10-15T22:59:11Z",
            },
        ]
    }
    record.update(changes)
    return record


def to_bytes(value):
    return json.dumps(value).encode("utf-8")


def test_opt_in_requires_absolute_owner_selected_report(tmp_path):
    assert WorkSettings.from_env({}) == WorkSettings()
    assert WorkSettings.from_env({"STAR_DISCORD_WORK_STATUS": "0",
                                  "STAR_DISCORD_WORK_REPORT": "invalid"}) == WorkSettings()
    expected = tmp_path / "work.json"
    cfg = WorkSettings.from_env({"STAR_DISCORD_WORK_STATUS": "1",
                                 "STAR_DISCORD_WORK_REPORT": str(expected)})
    assert cfg.enabled and cfg.report_path == expected
    for bad in ("yes", "true", "2"):
        with pytest.raises(ValueError, match="must be 0 or 1"):
            WorkSettings.from_env({"STAR_DISCORD_WORK_STATUS": bad})
    for bad in ("", "relative.json", str(tmp_path / "not-txt.txt")):
        with pytest.raises(ValueError, match="absolute .json"):
            WorkSettings.from_env({"STAR_DISCORD_WORK_STATUS": "1",
                                   "STAR_DISCORD_WORK_REPORT": bad})


def test_reports_show_real_parallel_work_and_progress(tmp_path):
    path = tmp_path / "work.json"
    path.write_bytes(to_bytes(receipt()))
    snapshot = read_work_report(WorkSettings(True, path))
    text = format_work_report(snapshot, now=NOW)
    assert "Coding · Working" in text and "Studying · Working" in text
    assert "Fix Luau module type false positives" in text
    assert "checks 4/9" in text
    assert "Last recorded action" in text and "Next recorded step" in text
    assert "not independently verified" in text.lower()


def test_stale_is_unknown_not_fake_background_activity():
    snap = parse_work_report(to_bytes(receipt()))
    stale = format_work_report(snap, now=NOW + timedelta(hours=2))
    assert "can't confirm" in stale and "stale" in stale
    assert "Coding · Working" not in stale
    pending = receipt(workers=[{**receipt()["workers"][0], "state": "waiting"}])
    text = format_work_report(parse_work_report(to_bytes(pending)), now=NOW)
    assert "Active now:** No fresh worker" in text and "Coding · Waiting" in text


def test_finished_is_not_described_as_running():
    completed = receipt(workers=[{**receipt()["workers"][0], "state": "completed"}])
    text = format_work_report(parse_work_report(to_bytes(completed)), now=NOW)
    assert "Coding · Completed" in text and "No fresh worker" in text
    text = format_work_report(parse_work_report(to_bytes(receipt(workers=[]))), now=NOW)
    assert "No worker jobs" in text


def test_reject_injection_secrets_and_fake_metrics():
    sample = receipt()
    original = sample["workers"][0]
    invalid_workers = [
        [{**original, "task": "@everyone take this secret"}],
        [{**original, "task": "Read C:\\Users\\Secret\\keys.txt"}],
        [{**original, "last_step": "run `powershell`"}],
        [{**original, "next_step": "https://example.test/secret"}],
        [{**original, "task": "good\\nbad"}],
        [{**original, "done": 1000, "total": 9}],
        [{**original, "done": True}],
        [{**original, "id": "../file"}],
        [{**original, "kind": ["coding"]}],
        [{**original, "state": "superintelligent"}],
        [{**original, "updated_at": "2026-10-17T00:00:00Z"}],
        [{**original, "extra": "prompt"}],
        [original, original],
    ]
    for workers in invalid_workers:
        with pytest.raises((ValueError, TypeError)):
            parse_work_report(to_bytes(receipt(workers=workers)))
    for bad in ({"version": 2}, {"version": True}, {"updated_at": "now"},
                {"workers": "any"}, {"workers": [original] * 13},
                {"private_key": "secret"}):
        with pytest.raises(ValueError):
            parse_work_report(to_bytes(receipt(**bad)))
    with pytest.raises(ValueError):
        parse_work_report(to_bytes(sample) + b"x" * 20000)


def test_refuses_external_symlink(tmp_path):
    outside = tmp_path / "private.json"
    outside.write_bytes(to_bytes(receipt()))
    link = tmp_path / "work.json"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Host cannot create symlinks")
    with pytest.raises(ValueError, match="not trusted"):
        read_work_report(WorkSettings(True, link))


@pytest.mark.parametrize("question", [
    "STAR, what are you working on?", "hey Star AI, what are you doing right now",
    "What are your agents doing?", "Are you coding?", "what are you studying?",
    "What is Brain 2 working on?", "Show me your progress",
])
def test_natural_work_questions_are_factual_intents(question):
    assert classify_work_question(question)


@pytest.mark.parametrize("question", [
    "Write a scene where Star is coding", "What are you doing in this picture?",
    "Show me code to check active users", "How does studying work?", "",
])
def test_unrelated_chat_keeps_its_original_routing(question):
    assert not classify_work_question(question)
