"""Execute the proposal pipeline and real CLI/SQLite reader without a model or desktop."""
import copy
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sqlite3
import subprocess
import sys

import pytest

from star.lessons_hygiene import OverrideObservation, build_report, main, read_database, token_overlap

FIXTURE = Path(__file__).parent / "fixtures" / "lessons_hygiene.json"
CLOCK = datetime(2026, 10, 12, tzinfo=timezone.utc)


@pytest.fixture
def forty():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(fixture["lessons"]) == 40
    return fixture


def report(forty, **kwargs):
    return build_report(forty["lessons"], as_of=CLOCK,
                        overrides=[OverrideObservation(**item) for item in forty["overrides"]], **kwargs)


def pairs(result, kind):
    return {proposal.lesson_ids for proposal in result.proposals if proposal.kind == kind}


def two(forty, first, second, **kwargs):
    rows = [dict(forty["lessons"][0], id=1, text=first),
            dict(forty["lessons"][0], id=2, text=second)]
    return build_report(rows, as_of=CLOCK, **kwargs)


def test_forty_lesson_oracle_and_no_input_mutation(forty):
    before = copy.deepcopy(forty)
    result = report(forty)
    assert result.scanned == 40 and result.review_required is True
    assert pairs(result, "merge") == {(1, 2), (3, 4)}
    assert pairs(result, "contradiction") == {(5, 6), (7, 8), (9, 10), (11, 12), (35, 36)}
    assert pairs(result, "stale") == {(13,), (14,), (15,), (17,)}
    assert pairs(result, "scope") == {(23,), (27,), (28,)}
    assert result.warnings == ()
    assert forty == before
    shuffled = list(forty["lessons"])
    random.Random(11).shuffle(shuffled)
    assert report({**forty, "lessons": iter(shuffled)}) == result
    with pytest.raises(FrozenInstanceError):
        result.review_required = False
    assert json.loads(json.dumps(result.public()))["review_required"] is True


def test_more_specific_exact_wording_and_both_evidence_links_survive(forty):
    result = report(forty)
    merged = next(item for item in result.proposals if item.lesson_ids == (1, 2))
    assert merged.keep_id == 2
    assert merged.suggested_text == forty["lessons"][1]["text"]
    assert [(item.lesson_id, item.source, item.evidence) for item in merged.evidence] == [
        (row["id"], row["source"], row["evidence"]) for row in forty["lessons"][:2]
    ]
    # A proposal's preferred wording does not approve the candidate supplying it.
    assert forty["lessons"][1]["status"] == "candidate"
    tied = two(forty, "Use stable widget identifiers.", "Please please use stable widget identifiers.")
    assert next(item for item in tied.proposals if item.kind == "merge").keep_id == 1


def test_injected_embeddings_find_a_lexically_different_paraphrase_and_are_cached(forty):
    texts = sorted({row["text"] for row in forty["lessons"] if row["status"] in {"accepted", "candidate"}})
    first, second = (forty["lessons"][i]["text"] for i in (30, 31))
    dimensions = {text: i for i, text in enumerate(texts)}
    dimensions[second] = dimensions[first]
    calls = []

    def embed(text):
        calls.append(text)
        return [1.0 if i == dimensions[text] else 0.0 for i in range(len(texts))]

    result = report(forty, embed=embed)
    assert pairs(result, "merge") == {(1, 2), (3, 4), (31, 32)}
    assert sorted(calls) == texts
    proposal = next(item for item in result.proposals if item.lesson_ids == (31, 32))
    assert proposal.embedding_similarity == pytest.approx(1)
    assert proposal.token_overlap < 0.8
    assert "injected embedding" in proposal.reason
    assert pairs(result, "contradiction") == pairs(report(forty), "contradiction")


