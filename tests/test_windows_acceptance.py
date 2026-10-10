"""The Windows acceptance helper must itself be trustworthy: a script that
passes when it should fail would make issue #15 look done when it is not."""
import hashlib
import http.server
import json
import re
import sqlite3
import threading
from pathlib import Path

import pytest

from scripts import windows_acceptance as wa

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "STAR_WINDOWS_ACCEPTANCE.md"


# --- inventory / preservation ---------------------------------------------------

def make_profile(root: Path, rows=2, with_new_columns=False):
    (root / "models").mkdir(parents=True, exist_ok=True)
    (root / "models" / "weights.gguf").write_bytes(b"GGUF" * 1000)
    (root / "logs").mkdir(exist_ok=True)
    (root / "logs" / "star-brain.log").write_text("started", encoding="utf-8")
    (root / "settings.json").write_text(json.dumps({"provider": "local", "endpoint": "http://127.0.0.1:8080/v1",
                                                    "model": "q", "project": "STAR", "secret": "x"}), encoding="utf-8")
    db = root / "conversations.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT, "
                     "role TEXT, body TEXT, created TEXT, chat_id TEXT)")
        existing = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        for i in range(existing, rows):
            conn.execute("INSERT INTO messages(project,role,body,created,chat_id) VALUES ('STAR',?,?,'t','c1')",
                         ("user" if i % 2 == 0 else "assistant", f"message {i}"))
        if with_new_columns:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(messages)")}
            if "status" not in cols:
                conn.execute("ALTER TABLE messages ADD COLUMN status TEXT NOT NULL DEFAULT 'complete'")
                conn.execute("ALTER TABLE messages ADD COLUMN reply_to INTEGER")


def snap(label, data, install):
    return json.loads(json.dumps(wa.take_snapshot(label, data, install, 10**9)))


@pytest.fixture
def no_machine_probing(monkeypatch):
    monkeypatch.setattr(wa, "windows_facts", lambda: {"platform": "test", "installed": None, "gpu": None})


def make_install(root: Path, mtime: int):
    internal = root / "_internal" / "frontend" / "dist"
    internal.mkdir(parents=True, exist_ok=True)
    (root / "STAR.exe").write_bytes(b"MZ")
    (internal / "index.html").write_text("<html/>", encoding="utf-8")
    (root / "_internal" / "lib.dll").write_bytes(b"x")
    import os
    for path in (root / "_internal").rglob("*"):
        if path.is_file():
            os.utime(path, (mtime, mtime))


def verdicts(rows):
    return {(status, ident) for status, ident, _ in rows}


def test_preservation_passes_when_data_survives_and_migration_only_adds(tmp_path, no_machine_probing):
    data, app = tmp_path / "STAR", tmp_path / "app"
    make_profile(data, rows=4)
    make_install(app, 1_700_000_000)
    before = snap("before", data, app)
    make_profile(data, rows=4, with_new_columns=True)  # additive migration
    make_install(app, 1_800_000_000)                   # runtime replaced by a newer build
    (data / "logs" / "star-brain.log").unlink()        # volatile, never judged
    after = snap("after", data, app)
    rows = wa.compare_snapshots(before, after)
    assert not [r for r in rows if r[0] == "FAIL"], rows
    assert ("PASS", "preserve-files") in verdicts(rows)
    assert ("PASS", "preserve-db:conversations.sqlite3") in verdicts(rows)
    assert ("PASS", "runtime-replaced") in verdicts(rows)


def test_preservation_fails_on_lost_files_changed_models_and_shrunk_tables(tmp_path, no_machine_probing):
    data, app = tmp_path / "STAR", tmp_path / "app"
    make_profile(data, rows=4)
    make_install(app, 1_700_000_000)
    before = snap("before", data, app)
    (data / "settings.json").unlink()
    (data / "models" / "weights.gguf").write_bytes(b"CORRUPT")
    with sqlite3.connect(data / "conversations.sqlite3") as conn:
        conn.execute("DELETE FROM messages WHERE id > 1")
    rows = wa.compare_snapshots(before, snap("after", data, app))
    messages = " | ".join(m for s, _, m in rows if s == "FAIL")
    assert "missing after upgrade: settings.json" in messages
    assert "content changed: models/weights.gguf" in messages
    assert "messages: 4 rows became 1" in messages
    assert ("PASS", "preserve-files") not in verdicts(rows)


def test_missing_react_bundle_fails(tmp_path, no_machine_probing):
    data, app = tmp_path / "STAR", tmp_path / "app"
    make_profile(data)
    make_install(app, 1_700_000_000)
    before = snap("before", data, app)
    (app / "_internal" / "frontend" / "dist" / "index.html").unlink()
    assert ("FAIL", "react-bundle") in verdicts(wa.compare_snapshots(before, snap("after", data, app)))


def test_snapshot_never_stores_message_text_or_secrets(tmp_path, no_machine_probing):
    data, app = tmp_path / "STAR", tmp_path / "app"
    make_profile(data)
    make_install(app, 1_700_000_000)
    snapshot = wa.take_snapshot("x", data, app, 10**9)
    assert "message 0" not in json.dumps(snapshot) and "message 1" not in json.dumps(snapshot)
    assert set(snapshot["settings"]) == {"provider", "endpoint", "model", "project"}  # whitelisted keys only
    assert "secret" not in snapshot["settings"]


