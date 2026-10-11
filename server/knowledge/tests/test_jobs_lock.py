"""Quiet-lock regression tests for every knowledge batch worker.

All time advances are synthetic; no network, model, real sleeping, or keyring.
"""
from pathlib import Path
import json
import os
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starkb import corpus_plan, coverage, embed, quiet, refresh, store, study  # noqa: E402
from starkb.chunking import Chunk, Doc  # noqa: E402
from corpus_fixture import snapshot  # noqa: E402


class FakeClock:
    def __init__(self, lock: Path, release_after: float | None = 10.0):
        self.lock = lock
        self.now = 2_000_000_000.0
        self.release_after = release_after
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def arm(self) -> None:
        self.lock.mkdir()
        (self.lock / "owner").write_text("timing", encoding="utf-8")
        os.utime(self.lock, (self.now, self.now))
        os.utime(self.lock / "owner", (self.now, self.now))

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds
        if self.release_after is not None and sum(self.sleeps) >= self.release_after:
            (self.lock / "owner").unlink(missing_ok=True)
            if self.lock.exists():
                self.lock.rmdir()


@pytest.fixture
def fake_clock(tmp_path, monkeypatch):
    clock = FakeClock(tmp_path / "lock")
    monkeypatch.setattr(quiet, "LOCK_DIR", clock.lock)
    monkeypatch.setattr(quiet.time, "time", clock.time)
    monkeypatch.setattr(quiet.time, "sleep", clock.sleep)
    return clock


def assert_paused_once(messages: list[str]) -> None:
    assert sum("server lock present, pausing" in m for m in messages) == 1
    assert sum("continuing after" in m for m in messages) == 1


def test_shared_gate_uses_owner_stamp_and_exact_15_minute_stale_boundary(fake_clock):
    clock = fake_clock
    assert quiet.STALE_SECONDS == 900
    assert not quiet.lock_held()
    clock.arm()
    os.utime(clock.lock, (clock.now - 1000, clock.now - 1000))
    assert quiet.lock_held()  # fresh owner overrides the older directory timestamp
    clock.now += 899
    assert quiet.lock_held()
    clock.now += 1
    assert not quiet.lock_held()  # exactly 15 minutes is stale, without unlinking the lock
    assert clock.lock.exists() and (clock.lock / "owner").exists()
    clock.now -= 900
    messages = []
    waited = quiet.wait_while_locked(log=messages.append, poll=5)
    assert waited == 10 and clock.sleeps == [5, 5]
    assert_paused_once(messages)


def test_shared_gate_times_out_and_stops_without_a_false_resume(fake_clock):
    clock = fake_clock
    clock.release_after = None
    clock.arm()
    messages = []
    assert quiet.wait_while_locked(log=messages.append, poll=7, max_wait=15) is None
    assert clock.sleeps == [7, 7, 1]
    assert sum("pausing" in m for m in messages) == 1
    assert not any("continuing" in m for m in messages)
    assert "maximum wait" in messages[-1]
    assert quiet.wait_while_locked(log=messages.append, stop=lambda: True) == 0


def minimal_index(path: Path, count: int = 2) -> None:
    db = store.connect(path)
    db.execute(store.FTS)
    for i in range(count):
        doc_id = db.execute("INSERT INTO docs(source,path,kind,title,url) VALUES(?,?,?,?,?)",
                            ("fixture", f"{i}.md", "guide", f"Title {i}", "https://example.invalid")).lastrowid
        db.execute("INSERT INTO chunks(doc_id,ord,kind,heading,anchor,text,idents,text_sha) "
                   "VALUES(?,0,'guide',?,'',?,'',?)",
                   (doc_id, f"Heading {i}", f"Index text {i}", f"sha-{i}"))
    db.commit()
    db.close()


def test_embedding_waits_before_the_next_batch(fake_clock, tmp_path, monkeypatch):
    index = tmp_path / "index.sqlite3"
    minimal_index(index)
    starts = []
    clock = fake_clock

    class Brain:
        def embed(self, texts):
            starts.append(clock.now)
            if len(starts) == 1:
                clock.arm()
            return [[1.0, 0.0] for _ in texts], len(texts)

    monkeypatch.setattr(embed, "Brain", Brain)
    messages = []
    result = embed.run(index, batch=1, log=messages.append, stop=lambda: False)
    assert result["embedded_now"] == 2
    assert result["paused_for_lock_s"] == 10
    assert starts == [2_000_000_000.0, 2_000_000_010.0]
    assert_paused_once(messages)


