#!/usr/bin/env python3
"""Smoke-test a packaged STAR.exe on a disposable copy of a Windows profile.

Uses only the standard library. The server key is supplied only to the child
process, is never printed, and must not appear in the rendered page.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import struct
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlsplit


class CDP:
    """Small synchronous DevTools WebSocket client; no third-party dependencies."""

    def __init__(self, ws_url: str):
        url = urlsplit(ws_url)
        if url.scheme != "ws" or url.hostname != "127.0.0.1" or not url.port or url.username or url.password:
            raise ValueError("DevTools must be a loopback ws://127.0.0.1 URL")
        self.sock = socket.create_connection(("127.0.0.1", url.port), timeout=30)
        self.sock.settimeout(30)
        self.buf = b""
        self.next_id = 0
        nonce = base64.b64encode(os.urandom(16)).decode("ascii")
        target = url.path or "/"
        if url.query:
            target += "?" + url.query
        request = (
            f"GET {target} HTTP/1.1\r\nHost: 127.0.0.1:{url.port}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {nonce}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        try:
            self.sock.sendall(request.encode("ascii"))
            head = b""
            while b"\r\n\r\n" not in head:
                chunk = self.sock.recv(4096)
                if not chunk:
                    raise RuntimeError("debugging socket closed during handshake")
                head += chunk
                if len(head) > 65536:
                    raise RuntimeError("debugging socket handshake too large")
            headers, self.buf = head.split(b"\r\n\r\n", 1)
            lines = headers.split(b"\r\n")
            if b" 101 " not in lines[0]:
                raise RuntimeError("debugging socket refused upgrade")
            fields = {}
            for line in lines[1:]:
                if b":" in line:
                    name, value = line.split(b":", 1)
                    fields[name.strip().lower()] = value.strip()
            expected = base64.b64encode(hashlib.sha1(
                (nonce + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
            ).digest())
            if fields.get(b"sec-websocket-accept") != expected:
                raise RuntimeError("debugging socket handshake mismatch")
            if fields.get(b"upgrade", b"").lower() != b"websocket":
                raise RuntimeError("debugging socket upgrade mismatch")
        except BaseException:
            self.sock.close()
            raise

    def close(self) -> None:
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def _read(self, length: int) -> bytes:
        while len(self.buf) < length:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise RuntimeError("debugging socket closed")
            self.buf += chunk
        result, self.buf = self.buf[:length], self.buf[length:]
        return result

    def _send(self, payload: bytes, opcode: int = 1) -> None:
        size = len(payload)
        if size < 126:
            length = bytes((0x80 | size,))
        elif size < 65536:
            length = bytes((0x80 | 126,)) + struct.pack(">H", size)
        else:
            length = bytes((0x80 | 127,)) + struct.pack(">Q", size)
        mask = os.urandom(4)
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        self.sock.sendall(bytes((0x80 | opcode,)) + length + mask + masked)

    def _recv(self) -> str:
        parts = []
        continuing = False
        while True:
            first, second = self._read(2)
            opcode = first & 15
            length = second & 127
            if second & 128:
                raise RuntimeError("server sent masked frame")
            if length == 126:
                length = struct.unpack(">H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read(8))[0]
            payload = self._read(length)
            if opcode == 9:
                self._send(payload, 10)
                continue
            if opcode == 8:
                raise RuntimeError("debugging socket closed by app")
            if opcode == 10:
                continue
            if opcode in (1, 2):
                if continuing:
                    raise RuntimeError("unexpected new data frame")
                continuing = True
            elif opcode != 0 or not continuing:
                raise RuntimeError("unexpected WebSocket frame")
            parts.append(payload)
            if first & 0x80:
                return b"".join(parts).decode("utf-8", "replace")

    def call(self, method: str, timeout: float = 60.0, **params):
        self.next_id += 1
        message_id = self.next_id
        self._send(json.dumps({"id": message_id, "method": method, "params": params}).encode("utf-8"))
        self.sock.settimeout(timeout)
        while True:
            message = json.loads(self._recv())
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})

    def js(self, expression: str, timeout: float = 60.0):
        response = self.call("Runtime.evaluate", timeout=timeout, expression=expression,
                             returnByValue=True, awaitPromise=True)
        if response.get("exceptionDetails"):
            raise RuntimeError("page script failed")
        return response.get("result", {}).get("value")

    def wait(self, expression: str, timeout: float, what: str, poll: float = 0.25):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.js(expression):
                return
            time.sleep(poll)
        raise TimeoutError(f"timed out waiting for {what}")

    def shot(self, path: Path) -> None:
        response = self.call("Page.captureScreenshot", format="png")
        path.write_bytes(base64.b64decode(response["data"]))


TURNS = """[...document.querySelectorAll('.thread-turns > .msg')].map(el => ({
 cls: el.className,
 text: (el.classList.contains('msg-note') ? (el.querySelector('.note-main p') || el).innerText
       : (el.querySelector('.msg-bubble, .msg-prose') || el).innerText).trim().slice(0, 1200)}))"""


def read_key_file(path: Path) -> str:
    """Accept a bare key or a single NAME=value line, preserving '=' in the key."""
    value = path.read_text(encoding="utf-8").strip()
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", value):
        value = value.split("=", 1)[1].strip()
    return value


def safe_profile_root(root: Path, appdata: str | None = None) -> bool:
    root = root.resolve()
    roaming = (root / "Roaming").resolve()
    real = Path(appdata).resolve() if appdata else None
    if real and (roaming == real or roaming == real.parent or real in roaming.parents):
        return False
    return (roaming / "STAR").is_dir()


def count_saved_prompt(db: Path, marker: str) -> int:
    with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as con:
        return con.execute(
            "SELECT count(*) FROM messages WHERE role = ? AND body LIKE ?",
            ("user", "%" + marker + "%"),
        ).fetchone()[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--exe", required=True)
    parser.add_argument("--profile-root", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", default="star-fast")
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--port", type=int, default=9333)
    parser.add_argument("--prompt", default="ACCEPT-MARKER-0002: in one short sentence, what is a RemoteEvent in Roblox?")
    parser.add_argument("--shots", required=True)
    parser.add_argument("--timeout", type=float, default=420.0)
    parser.add_argument("--keep-settings", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.profile_root).resolve()
    if not safe_profile_root(root, os.environ.get("APPDATA")):
        print("REFUSED: --profile-root must hold a copy at Roaming\\STAR and must not be the real profile")
        return 2

    roaming, local = root / "Roaming", root / "Local"
    shots = Path(args.shots)
    shots.mkdir(parents=True, exist_ok=True)
    local.mkdir(parents=True, exist_ok=True)
    key = read_key_file(Path(args.key_file))
    results: list[bool] = []

    def check(ok: bool, name: str, detail: str = "") -> bool:
        results.append(ok)
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""), flush=True)
        return ok

    settings_path = roaming / "STAR" / "settings.json"
    if not args.keep_settings:
        settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
        settings.update({"provider": "star_server", "server_endpoint": args.endpoint, "model": args.model})
        settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")

    env = dict(os.environ, APPDATA=str(roaming), LOCALAPPDATA=str(local),
               QTWEBENGINE_REMOTE_DEBUGGING=str(args.port))
    if key:
        env["STAR_SERVER_API_KEY"] = key
    started = time.monotonic()
    proc = subprocess.Popen([args.exe], env=env)
    cdp = None
    try:
        page = None
        while time.monotonic() - started < 60 and page is None:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/json", timeout=2) as response:
                    pages = [item for item in json.loads(response.read()) if
                             item.get("type") == "page" and item.get("webSocketDebuggerUrl")]
                    page = pages[0] if pages else None
            except (OSError, ValueError):
                time.sleep(0.5)
        if not check(page is not None, "the packaged app exposes its page"):
            return 1
        cdp = CDP(page["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        cdp.wait("!!document.querySelector('#star-prompt')", 60, "the chat page")
        check(True, "chat page ready", str(cdp.js("document.title")))
        check(proc.poll() is None, "the process is still running")
        cdp.shot(shots / "packaged-01-start.png")
        status = cdp.js("(document.querySelector('.cmp-status')||{innerText:''}).innerText.replace(/\\s+/g,' ').trim()")
        check(True, "status line read", str(status)[:120])
        fresh = cdp.js("(()=>{const b=[...document.querySelectorAll('button')].find(b=>/^\\s*New chat\\s*$/i.test(b.innerText||''));if(b){b.click();return true}return false})()")
        time.sleep(1)
        check(True, "new chat", "clicked" if fresh else "using open thread")
        box = cdp.js("(()=>{const r=document.querySelector('#star-prompt').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()")
        for kind in ("mousePressed", "mouseReleased"):
            cdp.call("Input.dispatchMouseEvent", type=kind, x=box["x"], y=box["y"], button="left", clickCount=1)
        cdp.call("Input.insertText", text=args.prompt)
        check(cdp.js("document.querySelector('#star-prompt').value") == args.prompt, "prompt typed")
        check(cdp.js("document.querySelector('.cmp-send').disabled") is False, "Send is enabled")
        before = cdp.js(f"({TURNS}).length") or 0
        send = cdp.js("(()=>{const r=document.querySelector('.cmp-send').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()")
        sent_at = time.monotonic()
        for kind in ("mousePressed", "mouseReleased"):
            cdp.call("Input.dispatchMouseEvent", type=kind, x=send["x"], y=send["y"], button="left", clickCount=1)
        cdp.wait(f"!!document.querySelector('.cmp.is-busy') || document.querySelectorAll('.thread-turns > .msg').length > {before}", 20, "turn start", poll=0.05)
        first_word = None
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            if first_word is None and cdp.js("!!(document.querySelector('.msg-star .msg-prose')||{innerText:''}).innerText.trim()"):
                first_word = time.monotonic() - sent_at
            if not cdp.js("!!document.querySelector('.cmp.is-busy')"):
                break
            time.sleep(0.2)
        total = time.monotonic() - sent_at
        turns = cdp.js(TURNS) or []
        time.sleep(1.5)
        cdp.shot(shots / "packaged-02-reply.png")
        check(not cdp.js("!!document.querySelector('.cmp.is-busy')"), "turn ended", f"{total:.1f} s")
        check(len(turns) >= before + 2, "question and answer added", str(len(turns) - before))
        last = turns[-1] if turns else {"cls": "", "text": ""}
        check("msg-star" in last["cls"] and bool(last["text"]), "STAR answered", last["text"][:220].replace("\n", " "))
        check(True, "timing", f"first words after {first_word:.1f} s" if first_word is not None else "first word not seen")
        if key:
            check(key not in (cdp.js("document.documentElement.innerText") or ""), "server key absent from page")
    except Exception as error:
        check(False, "run completed", f"{type(error).__name__}: {error}"[:300])
        try:
            if cdp:
                cdp.shot(shots / "packaged-99-error.png")
        except Exception:
            pass
    finally:
        if cdp:
            cdp.close()
        if proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(proc.pid)], capture_output=True)
            try:
                proc.wait(25)
                check(True, "window closed normally", f"exit code {proc.returncode}")
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
                check(False, "window closed normally", "forced termination")

    try:
        count = count_saved_prompt(roaming / "STAR" / "conversations.sqlite3", args.prompt.split(":", 1)[0])
        check(count == 1, "prompt stored exactly once", f"user rows: {count}")
    except Exception as error:
        check(False, "prompt stored exactly once", type(error).__name__)
    failures = results.count(False)
    print(f"RESULT: {len(results) - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
