"""Nightly refresh: what it does when a fetch fails, when nothing changed, and while the lock is held.

No network, no git, no model: the fetch step and the lock are replaced. Run on the PC:
    python -m pytest -q server/knowledge/tests
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starkb import refresh, store  # noqa: E402

MANIFEST = ('{"sources": [{"name": "creator-docs", "repo": "r", "branch": "main", "licence": "l", "attribution": "a", '
            '"content_root": "content/en-us", "public_base": "https://example.invalid"}]}')


def make_home(tmp_path: Path) -> tuple[Path, Path, Path]:
    home, app = tmp_path / "home", tmp_path / "app"
    (home / "data").mkdir(parents=True)
    (home / "sources").mkdir()
    (app / "eval").mkdir(parents=True)
    (app / "corpora.json").write_text(MANIFEST)
    index = home / "data" / "kb.sqlite3"
    db = store.connect(index)
    db.execute(store.FTS)
    doc = db.execute("INSERT INTO docs(source,path,kind,title,url) VALUES('creator-docs','content/en-us/a.md','guide','A','u')").lastrowid
    rowid = db.execute("INSERT INTO chunks(doc_id,ord,kind,heading,anchor,text,idents,text_sha) VALUES(?,0,'guide','A','','tween text','','sha-a')",
                       (doc,)).lastrowid
    db.execute("INSERT INTO chunks_fts(rowid,title,heading,idents,text,questions) VALUES(?,'A','A','','tween text','')", (rowid,))
    db.execute("INSERT OR REPLACE INTO meta VALUES('built_at','2026-01-01T00:00:00+00:00')")
    db.commit()
    db.close()
    return home, app, index


def snapshot(index: Path) -> tuple:
    db = store.connect(index)
    try:
        return (db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
                db.execute("SELECT value FROM meta WHERE name='built_at'").fetchone()[0],
                db.execute("SELECT COUNT(*) FROM chunks_fts WHERE chunks_fts MATCH 'tween'").fetchone()[0])
    finally:
        db.close()


def test_a_failed_fetch_leaves_the_index_alone_and_is_reported(tmp_path, monkeypatch):
    home, app, index = make_home(tmp_path)
    monkeypatch.setattr(refresh, "lock_held", lambda: False)
    before = snapshot(index)

    def fetch(sources_dir, config):
        raise RuntimeError("git fetch failed in creator-docs: could not resolve host")

    result = refresh.run(index, home, app, log=lambda _m: None, stop=lambda: False, fetch=fetch)
    assert result["status"] == "fetch-failed" and "could not resolve host" in result["error"]
    assert snapshot(index) == before
    line = (home / "data" / refresh.REPORT_NAME).read_text().strip()
    assert "status=fetch-failed" in line and line.startswith(result["at"]) and "took=" in line


def test_unchanged_sources_are_not_rebuilt(tmp_path, monkeypatch):
    home, app, index = make_home(tmp_path)
    monkeypatch.setattr(refresh, "lock_held", lambda: False)
    monkeypatch.setattr(store, "build", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not rebuild")))
    before = snapshot(index)
    fetch = lambda sources_dir, config: [{"name": "creator-docs", "repo": sources_dir / "creator-docs", "old": "a" * 40, "new": "a" * 40}]
    result = refresh.run(index, home, app, log=lambda _m: None, stop=lambda: False, fetch=fetch, check=False)
    assert result["status"] == "unchanged" and result["chunks"] == 1 and snapshot(index) == before
    line = (home / "data" / refresh.REPORT_NAME).read_text().strip()
    assert "status=unchanged creator-docs=aaaaaaa chunks=1" in line


def test_it_does_not_run_while_the_lock_is_held(tmp_path, monkeypatch):
    home, app, index = make_home(tmp_path)
    monkeypatch.setattr(refresh, "lock_held", lambda: True)
    monkeypatch.setattr(refresh.time, "sleep", lambda _s: None)
    called = []
    result = refresh.run(index, home, app, max_wait=45, log=lambda _m: None, stop=lambda: False,
                         fetch=lambda *a: called.append(1))
    assert result["status"] == "skipped-lock" and not called
    assert "status=skipped-lock" in (home / "data" / refresh.REPORT_NAME).read_text()


def test_a_refused_rebuild_puts_the_checkouts_back(tmp_path, monkeypatch):
    home, app, index = make_home(tmp_path)
    monkeypatch.setattr(refresh, "lock_held", lambda: False)
    resets = []
    monkeypatch.setattr(refresh, "_git", lambda repo, *args, **kw: resets.append(args[-1]) or "")

    def refuse(*a, **k):
        raise store.RebuildRefused("the rebuild has 0 chunks, the working index has 1; kept the working index")

    monkeypatch.setattr(refresh, "build", refuse)
    before = snapshot(index)
    fetch = lambda sources_dir, config: [{"name": "creator-docs", "repo": sources_dir / "creator-docs", "old": "a" * 40, "new": "b" * 40}]
    result = refresh.run(index, home, app, log=lambda _m: None, stop=lambda: False, fetch=fetch)
    assert result["status"] == "rebuild-refused" and snapshot(index) == before
    assert resets == ["b" * 40, "a" * 40]          # moved forward, then back to what the index was built from
    assert "creator-docs=aaaaaaa>bbbbbbb" in (home / "data" / refresh.REPORT_NAME).read_text()
