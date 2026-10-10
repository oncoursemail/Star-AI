#!/usr/bin/env python3
"""Evidence helper for STAR's real Windows 11 acceptance run (GitHub issue #15).

This script automates only what a computer can honestly measure on the test PC:
file inventories before/after an upgrade, release checksums, the local model
server's real streaming behaviour, packaged `--doctor` output, log scans and
read-only database checks. Everything that needs a human (does it look right,
does Roblox Studio edit correctly) stays in docs/STAR_WINDOWS_ACCEPTANCE.md.

Safety: standard library only; reads `%APPDATA%\\STAR` but never writes or
deletes there; talks only to loopback addresses (plus api.github.com for
`verify-release --tag`); records counts, sizes and hashes, never chat
text or credentials. Evidence goes to --evidence (default
%USERPROFILE%\\STAR-acceptance). It does not close or comment on any issue.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import platform
import re
import sqlite3
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

REPO = "oncoursemail/Star-AI"
INNO_APP_ID = "{E2B5518B-30A1-409D-AF44-6F773BF05C97}"
KNOWN_BAD_LOG_STRINGS = (
    "System message must be at the beginning",  # Qwen/llama.cpp strict template regression
    "Traceback (most recent call last)",
    "HTTP 500",
)
# Directories that legitimately change while STAR runs; never judged for preservation.
VOLATILE_PARTS = {"logs", "runs", "__pycache__", "tmp", "cache"}

# Manual checks live in docs/STAR_WINDOWS_ACCEPTANCE.md; the report lists them as NOT RUN.
MANUAL_CHECKS = {
    "W04": "Setup installed over the previous version",
    "W05": "STAR launched at the new version with the old chats visible",
    "W09": "React interface (not legacy), answers appear once",
    "W11": "STAR Brain installed and started from the app",
    "W12": "Test actual AI response shows a real answer",
    "W15": "Missing / corrupted model file produces an actionable error",
    "W16": "Offline chat works after install",
    "W17": "Long-context recall",
    "W18": "Vision reference",
    "W19": "Audio transcription",
    "W20": "No hosted API key is needed or stored",
    "W21": "Layout at 1050x680 and 1440x900",
    "W22": "Layout at 100%, 125%, 150% Windows scaling",
    "W23": "Keyboard: Ctrl+K, Esc, Enter vs Shift+Enter, focus",
    "W24": "Markdown code copy, send, retry, reduced motion, contrast",
    "W30": "Roblox Studio read-only discovery",
    "W31": "Roblox Studio scoped edit, undo and screenshot",
    "W40": "In-app update check, install and restart",
    "W41": "Failure and Stop show actionable errors and survive a restart",
}


# --------------------------------------------------------------------- paths
def data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / "STAR"


def install_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "Programs" / "STAR"


def evidence_dir(arg: str | None) -> Path:
    path = Path(arg) if arg else Path.home() / "STAR-acceptance"
    path.mkdir(parents=True, exist_ok=True)
    return path


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------- results
def record(evidence: Path, check_id: str, name: str, status: str, detail: str = "") -> dict:
    """Append one machine-readable result and echo it. status: PASS | FAIL | INFO."""
    assert status in {"PASS", "FAIL", "INFO"}
    row = {"id": check_id, "name": name, "status": status, "detail": detail, "at": now()}
    with (evidence / "results.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    print(f"[{status}] {check_id} {name}" + (f" - {detail}" if detail else ""))
    return row


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ----------------------------------------------------------------- inventory
def inventory(root: Path, hash_limit: int = 4_000_000_000) -> dict[str, dict]:
    """Relative path -> size, mtime and SHA-256 (None above hash_limit). Contents are never stored."""
    root = Path(root)
    files: dict[str, dict] = {}
    if not root.is_dir():
        return files
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        stat = path.stat()
        files[path.relative_to(root).as_posix()] = {
            "size": stat.st_size,
            "mtime": int(stat.st_mtime),
            "sha256": sha256_file(path) if stat.st_size <= hash_limit else None,
        }
    return files


def db_summary(path: Path) -> dict | None:
    """Row counts and column names per table, opened read-only. No row contents."""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=3)
    except sqlite3.Error as exc:  # pragma: no cover - locked / corrupt
        return {"error": f"{type(exc).__name__}: {exc}"}
    try:
        tables = {}
        for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{name}")')]
            count = connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            tables[name] = {"rows": count, "columns": columns}
        summary: dict = {"tables": tables}
        messages = tables.get("messages")
        if messages:
            summary["messages_by_role"] = dict(connection.execute("SELECT role, COUNT(*) FROM messages GROUP BY role"))
            if "status" in messages["columns"]:
                summary["messages_by_status"] = dict(connection.execute("SELECT status, COUNT(*) FROM messages GROUP BY status"))
        return summary
    except sqlite3.Error as exc:  # pragma: no cover
        return {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        connection.close()


def windows_facts() -> dict:
    facts: dict = {"platform": platform.platform(), "python": sys.version.split()[0], "machine": platform.machine()}
    if os.name == "nt":
        try:
            import winreg
            for hive, name in ((winreg.HKEY_CURRENT_USER, "HKCU"), (winreg.HKEY_LOCAL_MACHINE, "HKLM")):
                try:
                    key = winreg.OpenKey(hive, rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{INNO_APP_ID}_is1")
                except OSError:
                    continue
                with key:
                    facts["installed"] = {"hive": name, "version": winreg.QueryValueEx(key, "DisplayVersion")[0]}
                break
        except Exception as exc:  # pragma: no cover
            facts["installed_error"] = str(exc)
    for label, command in (
        ("gpu", ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"]),
        ("credentials_named_star", ["cmdkey", "/list"]),
    ):
        try:
            out = subprocess.run(command, capture_output=True, text=True, timeout=20).stdout
        except (OSError, subprocess.SubprocessError):
            facts[label] = None
            continue
        if label == "credentials_named_star":  # names only, and only ours
            out = "\n".join(line.strip() for line in out.splitlines() if "star" in line.lower() and "target" in line.lower())
        facts[label] = out.strip() or None
    return facts


def take_snapshot(label: str, data: Path, install: Path, hash_limit: int) -> dict:
    app = inventory(install, hash_limit=0)  # sizes only; the app tree is large and replaced by design
    internal = [v["mtime"] for k, v in app.items() if k.startswith("_internal/")]
    settings = {}
    try:
        raw = json.loads((data / "settings.json").read_text(encoding="utf-8"))
        settings = {k: raw.get(k) for k in ("provider", "endpoint", "model", "project") if k in raw}
    except (OSError, ValueError):
        pass
    return {
        "label": label, "taken_at": now(), "data_dir": str(data), "install_dir": str(install),
        "facts": windows_facts(),
        "install": {
            "present": (install / "STAR.exe").is_file(),
            "files": len(app),
            "internal_files": len(internal),
            "internal_oldest_mtime": min(internal) if internal else None,
            "internal_newest_mtime": max(internal) if internal else None,
            "react_bundle": (install / "_internal" / "frontend" / "dist" / "index.html").is_file(),
        },
        "settings": settings,
        "data_files": inventory(data, hash_limit),
        "databases": {name: db_summary(data / name) for name in
                      ("conversations.sqlite3", "checkpoints.sqlite3", "analytics.sqlite3")},
    }


def _volatile(rel: str) -> bool:
    return bool(VOLATILE_PARTS & set(rel.split("/")[:-1]))


def compare_snapshots(before: dict, after: dict) -> list[tuple[str, str, str]]:
    """(status, id, message) rows. Personal data must survive an upgrade or update."""
    rows: list[tuple[str, str, str]] = []
    old, new = before["data_files"], after["data_files"]
    if not old:
        rows.append(("INFO", "preserve-files", "The before snapshot has no %APPDATA%\\STAR files; nothing to compare"))
    for rel, meta in sorted(old.items()):
        if _volatile(rel):
            continue
        if rel not in new:
            rows.append(("FAIL", "preserve-files", f"missing after upgrade: {rel}"))
        elif rel.endswith((".gguf", ".exe", ".dll", ".png", ".webp", ".jpg", ".mp4", ".wav")) or rel.startswith(("models/", "engines/")):
            if meta["sha256"] and new[rel]["sha256"] != meta["sha256"]:
                rows.append(("FAIL", "preserve-files", f"content changed: {rel}"))
    if old and not any(r[0] == "FAIL" and r[1] == "preserve-files" for r in rows):
        rows.append(("PASS", "preserve-files", f"all {len([r for r in old if not _volatile(r)])} non-volatile files still present; binaries, models and media byte-identical"))
    for name, summary in before["databases"].items():
        later = after["databases"].get(name)
        if not summary or "tables" not in summary:
            continue
        if not later or "tables" not in later:
            rows.append(("FAIL", f"preserve-db:{name}", "database missing or unreadable after upgrade"))
            continue
        for table, meta in summary["tables"].items():
            current = later["tables"].get(table)
            if current is None:
                rows.append(("FAIL", f"preserve-db:{name}", f"table {table} disappeared"))
            elif current["rows"] < meta["rows"]:
                rows.append(("FAIL", f"preserve-db:{name}", f"{table}: {meta['rows']} rows became {current['rows']}"))
            elif not set(meta["columns"]) <= set(current["columns"]):
                rows.append(("FAIL", f"preserve-db:{name}", f"{table}: columns were removed"))
        if not any(r[1] == f"preserve-db:{name}" for r in rows):
            rows.append(("PASS", f"preserve-db:{name}", "no table lost rows or columns"))
    if before["install"]["present"] and after["install"]["present"]:
        newer = (after["install"]["internal_oldest_mtime"] or 0) > (before["install"]["internal_newest_mtime"] or 0)
        rows.append(("PASS" if newer else "INFO", "runtime-replaced",
                     "every file under _internal is newer than the previous runtime" if newer
                     else "some _internal files predate the previous runtime (re-check after installing a different version)"))
    if not after["install"]["react_bundle"]:
        rows.append(("FAIL", "react-bundle", "_internal\\frontend\\dist\\index.html is missing after install"))
    return rows


# -------------------------------------------------------------------- release
def parse_sha256sums(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        match = re.fullmatch(r"\s*([0-9a-fA-F]{64})\s+\*?(\S.*?)\s*", line)
        if match:
            result[match.group(2)] = match.group(1).lower()
    return result


def fetch_release_digest(tag: str, asset: str) -> str | None:
    """Ask GitHub (anonymously) for the digest it records for a release asset."""
    connection = http.client.HTTPSConnection("api.github.com", timeout=20)
    try:
        connection.request("GET", f"/repos/{REPO}/releases/tags/{urllib.parse.quote(tag)}",
                           headers={"Accept": "application/vnd.github+json", "User-Agent": "star-windows-acceptance"})
        response = connection.getresponse()
        if response.status != 200:
            return None
        for item in json.loads(response.read()).get("assets", []):
            if item.get("name") == asset:
                return str(item.get("digest", "")).removeprefix("sha256:").lower() or None
    finally:
        connection.close()
    return None


# ------------------------------------------------------------------ local model
def require_loopback(endpoint: str) -> tuple[str, int, str]:
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.port:
        raise ValueError("Only http://127.0.0.1:PORT/v1 or http://localhost:PORT/v1 is allowed")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Endpoint must not contain credentials, a query or a fragment")
    return parsed.hostname, parsed.port, parsed.path.rstrip("/")


def _post(host: str, port: int, path: str, payload: dict, timeout: float):
    connection = http.client.HTTPConnection(host, port, timeout=timeout)
    connection.request("POST", path, json.dumps(payload), {"Content-Type": "application/json", "Authorization": "Bearer local-only"})
    return connection, connection.getresponse()


def brain_check(endpoint: str, model: str | None, timeout: float, negative_template: bool = False) -> list[tuple[str, str, str, str]]:
    """Real requests against the running local model server (STAR's own request shape)."""
    host, port, base = require_loopback(endpoint)
    rows: list[tuple[str, str, str, str]] = []
    try:
        connection = http.client.HTTPConnection(host, port, timeout=timeout)
        connection.request("GET", base + "/models", headers={"Authorization": "Bearer local-only"})
        response = connection.getresponse()
        body = response.read()
        connection.close()
    except OSError as exc:
        return [("FAIL", "W12a", "Model server reachable", f"{type(exc).__name__}: {exc}. Start STAR Brain first.")]
    if response.status != 200:
        return [("FAIL", "W12a", "Model server reachable", f"GET /models returned HTTP {response.status}")]
    ids = [str(item.get("id")) for item in json.loads(body).get("data", []) if isinstance(item, dict)]
    rows.append(("PASS" if ids else "FAIL", "W12a", "Model server lists a model", ", ".join(ids) or "none"))
    chosen = model or (ids[0] if ids else "")
    # STAR sends exactly ONE system message followed by user content (see star/agent.py).
    messages = [{"role": "system", "content": "You are a concise assistant."},
                {"role": "user", "content": "Count from 1 to 12 with single spaces between the numbers. No other text."}]
    started = time.monotonic()
    try:
        connection, response = _post(host, port, base + "/chat/completions",
                                     {"model": chosen, "messages": messages, "max_tokens": 80, "temperature": 0}, timeout)
        body = response.read().decode("utf-8", "replace")
        connection.close()
    except OSError as exc:
        return rows + [("FAIL", "W12b", "Single-system chat completion", f"{type(exc).__name__}: {exc}")]
    elapsed = time.monotonic() - started
    template_bug = "System message must be at the beginning" in body
    if response.status == 200 and not template_bug:
        content = json.loads(body)["choices"][0]["message"].get("content") or ""
        rows.append(("PASS" if content.strip() else "FAIL", "W12b", "Single-system chat completion returns text",
                     f"HTTP 200, {len(content)} chars, {elapsed:.1f}s"))
    else:
        rows.append(("FAIL", "W12b", "Single-system chat completion", f"HTTP {response.status}; template error present: {template_bug}"))
    # Streaming: count separate content deltas and time the first one.
    started = time.monotonic()
    first = None
    deltas = 0
    try:
        connection, response = _post(host, port, base + "/chat/completions",
                                     {"model": chosen, "messages": messages, "max_tokens": 80, "temperature": 0, "stream": True}, timeout)
        if response.status != 200:
            rows.append(("FAIL", "W13", "Real token streaming", f"HTTP {response.status}"))
        else:
            for raw in response:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:") or line == "data: [DONE]":
                    continue
                choice = (json.loads(line[5:]).get("choices") or [{}])[0]
                if (choice.get("delta") or {}).get("content"):
                    deltas += 1
                    first = first if first is not None else time.monotonic() - started
            total = time.monotonic() - started
            ok = deltas >= 3
            rows.append(("PASS" if ok else "FAIL", "W13", "Real token streaming (several separate deltas)",
                         f"{deltas} content deltas, first after {first:.2f}s, finished in {total:.2f}s"
                         if first is not None else "no content deltas arrived"))
        connection.close()
    except (OSError, ValueError) as exc:
        rows.append(("FAIL", "W13", "Real token streaming", f"{type(exc).__name__}: {exc}"))
    if negative_template:
        bad = messages + [{"role": "system", "content": "A second system message."}]
        try:
            connection, response = _post(host, port, base + "/chat/completions", {"model": chosen, "messages": bad, "max_tokens": 8}, timeout)
            text = response.read().decode("utf-8", "replace")
            connection.close()
            rows.append(("INFO", "W14", "Second system message is rejected by this model template (why STAR sends only one)",
                         f"HTTP {response.status}; mentions template rule: {'System message must be at the beginning' in text}"))
        except OSError as exc:
            rows.append(("INFO", "W14", "Negative template probe", f"{type(exc).__name__}: {exc}"))
    return rows


def scan_logs(logs: Path, patterns=KNOWN_BAD_LOG_STRINGS) -> dict[str, dict[str, int]]:
    found: dict[str, dict[str, int]] = {}
    if not Path(logs).is_dir():
        return found
    for path in sorted(Path(logs).glob("*.log")):
        text = path.read_text(encoding="utf-8", errors="replace")
        counts = {p: text.count(p) for p in patterns if p in text}
        if counts:
            found[path.name] = counts
    return found


# -------------------------------------------------------------------- database
def db_check(db: Path) -> list[tuple[str, str, str, str]]:
    summary = db_summary(db)
    if summary is None:
        return [("FAIL", "W41a", "Conversation database exists", f"{db} not found")]
    if "tables" not in summary or "messages" not in summary["tables"]:
        return [("FAIL", "W41a", "Conversation database readable", str(summary))]
    columns = summary["tables"]["messages"]["columns"]
    rows = [("PASS" if {"status", "reply_to", "chat_id"} <= set(columns) else "FAIL", "W41a",
             "messages table has chat_id, status and reply_to (additive migration ran)", ", ".join(columns))]
    by_status = summary.get("messages_by_status", {})
    rows.append(("INFO", "W41b", "Messages by status", json.dumps(by_status)))
    connection = sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True, timeout=3)
    try:
        orphans = connection.execute(
            "SELECT COUNT(*) FROM messages u WHERE u.role='user' AND NOT EXISTS ("
            "SELECT 1 FROM messages a WHERE a.project=u.project AND a.chat_id=u.chat_id AND a.id>u.id "
            "AND a.id<COALESCE((SELECT MIN(n.id) FROM messages n WHERE n.project=u.project AND n.chat_id=u.chat_id "
            "AND n.id>u.id AND n.role='user'),9223372036854775807) AND a.role IN ('assistant','event'))").fetchone()[0]
    finally:
        connection.close()
    rows.append(("INFO", "W41c", "User messages with no assistant or failure record after them",
                 f"{orphans} (turns from before the fix, or a turn running right now, are expected here)"))
    return rows