# --- release checksums ------------------------------------------------------------

def test_sha256sums_parsing_and_verify_release_cli(tmp_path):
    setup = tmp_path / "STAR-Setup-v9.9.9.exe"
    setup.write_bytes(b"MZ" + b"payload" * 100)
    digest = hashlib.sha256(setup.read_bytes()).hexdigest()
    sums = tmp_path / "SHA256SUMS.txt"
    sums.write_text(f"{digest}  STAR-Setup-v9.9.9.exe\n{'a' * 64} *STAR-Genesis-Windows-x64.zip\n", encoding="utf-8")
    assert wa.parse_sha256sums(sums.read_text()) == {"STAR-Setup-v9.9.9.exe": digest,
                                                     "STAR-Genesis-Windows-x64.zip": "a" * 64}
    evidence = tmp_path / "ev"
    assert wa.main(["--evidence", str(evidence), "verify-release", str(setup), "--sums", str(sums)]) == 0
    rows = [json.loads(line) for line in (evidence / "results.jsonl").read_text().splitlines()]
    assert {r["id"]: r["status"] for r in rows} == {"W03a": "INFO", "W03b": "PASS"}
    sums.write_text(f"{'0' * 64}  STAR-Setup-v9.9.9.exe\n", encoding="utf-8")
    assert wa.main(["--evidence", str(evidence), "verify-release", str(setup), "--sums", str(sums)]) == 1


# --- loopback-only networking ----------------------------------------------------

@pytest.mark.parametrize("bad", [
    "https://127.0.0.1:8080/v1", "http://10.0.0.5:8080/v1", "http://example.com:8080/v1",
    "http://127.0.0.1/v1", "http://user:pw@127.0.0.1:8080/v1", "http://127.0.0.1:8080/v1?x=1",
])
def test_brain_check_refuses_non_loopback_endpoints(bad):
    with pytest.raises(ValueError):
        wa.require_loopback(bad)


def test_loopback_endpoint_is_parsed():
    assert wa.require_loopback("http://localhost:8080/v1/") == ("localhost", 8080, "/v1")


class FakeLlama(http.server.BaseHTTPRequestHandler):
    """A tiny llama-server stand-in with the strict Qwen template rule."""
    mode = "ok"

    def log_message(self, *args):
        pass

    def _json(self, status, body):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/v1/models":
            return self._json(200, {"data": [{"id": "qwen-fake"}]})
        self._json(404, {})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        systems = [m for m in body["messages"] if m["role"] == "system"]
        if len(systems) > 1 or self.mode == "template-bug":
            return self._json(500, {"error": {"message": "System message must be at the beginning."}})
        if not body.get("stream"):
            return self._json(200, {"choices": [{"message": {"content": "1 2 3 4 5 6 7 8 9 10 11 12"}}]})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        pieces = ["1 2 3"] if self.mode == "one-chunk" else ["1 2", " 3 4", " 5 6", " 7 8"]
        for piece in pieces:
            self.wfile.write(b"data: " + json.dumps({"choices": [{"delta": {"content": piece}}]}).encode() + b"\n\n")
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")


@pytest.fixture
def llama():
    def start(mode):
        handler = type("H", (FakeLlama,), {"mode": mode})
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        started.append(server)
        return f"http://127.0.0.1:{server.server_port}/v1"
    started = []
    yield start
    for server in started:
        server.shutdown()
        server.server_close()


def by_id(rows):
    return {ident: status for status, ident, *_ in rows}


def test_brain_check_passes_against_a_healthy_streaming_server(llama):
    rows = wa.brain_check(llama("ok"), None, 10, negative_template=True)
    assert by_id(rows) == {"W12a": "PASS", "W12b": "PASS", "W13": "PASS", "W14": "INFO"}
    assert "True" in [r for r in rows if r[1] == "W14"][0][3]  # the second system message really is rejected


def test_brain_check_fails_when_the_answer_is_not_streamed(llama):
    assert by_id(wa.brain_check(llama("one-chunk"), None, 10))["W13"] == "FAIL"


def test_brain_check_fails_on_the_template_regression(llama):
    rows = by_id(wa.brain_check(llama("template-bug"), None, 10))
    assert rows["W12b"] == "FAIL"


def test_brain_check_reports_an_unreachable_server_as_a_failure():
    rows = wa.brain_check("http://127.0.0.1:9/v1", None, 2)
    assert rows[0][:2] == ("FAIL", "W12a") and "Start STAR Brain" in rows[0][3]


# --- logs and database ----------------------------------------------------------

def test_scan_logs_finds_the_known_regression(tmp_path):
    (tmp_path / "star-brain.log").write_text("ok\nerror: System message must be at the beginning\n", encoding="utf-8")
    (tmp_path / "other.log").write_text("fine", encoding="utf-8")
    assert wa.scan_logs(tmp_path) == {"star-brain.log": {"System message must be at the beginning": 1}}
    assert wa.scan_logs(tmp_path / "missing") == {}