@pytest.mark.parametrize("first, second", [
    ("Always use polling for lobby readiness.", "Never use polling for lobby readiness."),
    ("Use polling for lobby readiness.", "Don't use polling for lobby readiness."),
    ("Use polling for lobby readiness.", "Do not use polling for lobby readiness."),
    ("Use polling for lobby readiness.", "Avoid using polling for lobby readiness."),
    ("Use polling for lobby readiness.", "Stop using polling for lobby readiness."),
    ("Enable streaming for terrain chunks.", "Disable streaming for terrain chunks."),
    ("Turn on terrain streaming.", "Turn off terrain streaming."),
    ("Include debug overlays in production builds.", "Exclude debug overlays from production builds."),
    ("Allow nested inventory transfers.", "Disallow nested inventory transfers."),
    ("Keep orphaned inventory connections.", "Remove orphaned inventory connections."),
    ("Prefer camelCase over snake_case.", "Prefer snake_case over camelCase."),
    ("Use task.wait instead of wait.", "Use wait instead of task.wait."),
    ("Never use polling. Always use lobby signals.", "Never use lobby signals."),
    ("Do not avoid terrain streaming.", "Avoid terrain streaming."),
])
def test_opposites_are_not_merged_even_with_identical_embeddings(forty, first, second):
    result = two(forty, first, second, embed=lambda _: [1.0, 0.0])
    assert pairs(result, "contradiction") == {(1, 2)}
    assert pairs(result, "merge") == set()


@pytest.mark.parametrize("first, second", [
    ("Keep UI logic in LocalScripts.", "Never keep game logic in LocalScripts."),
    ("Use terrain streaming.", "Never use inventory polling."),
    ("Never use polling. Always use lobby signals.", "Use lobby signals."),
])
def test_shared_words_or_negation_in_another_clause_are_not_contradictions(forty, first, second):
    assert pairs(two(forty, first, second), "contradiction") == set()


@pytest.mark.parametrize("first, second", [
    ("Cap inventory refresh batches at 20 items.", "Cap inventory refresh batches at 40 items."),
    ("Use task.wait for timed loops.", "Use task.wait for timed loops only when the timer is enabled."),
    ("Use terrain streaming without physics streaming.", "Use terrain streaming with physics streaming."),
])
def test_conflicting_numbers_and_unmatched_exceptions_block_semantic_merge(forty, first, second):
    assert not pairs(two(forty, first, second, embed=lambda _: [1.0]), "merge")


@pytest.mark.parametrize("vector", [[], [0, 0], [float("nan"), 1], [float("inf")], "123", None])
def test_invalid_embeddings_fall_back_to_lexical_matching(forty, vector):
    result = two(forty, "Use stable widget identifiers.", "Always use stable widget identifiers.",
                 embed=lambda _: vector)
    assert pairs(result, "merge") == {(1, 2)}
    assert any("embedding unavailable" in warning for warning in result.warnings)


def test_embedding_failure_and_dimension_mismatch_do_not_abort_or_echo_exception(forty):
    def unavailable(_):
        raise RuntimeError("unexpected fixture marker")

    result = report(forty, embed=unavailable)
    assert pairs(result, "merge") == {(1, 2), (3, 4)}
    assert "unexpected fixture marker" not in json.dumps(result.public())
    result = two(forty, "Use stable widget identifiers.", "Always use stable widget identifiers.",
                 embed=lambda text: [1.0] if text.startswith("Use") else [1.0, 0.0])
    assert pairs(result, "merge") == {(1, 2)}
    assert any("dimensions differ" in warning for warning in result.warnings)


def test_embedding_scaling_avoids_overflow_and_threshold_is_configurable(forty):
    result = two(forty, "Backpack contents survive reconnects.", "Persist inventory between sessions.",
                 embed=lambda _: [1e308, 1e308])
    assert pairs(result, "merge") == {(1, 2)}
    assert all(item.embedding_similarity == pytest.approx(1) for item in result.proposals)
    result = two(forty, "Backpack contents survive reconnects.", "Persist inventory between sessions.",
                 embed=lambda text: [1.0, 0.0] if text.startswith("Backpack") else [0.9, 0.436],
                 embedding_threshold=0.99)
    assert not pairs(result, "merge")


def test_no_cross_project_merge_or_contradiction(forty):
    rows = [dict(forty["lessons"][0], project="DemoA"),
            dict(forty["lessons"][0], id=2, project="DemoB")]
    assert not build_report(rows, as_of=CLOCK, embed=lambda _: [1]).proposals
    rows[1]["text"] = "Never use camelCase for local variables."
    assert not build_report(rows, as_of=CLOCK, embed=lambda _: [1]).proposals