def count_marker(db: Path, marker: str) -> dict[str, int]:
    """How many stored rows contain a test marker, by role. Prints counts only."""
    connection = sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True, timeout=3)
    try:
        return dict(connection.execute("SELECT role, COUNT(*) FROM messages WHERE body LIKE ? ESCAPE '\\' GROUP BY role",
                                       ("%" + marker.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%",)))
    finally:
        connection.close()


def latest_answer_contains(db: Path, needle: str) -> tuple[bool, int]:
    connection = sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True, timeout=3)
    try:
        row = connection.execute("SELECT body FROM messages WHERE role='assistant' ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        connection.close()
    body = row[0] if row else ""
    return needle.lower() in body.lower(), len(body)


def make_long_prompt(path: Path, secret: str, filler_lines: int) -> str:
    """A long note with one fact buried in the middle and a question at the end."""
    lines = [f"Note {i}: the weather log entry {i} records ordinary sky conditions and nothing else." for i in range(filler_lines)]
    lines.insert(filler_lines // 2, f"Important: the maintenance code word is {secret}.")
    lines.append("Question: what is the maintenance code word? Answer with the word only.")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    return secret


# ---------------------------------------------------------------------- windows
def set_client_size(title_prefix: str, width: int, height: int) -> str:
    """Resize STAR's window so its CLIENT area is exactly width x height (Windows only)."""
    if os.name != "nt":
        raise OSError("window-size runs on Windows only")
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    try:
        user32.SetProcessDPIAware()
    except Exception:  # pragma: no cover
        pass
    found: list[tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            buffer = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buffer, 256)
            if buffer.value.startswith(title_prefix):
                found.append((hwnd, buffer.value))
        return True

    user32.EnumWindows(visit, 0)
    if not found:
        raise LookupError(f"No visible window whose title starts with {title_prefix!r}. Is STAR running?")
    hwnd, title = found[0]
    outer, client = wintypes.RECT(), wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(outer))
    user32.GetClientRect(hwnd, ctypes.byref(client))
    extra_w = (outer.right - outer.left) - (client.right - client.left)
    extra_h = (outer.bottom - outer.top) - (client.bottom - client.top)
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE: leave maximized state
    user32.MoveWindow(hwnd, outer.left, outer.top, width + extra_w, height + extra_h, True)
    user32.GetClientRect(hwnd, ctypes.byref(client))
    return f"{title}: client area is now {client.right - client.left}x{client.bottom - client.top} (requested {width}x{height})"


# ----------------------------------------------------------------------- report
def build_report(evidence: Path) -> str:
    results: dict[str, dict] = {}
    path = evidence / "results.jsonl"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                results[row["id"]] = row  # the latest run of a check wins
    out = ["# STAR Windows acceptance evidence", "", f"Generated {now()} on {platform.platform()}", "",
           "Automated checks measure files, hashes, HTTP behaviour and database counts only. Attach this file, the",
           "JSON snapshots and your screenshots to issue #15. Do not close the issue from this report alone.", "",
           "## Automated results", "", "| ID | Result | Check | Detail |", "|---|---|---|---|"]
    for key in sorted(results):
        r = results[key]
        out.append(f"| {key} | {r['status']} | {r['name']} | {str(r['detail']).replace('|', '/')} |")
    if not results:
        out.append("| - | - | nothing was run yet | - |")
    out += ["", "## Manual checks (a person must observe these)", "", "| ID | Check | Result | Notes / evidence file |", "|---|---|---|---|"]
    for key, title in MANUAL_CHECKS.items():
        out.append(f"| {key} | {title} | NOT RUN | |")
    failed = [k for k, r in results.items() if r["status"] == "FAIL"]
    out += ["", f"Automated failures: {', '.join(failed) if failed else 'none'}", ""]
    return "\n".join(out)


# --------------------------------------------------------------------------- CLI
def _print_rows(evidence: Path, rows) -> int:
    """Record (status, id, name, detail) rows; the exit code is 1 when any row failed."""
    failed = 0
    for status, check_id, name, detail in rows:
        record(evidence, check_id, name, status, detail)
        failed += status == "FAIL"
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--evidence", help="evidence folder (default %%USERPROFILE%%\\STAR-acceptance)")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("snapshot", help="record file/database facts about the install and %%APPDATA%%\\STAR")
    s.add_argument("label", help="for example before-upgrade or after-upgrade")
    s.add_argument("--no-hash-above-mb", type=int, default=4000, help="skip hashing files larger than this (default 4000)")
    c = sub.add_parser("compare", help="prove personal data survived: compare two snapshots")
    c.add_argument("before"); c.add_argument("after")
    v = sub.add_parser("verify-release", help="check a downloaded installer's SHA-256")
    v.add_argument("setup"); v.add_argument("--sums", help="path to SHA256SUMS.txt from the same release")
    v.add_argument("--tag", help="release tag such as v0.8.1, to compare with GitHub's recorded digest")
    d = sub.add_parser("doctor", help="run the packaged STAR.exe --doctor, --ui-doctor and --build-doctor")
    d.add_argument("--app", default=str(install_dir() / "STAR.exe"))
    d.add_argument("--expect-sha", default="", help="exact source commit the build must contain (STAR_EXPECTED_HEAD_SHA)")
    b = sub.add_parser("brain-check", help="real requests to the running local model server")
    b.add_argument("--endpoint", default="http://127.0.0.1:8080/v1"); b.add_argument("--model")
    b.add_argument("--timeout", type=float, default=180.0)
    b.add_argument("--negative-template", action="store_true", help="also show that a second system message is rejected")
    sub.add_parser("scan-logs", help="look for known failure strings in %%APPDATA%%\\STAR\\logs")
    sub.add_parser("db-check", help="read-only: migration columns and unanswered user messages")
    m = sub.add_parser("count-marker", help="count stored rows containing a test marker (no text printed)")
    m.add_argument("marker"); m.add_argument("--expect-user", type=int, default=1)
    a = sub.add_parser("check-answer", help="does the newest stored assistant answer contain a word (no text printed)")
    a.add_argument("needle")
    lp = sub.add_parser("make-long-prompt", help="write a long note with a hidden code word to paste into STAR")
    lp.add_argument("--lines", type=int, default=400); lp.add_argument("--secret", default="PELICAN-4821")
    w = sub.add_parser("window-size", help="set STAR's client area, for example 1050 680")
    w.add_argument("width", type=int); w.add_argument("height", type=int)
    sub.add_parser("report", help="write ACCEPTANCE_REPORT.md from everything recorded so far")

    args = parser.parse_args(argv)
    evidence = evidence_dir(args.evidence)
    data = data_dir()

    if args.command == "snapshot":
        snap = take_snapshot(args.label, data, install_dir(), args.no_hash_above_mb * 1_000_000)
        target = evidence / f"snapshot-{args.label}.json"
        target.write_text(json.dumps(snap, indent=2), encoding="utf-8")
        print(f"Wrote {target}")
        return _print_rows(evidence, [("INFO", f"snapshot:{args.label}", "Snapshot written",
                                       f"{len(snap['data_files'])} data files; installed={snap['facts'].get('installed')}; "
                                       f"gpu={snap['facts'].get('gpu')}")])
    if args.command == "compare":
        before = json.loads(Path(args.before).read_text(encoding="utf-8"))
        after = json.loads(Path(args.after).read_text(encoding="utf-8"))
        return _print_rows(evidence, [(s, i, "Upgrade keeps personal data and replaces the runtime", m)
                                      for s, i, m in compare_snapshots(before, after)])
    if args.command == "verify-release":
        digest = sha256_file(Path(args.setup)).lower()
        name = Path(args.setup).name
        rows = [("INFO", "W03a", "SHA-256 of the file you downloaded", digest)]
        if args.sums:
            expected = parse_sha256sums(Path(args.sums).read_text(encoding="utf-8")).get(name)
            rows.append(("PASS" if expected == digest else "FAIL", "W03b", "Matches SHA256SUMS.txt",
                         f"expected {expected}" if expected != digest else name))
        if args.tag:
            published = fetch_release_digest(args.tag, name)
            rows.append(("PASS" if published == digest else "FAIL", "W03c", "Matches the digest GitHub records for the release asset",
                         f"GitHub says {published}" if published != digest else args.tag))
        return _print_rows(evidence, rows)
    if args.command == "doctor":
        app = Path(args.app)
        if not app.is_file():
            return _print_rows(evidence, [("FAIL", "W06", "STAR.exe found", str(app))])
        rows = []
        for flag, check_id in (("--doctor", "W06a"), ("--ui-doctor", "W06b"), ("--build-doctor", "W06c")):
            env = dict(os.environ, **({"STAR_EXPECTED_HEAD_SHA": args.expect_sha} if args.expect_sha and flag == "--build-doctor" else {}))
            try:
                done = subprocess.run([str(app), flag], capture_output=True, text=True, timeout=180, env=env)
                text = (done.stdout + done.stderr).strip().replace("\n", " | ")[:300]
                rows.append(("PASS" if done.returncode == 0 else "FAIL", check_id, f"STAR.exe {flag}", f"exit {done.returncode}: {text}"))
            except (OSError, subprocess.SubprocessError) as exc:
                rows.append(("FAIL", check_id, f"STAR.exe {flag}", f"{type(exc).__name__}: {exc}"))
        return _print_rows(evidence, rows)
    if args.command == "brain-check":
        return _print_rows(evidence, brain_check(args.endpoint, args.model, args.timeout, args.negative_template))
    if args.command == "scan-logs":
        found = scan_logs(data / "logs")
        return _print_rows(evidence, [("FAIL" if found else "PASS", "W12c", "Logs contain no known failure strings",
                                       json.dumps(found) if found else str(data / "logs"))])
    if args.command == "db-check":
        return _print_rows(evidence, db_check(data / "conversations.sqlite3"))
    if args.command == "count-marker":
        counts = count_marker(data / "conversations.sqlite3", args.marker)
        ok = counts.get("user", 0) == args.expect_user
        return _print_rows(evidence, [("PASS" if ok else "FAIL", "W10", "Prompt stored exactly once (no duplicated current prompt)",
                                       json.dumps(counts) + f"; expected user rows = {args.expect_user}")])
    if args.command == "check-answer":
        hit, size = latest_answer_contains(data / "conversations.sqlite3", args.needle)
        return _print_rows(evidence, [("PASS" if hit else "FAIL", "W17a", "Newest assistant answer contains the expected word",
                                       f"answer length {size} chars")])
    if args.command == "make-long-prompt":
        target = evidence / "long-prompt.txt"
        make_long_prompt(target, args.secret, args.lines)
        print(f"Wrote {target} ({target.stat().st_size} bytes). Paste it into STAR, send, then run:\n"
              f"  check-answer {args.secret}")
        return 0
    if args.command == "window-size":
        try:
            print(set_client_size("STAR Intelligence", args.width, args.height))
            return 0
        except (OSError, LookupError) as exc:
            print(f"[FAIL] {exc}")
            return 1
    if args.command == "report":
        target = evidence / "ACCEPTANCE_REPORT.md"
        target.write_text(build_report(evidence), encoding="utf-8")
        print(f"Wrote {target}")
        return 0
    return 2  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