def test_embedding_fallback_checks_between_oversized_items(fake_clock):
    clock = fake_clock
    calls = []

    class Brain:
        def embed(self, texts):
            calls.append((clock.now, list(texts)))
            if len(calls) == 1:
                raise RuntimeError("input too large")
            if len(calls) == 2:
                clock.arm()
            return [[1.0] for _ in texts], 1

    messages = []

    def gate():
        quiet.wait_while_locked(log=messages.append)

    vectors, tokens = embed.embed_batch(Brain(), ["a", "b"], {}, gate=gate)
    assert vectors == [[1.0], [1.0]] and tokens == 2
    assert calls[-1][0] - calls[1][0] == 10
    assert_paused_once(messages)


def test_index_builder_checks_between_documents_and_fts_rows(fake_clock, tmp_path):
    clock = fake_clock
    manifest = tmp_path / "sources.json"
    manifest.write_text(json.dumps({"sources": [{"name": "fixture", "repo": "https://example.invalid",
                         "branch": "main", "content_root": "", "public_base": "https://example.invalid",
                         "licence": "test", "attribution": "test"}]}), encoding="utf-8")

    def docs(_root, _base):
        for i in range(2):
            if i == 1:
                clock.arm()
            document = Doc(path=f"{i}.md", kind="guide", title=f"Title {i}",
                           url="https://example.invalid")
            document.chunks.append(Chunk(kind="guide", heading=f"Title {i}", anchor="",
                                         text=f"Index text {i}", idents=""))
            yield document

    messages = []
    result = store.build(tmp_path / "index.sqlite3", tmp_path, manifest,
                         walkers={"fixture": docs},
                         source_metadata={"fixture": {"commit": "a" * 40, "commit_date": "date"}},
                         log=messages.append)
    assert result["_all"]["chunks"] == 2
    assert clock.sleeps == [5, 5]
    assert_paused_once(messages)


def test_refresh_checks_each_source_fetch_and_respects_timeout(fake_clock, tmp_path):
    clock = fake_clock
    source_dir = tmp_path / "sources"
    for name in ("first", "second"):
        (source_dir / name / ".git").mkdir(parents=True)
    config = {"sources": [{"name": name, "branch": "main"} for name in ("first", "second")]}
    calls = []

    def git(repo, *args):
        calls.append((clock.now, repo.name, args[0]))
        if repo.name == "first" and args[:2] == ("rev-parse", "FETCH_HEAD"):
            clock.arm()
        return "a" * 40

    messages = []
    sources = refresh.fetch_all(source_dir, config, git=git,
                                wait=lambda: refresh.wait_for_quiet(60, lambda: False, messages.append))
    assert len(sources) == 2
    assert calls[3][1] == "second" and calls[3][0] == calls[2][0] + 15
    assert_paused_once(messages)

    clock.release_after = None
    clock.sleeps.clear()
    clock.arm()
    messages.clear()
    assert not refresh.wait_for_quiet(30, lambda: False, messages.append)
    assert clock.sleeps == [15, 15]
    assert not any("continuing" in m for m in messages)


def test_corpus_planning_pauses_between_selected_files(fake_clock, tmp_path, monkeypatch):
    repo, manifest, source = snapshot(tmp_path, files={
        "src/content/docs/a.md": "# First\nEvidence for A.\n",
        "src/content/docs/b.md": "# Second\nEvidence for B.\n",
    })
    real_read = corpus_plan.tracked_read
    reads = []

    def read(*args, **kwargs):
        data = real_read(*args, **kwargs)
        reads.append(args[1])
        if len(reads) == 1:
            fake_clock.arm()
        return data

    monkeypatch.setattr(corpus_plan, "tracked_read", read)
    report = corpus_plan.plan(manifest, repo.parent)
    assert report["sources"][0]["status"] == "verified-local"
    assert reads == source["paths"]
    assert fake_clock.sleeps == [5, 5]