def test_global_scope_catalog_explicit_names_and_boundary_negatives(forty):
    scopes = {p.lesson_ids[0]: p.suggested_project for p in report(forty).proposals if p.kind == "scope"}
    assert scopes == {23: "DemoA", 27: "Harbor Tools", 28: "DemoB"}
    result = two(forty, "Use parchment panels for DemoA menus.", "Use parchment panels for menus.")
    assert not pairs(result, "scope")  # already project-scoped
    rows = [dict(forty["lessons"][0], project="global", text='Use tabs for project Nebula.'),
            dict(forty["lessons"][0], id=2, project="global", text="Use tabs for this project.")]
    result = build_report(rows, as_of=CLOCK, embed=lambda _: [1])
    assert pairs(result, "scope") == {(1,)}
    assert next(item for item in result.proposals if item.kind == "scope").suggested_project == "Nebula"
    assert not pairs(result, "merge")  # named global guidance must not absorb generic guidance


def test_scope_case_and_configured_global_label(forty):
    rows = [dict(forty["lessons"][0], project="Shared", text="Use compact tabs for DEMOA menus.")]
    result = build_report(rows, as_of=CLOCK, global_projects=["Shared"], project_names=["DemoA", "demoa"])
    assert pairs(result, "scope") == {(1,)}
    assert next(item for item in result.proposals if item.kind == "scope").suggested_project == "DemoA"


def test_staleness_cutoff_creation_last_use_and_review_timestamps(forty):
    result = report(forty)
    stale = {p.lesson_ids[0]: p.reason for p in result.proposals if p.kind == "stale"}
    assert "Never recalled" in stale[13] and "last use" in stale[14]
    assert 17 in stale and 18 not in stale  # exact N-day boundary and one second younger
    assert all(i not in stale for i in (19, 20, 21, 22))  # deliberately untrusted/retired
    rows = [dict(forty["lessons"][13], last_used="2026-10-11T00:00:00Z")]
    assert not pairs(build_report(rows, as_of=CLOCK), "stale")
    rows = [dict(forty["lessons"][16], created="2026-07-14T02:00:00+02:00")]
    assert pairs(build_report(rows, as_of=CLOCK), "stale") == {(17,)}
    rows[0]["created"] = "2026-07-14T00:00:00"
    assert pairs(build_report(rows, as_of=CLOCK), "stale") == {(17,)}


@pytest.mark.parametrize("changes", [
    {"created": "not-a-date"}, {"uses": 1, "last_used": ""},
    {"created": "2027-01-01T00:00:00Z"}, {"uses": 1, "last_used": "2027-01-01T00:00:00Z"},
    {"uses": 1, "last_used": "2025-01-01T00:00:00Z"}, {"uses": 0, "last_used": "2026-10-11T00:00:00Z"},
])
def test_unknown_or_inconsistent_use_dates_are_not_fabricated_staleness(forty, changes):
    rows = [dict(forty["lessons"][12], **changes)]
    result = build_report(rows, as_of=CLOCK)
    assert not pairs(result, "stale")
    assert any("timestamps" in warning for warning in result.warnings)


def test_always_overridden_requires_distinct_observations_and_not_just_use_counts(forty):
    row = forty["lessons"][14]
    result = build_report([row], as_of=CLOCK)
    assert not pairs(result, "stale") and any("overrides" in item for item in result.warnings)
    repeated = OverrideObservation(15, "chat:observed#1", True)
    assert not pairs(build_report([row], as_of=CLOCK, overrides=[repeated] * 5), "stale")
    samples = [OverrideObservation(15, f"chat:observed#{i}", True) for i in range(3)]
    result = build_report([row], as_of=CLOCK, overrides=samples)
    assert pairs(result, "stale") == {(15,)}
    assert len(result.proposals[0].evidence) == 4  # original plus three outcome sources
    samples.append(OverrideObservation(15, "chat:observed#4", False))
    assert not pairs(build_report([row], as_of=CLOCK, overrides=samples), "stale")
    with pytest.raises(ValueError, match="Conflicting"):
        build_report([row], as_of=CLOCK, overrides=[repeated, OverrideObservation(15, repeated.source, False)])