def stored_db(path: Path):
    from star.desktop_core import Conversations
    chats = Conversations(path)
    try:
        chat = chats.active_chat("STAR")
        chats.add("STAR", "user", "answered 100%_done", chat_id=chat)
        chats.add("STAR", "assistant", "the maintenance code word is PELICAN-4821", chat_id=chat)
        second = chats.add("STAR", "user", "will fail", chat_id=chat)
        chats.add_terminal("STAR", chat, second, "failed", "Cannot reach STAR Brain.")
        chats.add("STAR", "user", "never answered", chat_id=chat)
    finally:
        chats.close()


def test_db_check_confirms_migration_and_counts_unanswered_questions(tmp_path):
    db = tmp_path / "conversations.sqlite3"
    stored_db(db)
    rows = {ident: (status, detail) for status, ident, _, detail in wa.db_check(db)}
    assert rows["W41a"][0] == "PASS"
    assert json.loads(rows["W41b"][1]) == {"complete": 4, "failed": 1}
    assert rows["W41c"][1].startswith("1 ")  # only the last question has no answer or failure record


def test_db_check_fails_on_a_database_without_the_new_columns(tmp_path):
    db = tmp_path / "conversations.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, project TEXT, role TEXT, body TEXT, created TEXT, chat_id TEXT)")
    assert wa.db_check(db)[0][0] == "FAIL"
    assert wa.db_check(tmp_path / "absent.sqlite3")[0][0] == "FAIL"


def test_marker_and_answer_checks_print_counts_not_text(tmp_path):
    db = tmp_path / "conversations.sqlite3"
    stored_db(db)
    assert wa.count_marker(db, "100%_done") == {"user": 1}  # LIKE wildcards are escaped, not interpreted
    assert wa.count_marker(db, "no such marker") == {}
    assert wa.latest_answer_contains(db, "pelican-4821")[0] is True
    assert wa.latest_answer_contains(db, "walrus")[0] is False


def test_long_prompt_hides_the_secret_in_the_middle(tmp_path):
    target = tmp_path / "long.txt"
    wa.make_long_prompt(target, "PELICAN-4821", 100)
    lines = target.read_text(encoding="utf-8").splitlines()
    assert sum("PELICAN-4821" in line for line in lines) == 1
    assert 40 < [i for i, line in enumerate(lines) if "PELICAN-4821" in line][0] < 60
    assert lines[-1].startswith("Question:")


# --- report and docs stay in sync ------------------------------------------------

def test_report_lists_results_and_every_manual_check_as_not_run(tmp_path):
    wa.record(tmp_path, "W12b", "Single-system chat completion", "PASS", "HTTP 200")
    wa.record(tmp_path, "W13", "Real token streaming", "FAIL", "1 delta | pipe")
    report = wa.build_report(tmp_path)
    assert "| W12b | PASS |" in report and "| W13 | FAIL |" in report and "1 delta / pipe" in report
    assert "Automated failures: W13" in report
    for ident in wa.MANUAL_CHECKS:
        assert f"| {ident} |" in report and "NOT RUN" in report
    assert "Do not close the issue" in report


def test_doc_and_script_describe_the_same_checks():
    doc = DOC.read_text(encoding="utf-8")
    for ident in wa.MANUAL_CHECKS:
        assert re.search(rf"^###? {ident} ", doc, re.M), f"{ident} has no section in the acceptance doc"
    used = set(re.findall(r"windows_acceptance\.cmd (?:--evidence \S+ )?([a-z][a-z-]+)", doc))
    commands = {"snapshot", "compare", "verify-release", "doctor", "brain-check", "scan-logs", "db-check",
                "count-marker", "check-answer", "make-long-prompt", "window-size", "report"}
    assert used <= commands, used - commands
    assert commands <= used | {"report"}, commands - used
    assert "issue #15" in doc.lower() and "stays **open**" in doc
    assert (ROOT / "scripts" / "windows_acceptance.cmd").is_file()


def test_script_never_writes_under_the_app_data_folder():
    source = (ROOT / "scripts" / "windows_acceptance.py").read_text(encoding="utf-8")
    assert "mode=ro" in source
    for forbidden in ("shutil.rmtree", "os.remove(", ".unlink(", "os.rename(", "shutil.move("):
        assert forbidden not in source


def test_batch_wrapper_keeps_crlf_and_reports_the_real_exit_code():
    raw = (ROOT / "scripts" / "windows_acceptance.cmd").read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b""), "cmd.exe needs CRLF; labels break on bare LF"
    assert "*.cmd -text" in (ROOT / ".gitattributes").read_text(encoding="utf-8")  # git must not rewrite them
    text = raw.decode("ascii")
    assert "exit /b %errorlevel%" in text
    code_lines = [line for line in text.splitlines() if line and not line.lower().startswith(("echo", "rem"))]
    assert not [line for line in code_lines if "(" in line or ")" in line], "a parenthesised block would freeze %errorlevel%"
    assert "-c \"import sys\"" in text  # the Microsoft Store python stub must be rejected, not run