def test_coverage_checker_pauses_between_lookup_batches(fake_clock, tmp_path, monkeypatch):
    monkeypatch.setattr(coverage, "MAX_SYMBOLS", 1)
    monkeypatch.setattr(coverage, "symbols_from_sources",
                        lambda *_args: ([("class", "First"), ("class", "Second")], []))

    class DB:
        def close(self):
            pass

    monkeypatch.setattr(coverage, "connect_readonly", lambda *_args: DB())
    calls = []

    def lookup(_db, symbols):
        calls.append(fake_clock.now)
        if len(calls) == 1:
            fake_clock.arm()
        return [{"found": True} for _ in symbols]

    monkeypatch.setattr(coverage, "api_lookup", lookup)
    result = coverage.run(tmp_path / "unused.db", tmp_path, tmp_path / "unused.json")
    assert result["symbols"] == 2 and result["found"] == 2
    assert calls[1] - calls[0] == 10
    assert fake_clock.sleeps == [5, 5]


def test_study_plan_checks_between_scanned_documents(fake_clock, tmp_path, monkeypatch):
    sources = tmp_path / "sources"
    content = sources / "fixture" / "docs"
    content.mkdir(parents=True)
    (content / "a.md").write_text("# First\nSee the docs.\n", encoding="utf-8")
    (content / "b.md").write_text("# Second\nSee the docs.\n", encoding="utf-8")
    manifest = tmp_path / "corpora.json"
    manifest.write_text(json.dumps({"sources": [{"name": "fixture", "content_root": "docs"}]}),
                        encoding="utf-8")
    index = tmp_path / "index.sqlite3"
    store.connect(index).close()
    count = 0
    original = quiet.wait_while_locked

    def gate(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            fake_clock.arm()
        return original(*args, **kwargs)

    monkeypatch.setattr(study, "wait_while_locked", gate)
    order, stats = study.plan(index, sources, manifest)
    assert order == [] and stats["size"] == 0
    assert count == 2 and fake_clock.sleeps == [5, 5]


def test_initial_fetch_script_uses_shared_quiet_gate_per_checkout():
    script = (Path(__file__).resolve().parents[1] / "fetch.sh").read_text(encoding="utf-8")
    assert script.index("while read -r NAME REPO BRANCH") < script.index("python3 -m starkb.quiet")
    assert script.index("python3 -m starkb.quiet") < script.index('DEST="$HOME_DIR/sources/$NAME"')

def test_full_text_index_migration_checks_between_rows(fake_clock, tmp_path, monkeypatch):
    index = tmp_path / "index.sqlite3"
    minimal_index(index)
    db = store.connect(index)
    actual = quiet.wait_while_locked
    checkpoints = []

    def gate(*args, **kwargs):
        checkpoints.append(fake_clock.now)
        if len(checkpoints) == 3:
            fake_clock.arm()
        return actual(*args, **kwargs)

    monkeypatch.setattr(store, "wait_while_locked", gate)
    try:
        assert store.rebuild_fts(db) == 2
        assert db.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0] == 2
    finally:
        db.close()
    assert len(checkpoints) == 3
    assert fake_clock.sleeps == [5, 5]


@pytest.mark.parametrize("walker", ["creator", "luau"])
def test_document_walkers_pause_between_source_files(fake_clock, tmp_path, monkeypatch, walker):
    root = tmp_path / "source"
    docs = root if walker == "creator" else root / "docs"
    docs.mkdir(parents=True)
    for name in ("a.md", "b.md"):
        (docs / name).write_text("# Example\\nEvidence.\\n", encoding="utf-8")
    parsed = []

    def parse(raw, *, path, url, **_kwargs):
        parsed.append(path)
        if len(parsed) == 1:
            fake_clock.arm()
        document = Doc(path=path, kind="guide", title=path, url=url)
        document.chunks.append(Chunk(kind="guide", heading=path, anchor="", text=raw, idents=""))
        return document

    monkeypatch.setattr(store, "chunk_markdown", parse)
    make_docs = store._creator_docs if walker == "creator" else store._luau_site
    assert len(list(make_docs(root, "https://example.invalid"))) == 2
    assert len(parsed) == 2 and fake_clock.sleeps == [5, 5]