@pytest.mark.parametrize("kwargs", [
    {"stale_days": 0}, {"stale_days": True}, {"stale_days": -2},
    {"minimum_overrides": 0}, {"token_threshold": 0}, {"token_threshold": float("nan")},
    {"embedding_threshold": 1.1}, {"embedding_threshold": True},
])
def test_invalid_thresholds_are_rejected(forty, kwargs):
    with pytest.raises(ValueError):
        report(forty, **kwargs)


@pytest.mark.parametrize("changes", [{"id": True}, {"id": -1}, {"uses": -1}, {"uses": True},
                                     {"text": None}, {"status": "trusted"}, {"evidence": 42}])
def test_invalid_export_records_are_rejected(forty, changes):
    with pytest.raises(ValueError):
        build_report([dict(forty["lessons"][0], **changes)], as_of=CLOCK)


def test_duplicate_ids_and_empty_token_inputs(forty):
    with pytest.raises(ValueError, match="unique"):
        build_report([forty["lessons"][0]] * 2, as_of=CLOCK)
    assert token_overlap("", "Always please use.") == 0
    assert not build_report([], as_of=CLOCK).proposals
    assert not pairs(two(forty, "Always please.", "Please always."), "merge")
    assert pairs(two(forty, "Use camelCase.", "Use camelCase!"), "merge") == {(1, 2)}


@pytest.fixture
def database(tmp_path, forty):
    home = tmp_path / "data with spaces"
    path = home / "knowledge" / "knowledge.sqlite3"
    path.parent.mkdir(parents=True)
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA wal_autocheckpoint=0")
    # Same columns queried from knowledge.py, plus the ordinary note fields. This local
    # harness tests SQL/CLI; test_lessons_hygiene_store.py also opens the real LessonStore.
    db.execute("""CREATE TABLE notes (
        id INTEGER PRIMARY KEY, project TEXT, kind TEXT, text TEXT, status TEXT, source TEXT,
        source_type TEXT, evidence TEXT, created TEXT, updated TEXT, supersedes_id INTEGER,
        merged_into INTEGER, reviewed INTEGER, revision TEXT)""")
    db.execute("CREATE TABLE lesson_use (note_id INTEGER PRIMARY KEY, uses INTEGER, last_used TEXT)")
    for row in forty["lessons"]:
        db.execute("""INSERT INTO notes VALUES (:id,:project,:kind,:text,:status,:source,:source_type,
                   :evidence,:created,:updated,:supersedes_id,:merged_into,:reviewed,'fixture')""",
                   {**row, "reviewed": int(row["status"] == "accepted")})
        if row["uses"]:
            db.execute("INSERT INTO lesson_use VALUES (:id,:uses,:last_used)", row)
    db.execute("INSERT INTO notes(id,project,kind,text,status) VALUES(41,'DemoA','observation','Plain note',NULL)")
    db.commit()
    yield home, path, db
    db.close()


