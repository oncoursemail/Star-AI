"""Unit tests for the GPU training pilot scripts (server/training/gpu): data building and the paired comparison.
No model, no GPU: only the parts that decide WHAT is trained on and HOW a result is judged."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys

import pytest

GPU = Path(__file__).resolve().parents[1] / "server" / "training" / "gpu"
sys.path.insert(0, str(GPU))

import build_pairs  # noqa: E402
import eval_retrieval  # noqa: E402
import gen_queries  # noqa: E402


def first_heldout() -> dict:
    for line in (build_pairs.KNOWLEDGE / "eval" / "heldout.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("//"):
            return json.loads(line)
    raise AssertionError("no held-out question")


def make_db(path: Path) -> None:
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE sources(name TEXT PRIMARY KEY, repo TEXT, branch TEXT, commit_sha TEXT, commit_date TEXT,
                             licence TEXT, attribution TEXT, indexed_at TEXT);
        CREATE TABLE docs(id INTEGER PRIMARY KEY, source TEXT, path TEXT, kind TEXT, title TEXT, url TEXT);
        CREATE TABLE chunks(id INTEGER PRIMARY KEY, doc_id INTEGER, ord INTEGER, kind TEXT, heading TEXT, anchor TEXT,
                            text TEXT, idents TEXT, text_sha TEXT);
        CREATE TABLE chunk_questions(id INTEGER PRIMARY KEY, text_sha TEXT, ord INTEGER, question TEXT, q_sha TEXT,
                                     model TEXT, created_at TEXT);
    """)
    db.execute("INSERT INTO sources VALUES('creator-docs','https://example.invalid/docs.git','main','abc','d',"
               "'CC-BY-4.0','attr','t')")
    # an evaluation answer page (the first held-out question's expected page) and an ordinary page
    db.execute("INSERT INTO docs VALUES(1,'creator-docs',?,'guide','Versioning','u')", (first_heldout()["expected"][0],))
    db.execute("INSERT INTO docs VALUES(2,'creator-docs','content/en-us/other/page.md','guide','Other','u')")
    db.execute("INSERT INTO docs VALUES(3,'creator-docs','content/en-us/news/n.md','news','News','u')")
    long = "x " * 150
    db.execute("INSERT INTO chunks VALUES(1,1,0,'guide','Versions','a','Data store versions ' || ?,'', 'sha-eval')", (long,))
    db.execute("INSERT INTO chunks VALUES(2,2,0,'guide','Part','a','Some other page ' || ?,'', 'sha-other')", (long,))
    db.execute("INSERT INTO chunks VALUES(3,3,0,'news','N','a','Release notes ' || ?,'', 'sha-news')", (long,))
    db.execute("INSERT INTO chunk_questions VALUES(1,'sha-other',0,'How do I move a part smoothly?','q','star-quick/q1','t')")
    db.commit()
    db.close()


def eval_question() -> str:
    return first_heldout()["question"]


def run_build(tmp_path: Path, monkeypatch, *extra: str) -> tuple[list[dict], dict]:
    db = tmp_path / "kb.sqlite3"
    make_db(db)
    queries = tmp_path / "q.jsonl"
    prov = {"generator": "local-open-model", "claude_or_chatgpt_involved": False}
    rows = [
        {"text_sha": "sha-other", "ok": True, "question": "How can I make a brick glide across the map nicely?",
         "task": "Write a script that slides a block from A to B over two seconds and then stops at B.", "provenance": prov},
        {"text_sha": "sha-other", "ok": True, "question": eval_question(), "task": "unrelated words here for the task "
         "field so that it passes length checks easily and fully", "provenance": prov},
        {"text_sha": "sha-eval", "ok": True, "question": "Where do I find old saved copies of my stored values?",
         "task": "Build an admin command that lists previous saved versions of a player's stored record.", "provenance": prov},
        {"text_sha": "sha-other", "ok": False, "question": "bad", "task": "bad", "provenance": prov},
    ]
    queries.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    out = tmp_path / "pairs.jsonl"
    monkeypatch.setattr(sys, "argv", ["build_pairs", "--db", str(db), "--queries", str(queries), "--out", str(out), *extra])
    build_pairs.main()
    pairs = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    manifest = json.loads(out.with_suffix(".manifest.json").read_text())
    return pairs, manifest


def test_pairs_drop_eval_lookalikes_and_bad_rows(tmp_path, monkeypatch):
    pairs, manifest = run_build(tmp_path, monkeypatch)
    anchors = [p["anchor"] for p in pairs]
    assert not any(eval_question() in a for a in anchors), "an evaluation question must never become training data"
    assert manifest["dropped"]["too similar to an evaluation question"] >= 1
    assert all(a.startswith("task: search result | query: ") for a in anchors)
    assert all(p["positive"].startswith("title: ") for p in pairs)
    assert manifest["claude_or_chatgpt_outputs_used"] is False
    assert {p["origin"] for p in pairs} == {"synthetic-question", "synthetic-task", "doc2query-index"}
    assert all(p["provenance"]["doc_source"]["licence"] == "CC-BY-4.0" for p in pairs)
    assert manifest["eval_pages_in_training"] == 1


def test_strict_variant_leaves_out_evaluation_pages(tmp_path, monkeypatch):
    pairs, manifest = run_build(tmp_path, monkeypatch, "--exclude-eval-pages")
    assert all(p["text_sha"] != "sha-eval" for p in pairs)
    assert manifest["eval_pages_in_training"] == 0
    assert manifest["dropped"]["page is an evaluation answer (strict variant)"] == 2


def test_sampler_skips_news_and_excluded_pages(tmp_path):
    db_path = tmp_path / "kb.sqlite3"
    make_db(db_path)
    db = sqlite3.connect(db_path)
    picked = gen_queries.sample_chunks(db, 100, 1, set())
    assert {c["text_sha"] for c in picked} == {"sha-eval", "sha-other"}
    picked = gen_queries.sample_chunks(db, 100, 1, {"content/en-us/other/page.md"})
    assert {c["text_sha"] for c in picked} == {"sha-eval"}
    db.close()


def test_sign_test_and_compare(tmp_path):
    assert eval_retrieval.sign_test(0, 0) == 1.0
    assert eval_retrieval.sign_test(5, 0) == pytest.approx(1 / 32)
    assert eval_retrieval.sign_test(3, 1) == pytest.approx(5 / 16)
    a = {"sets": {"golden": {"ranks": {"vector": {"q1": 1, "q2": None, "q3": 7, "q4": 2}}}}}
    b = {"sets": {"golden": {"ranks": {"vector": {"q1": 1, "q2": 3, "q3": 4, "q4": 9}}}}}
    (tmp_path / "a.json").write_text(json.dumps(a))
    (tmp_path / "b.json").write_text(json.dumps(b))
    rep = eval_retrieval.compare(tmp_path / "a.json", tmp_path / "b.json")["golden/vector"]
    assert (rep["a"], rep["b"], rep["wins"], rep["losses"]) == (2, 3, ["q2", "q3"], ["q4"])