def test_read_only_cli_sees_uncheckpointed_wal_and_preserves_every_row(database, forty, capsys, tmp_path):
    home, path, db = database
    before = (tuple(db.iterdump()), path.read_bytes(), db.total_changes)
    assert len(read_database(path)) == 40
    overrides = tmp_path / "outcomes.json"
    overrides.write_text(json.dumps(forty["overrides"]), encoding="utf-8")
    assert main(["report", "--home", str(home), "--as-of", CLOCK.isoformat(), "--overrides", str(overrides)]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert json.loads(output.out) == json.loads(json.dumps(report(forty).public()))
    assert (tuple(db.iterdump()), path.read_bytes(), db.total_changes) == before


def test_cli_reads_beyond_review_window_and_nullable_evidence(database, capsys):
    home, path, db = database
    for n in range(42, 602):
        db.execute("INSERT INTO notes SELECT ?,project,kind,text,status,source,source_type,NULL,created,"
                   "NULL,supersedes_id,merged_into,reviewed,revision FROM notes WHERE id=20", (n,))
    db.commit()
    assert main(["report", "--home", str(home), "--as-of", CLOCK.isoformat()]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["scanned"] == 600  # all rows, including records beyond list()/page() limits
    assert all(row["evidence"] == "" for row in read_database(path) if row["id"] >= 42)


def test_module_cli_export_filter_and_source_file_unchanged(forty, tmp_path):
    before = FIXTURE.read_bytes()
    command = [sys.executable, "-m", "star.lessons_hygiene", "report", "--input", str(FIXTURE),
               "--project", "global", "--as-of", CLOCK.isoformat()]
    done = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert result["scanned"] == 6
    assert {p["suggested_project"] for p in result["proposals"] if p["kind"] == "scope"} == {
        "DemoA", "DemoB", "Harbor Tools"}
    assert FIXTURE.read_bytes() == before


def test_missing_default_home_creates_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("APPDATA", str(tmp_path / "new-data"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "new-data"))
    before = list(tmp_path.rglob("*"))
    assert main(["report", "--as-of", CLOCK.isoformat()]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["scanned"] == 0 and not result["proposals"]
    assert any("nothing was created" in warning for warning in result["warnings"])
    assert list(tmp_path.rglob("*")) == before
    with pytest.raises(sqlite3.OperationalError):
        read_database(tmp_path / "absent.sqlite3")
    assert list(tmp_path.rglob("*")) == before


def test_old_schema_is_not_migrated(tmp_path, capsys):
    path = tmp_path / "knowledge" / "knowledge.sqlite3"
    path.parent.mkdir()
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE notes(id INTEGER PRIMARY KEY, text TEXT)")
    before = path.read_bytes()
    assert main(["report", "--home", str(tmp_path), "--as-of", CLOCK.isoformat()]) == 2
    output = capsys.readouterr()
    assert not output.out and "Unable to report" in output.err
    assert path.read_bytes() == before


@pytest.mark.parametrize("raw", ["not JSON", "null", "{}", '{"lessons":{}}', '[{"id":1}]'])
def test_cli_malformed_input_fails_without_partial_report(tmp_path, capsys, raw):
    path = tmp_path / "bad.json"
    path.write_text(raw, encoding="utf-8")
    assert main(["report", "--input", str(path)]) == 2
    output = capsys.readouterr()
    assert not output.out and "Unable to report" in output.err
    assert path.read_text(encoding="utf-8") == raw


@pytest.mark.parametrize("extra", [["--stale-days", "0"], ["--as-of", "not-a-date"], ["--as-of", ""]])
def test_cli_rejects_invalid_options(capsys, extra):
    assert main(["report", "--input", str(FIXTURE), *extra]) == 2
    assert "Unable to report" in capsys.readouterr().err


@pytest.mark.parametrize("first, second", [
    ("Use camelCase, not snake_case.", "Use snake_case, not camelCase."),
    ("Always cache inventory snapshots.", "Never cache inventory snapshots."),
    ("Accept nested inventory transfers.", "Reject nested inventory transfers."),
])
def test_additional_opposing_instructions_cannot_merge(forty, first, second):
    result = two(forty, first, second, embed=lambda _: [1.0])
    assert pairs(result, "contradiction") == {(1, 2)} and not pairs(result, "merge")


def test_negative_equivalents_and_signed_numeric_values(forty):
    result = two(forty, "Never use lobby polling.", "Avoid using lobby polling.")
    assert pairs(result, "merge") == {(1, 2)} and not pairs(result, "contradiction")
    result = two(forty, "Set camera tilt to -20 degrees.", "Set camera tilt to 20 degrees.",
                 embed=lambda _: [1.0])
    assert not pairs(result, "merge")


def test_scope_longest_name_and_generic_project_terms(forty):
    rows = [dict(forty["lessons"][0], project="global", text="Use tabs in Project Harbor Tools.")]
    result = build_report(rows, as_of=CLOCK, project_names=["Harbor", "Harbor Tools"])
    assert pairs(result, "scope") == {(1,)}
    assert result.proposals[0].suggested_project == "Harbor Tools"
    rows[0]["text"] = "Project Settings should use readable labels."
    assert not pairs(build_report(rows, as_of=CLOCK), "scope")
    for kwargs in ({"project_names": [None]}, {"global_projects": [None]}):
        with pytest.raises(ValueError):
            build_report(rows, as_of=CLOCK, **kwargs)
