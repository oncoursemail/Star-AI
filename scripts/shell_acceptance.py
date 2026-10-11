#!/usr/bin/env python3
"""Drive the real STAR Desktop shell against a real STAR Server, without a human.

This is an acceptance tool, not a unit test. Each phase starts the same window
the owner gets (`star.react_shell.launch()`: PySide6 Qt WebEngine, the Qt
WebChannel bridge and the built React bundle in frontend/dist), uses real mouse
and key events to exercise it, saves a screenshot of the window after each
step, and checks the result in the page and in the profile's SQLite database.

Nothing here is a stub: the bridge, the worker threads, the provider code and
the model server are the real ones. A phase is one process, so "restart" is a
real restart on the same profile.

Phases (default: all, in this order)
    first      boot, Model page + Test server, Fast send, Stop, failed send, Retry
    restart    relaunch: history, cancelled/failed rows and Retry survive; Retry works
    agent      Agent mode with a read-only tool call; the activity timeline
    pages      every sidebar page, live Settings checks, small-window layout
    wrongkey   a wrong server key: Test server and a send both explain it
    midclose   the window is closed while a reply streams
    afterclose relaunch after that: what was recorded
    upgrade    first start on a profile left by the released v0.8 app (old settings,
               old message table, on-device provider): nothing is lost or rewritten
    testclose  the window is closed while "Test actual response" is still waiting
    media      Settings shows where STAR generates (servers or this PC) with the host's notes;
               Create image makes a real picture with ComfyUI on this PC when it is running,
               and shows the host's plain explanation when it is not (no model server needed)
    settings   Settings > Voice and Settings > Roblox Studio: both sections render from the real host,
               a voice preview and a voice choice reach the voice engine, the commanding voices appear
               only after their switch, the STAR Studio server's address and command are stored and
               refused by the real host, and "Test connection" answers through the host's own check
    followup   Fast mode in a new chat: the first message and two follow-up messages, with the time
               from Enter to the first visible words of each

Safety
    * APPDATA is a fresh folder made by this script; a phase refuses to start
      when APPDATA is not such a folder, so the owner's real STAR data is never
      read or written.
    * The keyring is replaced by keyring's null backend for the run, so the
      Windows Credential Manager is never read or written either.
    * The server key comes from STAR_SERVER_API_KEY (or --key-file). It is never
      printed. The run fails if the key appears in the page, in a bridge event
      or in a log.
    * It never clicks anything that leaves the app: no file dialogs, no update
      install, no clipboard writes, and no Studio discovery on this PC. The settings
      phase tests the STAR Studio server choice only: first with nothing stored (the
      host starts nothing), then with a placeholder address under the reserved name
      `.invalid`, which cannot exist, so the one `ssh` it starts ends at once. An
      operator's STAR_STUDIO_MCP_COMMAND is removed from every phase's environment,
      so no phase can reach a real Studio.
    * The settings phase replaces the loudspeaker (and only the loudspeaker) by a
      silent sink, so the PC makes no sound; the voice engine and everything else
      are the real ones. `--audible` plays the preview through the real speakers.

Skipped automatically (exit 0, "SKIPPED: ...") when PySide6 with QtWebEngine,
the built interface, or the server settings are absent:

    STAR_SERVER_API_KEY       the server's bearer key (or --key-file PATH)
    STAR_ACCEPTANCE_SERVER    e.g. http://192.168.1.20:8080/v1
    STAR_ACCEPTANCE_MODEL     a model ID that server offers

Optional
    STAR_VOICE_MODELS            folder with the voice model files (star/voice/engines.py)
    STAR_ACCEPTANCE_EXTRA_PATH   import folders (os.pathsep-separated) added AFTER the environment's
                                 own, for optional engines that are installed elsewhere on this PC
                                 (for example the voice packages); nothing the environment already
                                 has is replaced

Example
    python scripts/shell_acceptance.py --key-file ~/.star/server_api_key --shots out/screenshots
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import re
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = '.star-shell-acceptance-profile'
PHASES = ('first', 'restart', 'agent', 'pages', 'wrongkey', 'midclose', 'afterclose', 'upgrade', 'testclose', 'media',
          'settings', 'followup')
CONSOLE_PROBE = 'shell-acceptance console probe'
ENV_KEY = 'STAR_SERVER_API_KEY'
ENV_SERVER = 'STAR_ACCEPTANCE_SERVER'
ENV_MODEL = 'STAR_ACCEPTANCE_MODEL'
WRONG_KEY = 'acceptance-wrong-key-not-a-secret'

PROMPT_FAST = 'Reply with one short sentence: what is 2+2?'
PROMPT_LONG = 'Write a detailed 400 word essay about the history of the Roman Empire.'
PROMPT_FAIL = 'Say hello in three words.'
PROMPT_IMAGE = 'A small lighthouse on a rocky island at sunset, clean low-poly game art'
PROMPT_VIDEO_LINK = 'Summarise what happens in this video in two sentences: https://www.youtube.com/watch?v=star0accept1'
NOT_WATCHED = re.compile(r"(?:haven't|have not|didn't|did not|can't|cannot|can not|unable to|not able to|no way to)\s+"
                         r"(?:actually\s+)?(?:watch|view|see|open|access|play)|only (?:have|see|got) (?:the|a) (?:link|title|url)|"
                         r"attach(?:ing)? the (?:video )?file", re.I)
# "tool" makes the read-only Agent Skills tools available; nothing here asks for Studio or a workspace.
PROMPT_AGENT = ('Call the star_skill_catalog tool once, then tell me in one short sentence '
                'how many Agent Skills it returned.')
PROMPT_FOLLOW_UP = ('And what is 3+3? One short sentence.', 'Now add those two results. One short sentence.')
# Placeholders only: `.invalid` is a reserved name that never resolves (RFC 2606).
STUDIO_ADDRESS = 'star@studio-acceptance.invalid'
STUDIO_COMMAND = '/home/star/bin/studio-mcp.sh'
STUDIO_REFUSED_COMMAND = 'run.sh; id'
ENV_EXTRA_PATH = 'STAR_ACCEPTANCE_EXTRA_PATH'
ENV_STUDIO_COMMAND = 'STAR_STUDIO_MCP_COMMAND'
TYPED_WHILE_STREAMING = 'typing while it streams'
PAGES = (('Projects', 'Your workspaces'), ('Library', 'Your library'), ('Tools', 'Connect your tools'),
         ('Analytics', 'Analytics'), ('Model', 'Model & connection'), ('Settings', 'Settings'))


# ----------------------------------------------------------------- preflight
def skip_reason(env=None) -> str | None:
    """Why this run cannot happen here, or None when everything needed is present."""
    env = os.environ if env is None else env
    missing = [name for name in (ENV_KEY, ENV_SERVER, ENV_MODEL) if not str(env.get(name, '')).strip()]
    if missing:
        return 'set ' + ', '.join(missing) + ' to run against a STAR Server'
    try:
        import PySide6.QtWebEngineWidgets  # noqa: F401
        import PySide6.QtWebChannel  # noqa: F401
        import PySide6.QtTest  # noqa: F401
    except Exception as exc:  # ImportError, or a broken Qt install
        return f'PySide6 with QtWebEngine is not installed ({type(exc).__name__})'
    if not (ROOT / 'frontend' / 'dist' / 'index.html').is_file():
        return 'frontend/dist is not built (run tsc -b and vite build in frontend/)'
    return None


def owner_data_roots() -> list[Path]:
    """Folders that hold the owner's real application data. A run never uses them."""
    home = Path.home()
    return [home / 'AppData' / 'Roaming', home / 'AppData' / 'Local', home / '.local' / 'share']


def is_acceptance_profile(folder) -> bool:
    """True only for a folder this tool created: it carries the marker and is not a real data root."""
    try:
        path = Path(folder).resolve()
    except (OSError, TypeError, ValueError):
        return False
    if not (path / MARKER).is_file():
        return False
    return all(path != root.resolve() for root in owner_data_roots())


def new_profile(evidence: Path) -> Path:
    profile = Path(tempfile.mkdtemp(prefix='profile-', dir=str(evidence)))
    (profile / MARKER).write_text('Created by scripts/shell_acceptance.py. Safe to delete.\n', encoding='utf-8')
    return profile


RELEASED_MESSAGES = (
    ('user', 'How do I tween a GUI frame in Roblox?'),
    ('assistant', 'Use TweenService:Create(frame, TweenInfo.new(0.3), {Position = goal}):Play().'),
    ('user', 'And how do I cancel it?'),
    ('assistant', 'Keep the Tween object and call :Cancel() on it.'),
)


def seed_released_profile(profile: Path, endpoint: str) -> None:
    """A profile as the released v0.8 app leaves it, for the upgrade phase.

    settings.json has only the fields that release knew (no provider, no server
    fields) plus one it has since dropped; the database is the first message
    table, without chat threads or turn outcomes.
    """
    home = profile / 'STAR'
    home.mkdir(parents=True, exist_ok=True)
    (home / 'settings.json').write_text(json.dumps({
        'endpoint': endpoint, 'model': 'released-local-model', 'project': 'STAR', 'workspace': '', 'studio_id': '',
        'studio_edit': False, 'workspace_edit': False, 'max_calls': 12, 'context_chars': 26000, 'llama_server': '',
        'gguf_model': '', 'gpu_layers': 25, 'reduced_motion': False, 'obsidian_vault': '', 'obsidian_enabled': False,
        'skills_enabled': True, 'graphify_enabled': True, 'a_setting_this_build_no_longer_has': 'kept out of the way',
    }, indent=2), encoding='utf-8')
    connection = sqlite3.connect(home / 'conversations.sqlite3')
    try:
        with connection:
            connection.execute('CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL, '
                               'role TEXT NOT NULL, body TEXT NOT NULL, created TEXT NOT NULL)')
            connection.executemany('INSERT INTO messages (project,role,body,created) VALUES (?,?,?,?)',
                                   [('STAR', role, body, f'2026-09-0{index + 1}T10:00:00+00:00')
                                    for index, (role, body) in enumerate(RELEASED_MESSAGES)])
    finally:
        connection.close()


def closed_loopback_endpoint() -> str:
    """An address on this PC where nothing listens, so a failed send never leaves the machine."""
    for _ in range(20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        if port < 1024:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as check:
            check.settimeout(1.0)
            if check.connect_ex(('127.0.0.1', port)) != 0:
                return f'http://127.0.0.1:{port}/v1'
    raise RuntimeError('Could not find a closed loopback port')


def scrub(text: str, key: str) -> str:
    return text.replace(key, '[key hidden]') if key and len(key) >= 8 else text


def read_messages(profile: Path) -> list[dict]:
    """Every stored message of the acceptance profile, oldest first (read-only)."""
    db = profile / 'STAR' / 'conversations.sqlite3'
    if not db.is_file():
        return []
    connection = sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True, timeout=10)
    try:
        rows = connection.execute(
            'SELECT id,project,chat_id,role,body,status,reply_to,created FROM messages ORDER BY id').fetchall()
    finally:
        connection.close()
    names = ('id', 'project', 'chat_id', 'role', 'body', 'status', 'reply_to', 'created')
    return [dict(zip(names, row)) for row in rows]


def summarize(numbers: list[float]) -> dict:
    if not numbers:
        return {'n': 0}
    ordered = sorted(numbers)
    pick = lambda q: ordered[min(len(ordered) - 1, int(q * len(ordered)))]
    return {'n': len(ordered), 'median': round(pick(0.5), 1), 'p95': round(pick(0.95), 1),
            'max': round(ordered[-1], 1)}


def format_table(steps: list[dict]) -> str:
    """Plain pass/fail table: one line per step, then every failed check."""
    lines = [f'{"phase":<11}{"step":<22}{"result":<7}{"time":>8}  notes', '-' * 78]
    for step in steps:
        failed = [c for c in step.get('checks', []) if not c['ok']]
        note = step.get('error') or ('; '.join(c['label'] for c in failed) if failed else
                                     f'{len(step.get("checks", []))} checks')
        lines.append(f'{step["phase"]:<11}{step["name"]:<22}{step["status"]:<7}{step.get("seconds", 0):>7}s  {note[:120]}')
    known = [(step, c) for step in steps for c in step.get('checks', []) if c.get('known')]
    if known:
        lines += ['', 'Known defects seen again (not counted as failures):']
        lines += [f'  {step["phase"]}/{step["name"]}: {c["label"]} -- {c["known"]}' for step, c in known]
    return '\n'.join(lines)


# ---------------------------------------------------------------- page helpers
PAGE_HELPERS = r"""
(() => {
  if (window.__acc) return true;
  const acc = window.__acc = {errors: [], keys: [], calls: [], frames: {on: false, gaps: []},
                              lag: {on: false, n: 0, max: 0, over100: 0}, stream: null};
  window.addEventListener('error', e => acc.errors.push({type: 'error', message: String(e.message),
    source: String(e.filename || ''), line: e.lineno || 0}));
  window.addEventListener('unhandledrejection', e => acc.errors.push({type: 'unhandledrejection',
    message: String(e.reason && (e.reason.stack || e.reason.message || e.reason))}));
  acc.visible = el => !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
  acc.find = (selector, text) => {
    for (const el of document.querySelectorAll(selector)) {
      if (!acc.visible(el)) continue;
      if (text && !((el.innerText || '') + ' ' + (el.getAttribute('aria-label') || '')).includes(text)) continue;
      return el;
    }
    return null;
  };
  acc.box = (selector, text) => {
    const el = acc.find(selector, text);
    if (!el) return null;
    el.scrollIntoView({block: 'center', inline: 'nearest'});
    const r = el.getBoundingClientRect();
    return {x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width, h: r.height,
            disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true',
            text: (el.innerText || '').trim().slice(0, 160)};
  };
  acc.text = selector => { const el = document.querySelector(selector); return el ? (el.innerText || '').trim() : null };
  acc.resetStream = () => { acc.stream = {firstAt: 0, paintedAt: 0, samples: []}; return true };
  acc.resetStream();
  // When does text of the live (still streaming) answer really exist in the page?
  new MutationObserver(() => {
    const live = document.querySelector('.msg-star[aria-busy="true"] .msg-prose');
    if (!live) return;
    const n = (live.textContent || '').length;
    if (!n) return;
    const s = acc.stream;
    if (!s.firstAt) { s.firstAt = Date.now(); requestAnimationFrame(() => { s.paintedAt = Date.now() }) }
    if (!s.samples.length || s.samples[s.samples.length - 1][1] !== n) s.samples.push([Date.now(), n]);
  }).observe(document.documentElement, {subtree: true, childList: true, characterData: true});
  let last = 0;
  const frame = t => {
    if (acc.frames.on) { if (last) acc.frames.gaps.push(Math.round(t - last)); last = t } else last = 0;
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
  let tick = performance.now();
  setInterval(() => {
    const now = performance.now();
    if (acc.lag.on) { const late = now - tick - 50; acc.lag.n++; if (late > acc.lag.max) acc.lag.max = late; if (late > 100) acc.lag.over100++ }
    tick = now;
  }, 50);
  document.addEventListener('keydown', e => {
    if (!e.target || e.target.id !== 'star-prompt') return;
    const rec = {key: e.key, down: Date.now(), input: 0, painted: 0};
    acc.keys.push(rec);
    requestAnimationFrame(() => requestAnimationFrame(() => { rec.painted = Date.now() }));
  }, true);
  document.addEventListener('input', e => {
    if (!e.target || e.target.id !== 'star-prompt' || !acc.keys.length) return;
    const rec = acc.keys[acc.keys.length - 1];
    if (!rec.input) rec.input = Date.now();
  }, true);
  // Every bridge call the page makes: action, how long the synchronous answer took, and any refusal.
  const native = window.starBridge;
  if (native && typeof native.invoke === 'function' && !native.__accWrapped) {
    const invoke = native.invoke;
    native.invoke = function (raw, done) {
      const began = performance.now();
      let action = '';
      try { action = JSON.parse(raw).action } catch (error) { /* not ours to judge */ }
      return invoke.call(this, raw, answer => {
        const rec = {action, ms: Math.round(performance.now() - began), ok: null, error: ''};
        try { const body = JSON.parse(answer); rec.ok = !!body.ok; rec.pending = !!body.pending; rec.error = String(body.error || '').slice(0, 300) } catch (error) { rec.error = 'unparseable answer' }
        acc.calls.push(rec);
        done(answer);
      });
    };
    native.__accWrapped = true;
  }
  return true;
})()
"""

TRANSCRIPT_JS = r"""
[...document.querySelectorAll('.thread-turns > .msg')].map(el => ({
  role: el.classList.contains('msg-user') ? 'user' : el.classList.contains('msg-star') ? 'assistant' : 'event',
  status: el.classList.contains('is-failed') ? 'failed' : el.classList.contains('is-cancelled') ? 'cancelled' : 'complete',
  text: (el.classList.contains('msg-note') ? (el.querySelector('.note-main p') || el).innerText
        : (el.querySelector('.msg-bubble, .msg-prose') || el).innerText).trim(),
  title: el.querySelector('.note-main strong') ? el.querySelector('.note-main strong').innerText.trim() : '',
  buttons: [...el.querySelectorAll('.note-button')].map(b => b.innerText.trim()),
}))
"""

OVERFLOW_JS = r"""
(() => {
  const wide = [];
  for (const el of document.querySelectorAll('.shell-main *')) {
    const r = el.getBoundingClientRect();
    if (r.width && r.height && (r.right > window.innerWidth + 1 || r.left < -1) && wide.length < 8)
      wide.push((el.className && el.className.baseVal === undefined ? String(el.className) : el.tagName).slice(0, 60));
  }
  return {scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth, outside: wide};
})()
"""


class Step:
    def __init__(self, phase: str, name: str):
        self.phase, self.name = phase, name
        self.checks: list[dict] = []
        self.facts: dict = {}
        self.shots: list[str] = []
        self.error = ''
        self.started = time.time()
        self.seconds = 0.0

    def check(self, ok, label: str, detail='', known: str = '') -> bool:
        """Record one check. `known` names a defect that is documented and not fixed yet: such a
        check is listed as KNOWN instead of failing the run, and becomes a plain pass once it is fixed."""
        entry = {'ok': bool(ok), 'label': label, 'detail': str(detail)[:500]}
        if known and not ok:
            entry.update(ok=True, known=known)
        self.checks.append(entry)
        mark = '  ok   ' if ok else '  KNOWN ' if known else '  FAIL '
        print(mark + label + (f'  [{str(detail)[:200]}]' if detail != '' and not ok else ''), flush=True)
        return bool(ok)

    def fact(self, name: str, value) -> None:
        self.facts[name] = value

    @property
    def status(self) -> str:
        return 'FAIL' if self.error or any(not c['ok'] for c in self.checks) else 'PASS'

    def as_dict(self) -> dict:
        return {'phase': self.phase, 'name': self.name, 'status': self.status, 'seconds': round(self.seconds, 1),
                'error': self.error, 'checks': self.checks, 'facts': self.facts, 'shots': self.shots}


class Driver:
    """Sequential steps on top of Qt's event loop: every wait runs a nested loop, so the app keeps working."""

    def __init__(self, app, shell, options):
        from PySide6.QtCore import QEventLoop, QPoint, Qt, QTimer
        from PySide6.QtTest import QTest
        self.Qt, self.QTimer, self.QEventLoop, self.QPoint, self.QTest = Qt, QTimer, QEventLoop, QPoint, QTest
        self.app, self.shell, self.options = app, shell, options
        self.view = shell.view
        self.page = shell.view.page()
        self.phase = options.child
        self.profile = Path(os.environ['APPDATA'])
        self.shots_dir = Path(options.shots)
        self.key = os.environ.get(ENV_KEY, '')
        self.real_key = os.environ.get('STAR_ACCEPTANCE_REAL_KEY', '') or self.key
        self.steps: list[Step] = []
        self.console: list[dict] = []
        self.events: list[dict] = []
        self.python_errors: list[str] = []
        self.qt_messages: list[str] = []
        self.leaks: list[str] = []
        self.marks: dict = {}
        self.crashed = ''

    # ---- plumbing
    def install_hooks(self) -> None:
        from PySide6.QtCore import qInstallMessageHandler

        def on_console(_page, level, message, line, source):
            self.console.append({'level': getattr(level, 'name', str(level)), 'message': str(message)[:600],
                                 'line': int(line), 'source': str(source)[-80:], 't': round(time.time(), 3)})
        # RestrictedPage is created inside launch(); patch its class so every console line reaches us.
        type(self.page).javaScriptConsoleMessage = on_console
        self.page.renderProcessTerminated.connect(
            lambda status, code: setattr(self, 'crashed', f'render process ended: {status} ({code})'))
        self.shell.bridge.event.connect(self.on_bridge_event)

        def on_qt(_mode, _context, message):
            self.qt_messages.append(str(message)[:400])
        qInstallMessageHandler(on_qt)

        def on_exception(kind, value, trace):
            self.python_errors.append(''.join(traceback.format_exception(kind, value, trace))[-3000:])
        sys.excepthook = on_exception
        threading.excepthook = lambda args: on_exception(args.exc_type, args.exc_value, args.exc_traceback)
        sys.unraisablehook = lambda info: on_exception(type(info.exc_value), info.exc_value, info.exc_traceback)

    def on_bridge_event(self, raw: str) -> None:
        if self.real_key and self.real_key in raw:
            self.leaks.append('bridge event')
        record = {'t': time.time()}
        try:
            body = json.loads(raw)
        except ValueError:
            self.events.append({**record, 'kind': 'unparseable'})
            return
        record.update(kind=body.get('kind'), request=str(body.get('requestId', ''))[:8])
        data = body.get('data')
        if isinstance(data, dict):
            if isinstance(data.get('delta'), str):
                record['delta_chars'] = len(data['delta'])
            for name in ('phase', 'activity'):
                if name in data:
                    record[name] = data[name]
            if body.get('kind') == 'result':
                record['data'] = data if len(raw) < 6000 else {k: (v if not isinstance(v, str) else v[:1500])
                                                               for k, v in data.items()}
            if body.get('kind') == 'voice':
                record['voice'] = str(data.get('type', ''))[:40]
                if isinstance(data.get('message'), str):
                    record['text'] = data['message'][:600]
        elif isinstance(data, str):
            record['text'] = data[:600]
        self.events.append(record)

    def pump(self, seconds: float) -> None:
        loop = self.QEventLoop()
        self.QTimer.singleShot(max(1, int(seconds * 1000)), loop.quit)
        loop.exec()

    def js(self, expression: str, timeout: float = 15.0):
        """Evaluate one JavaScript expression in the page and return its JSON value (None if unavailable)."""
        loop = self.QEventLoop()
        box: dict = {}

        def done(value):
            box['value'] = value
            loop.quit()
        code = 'JSON.stringify((()=>{try{return (' + expression + ')}catch(e){return {__error:String(e)}}})())'
        self.page.runJavaScript(code, 0, done)
        self.QTimer.singleShot(int(timeout * 1000), loop.quit)
        loop.exec()
        value = box.get('value')
        if not isinstance(value, str) or not value:
            return None
        try:
            return json.loads(value)
        except ValueError:
            return None

    def helpers(self) -> None:
        self.js(PAGE_HELPERS.strip())

    def wait_for(self, expression: str, timeout: float, what: str, poll: float = 0.1):
        deadline = time.time() + timeout
        while True:
            value = self.js(expression)
            if value and not (isinstance(value, dict) and '__error' in value):
                return value
            if self.crashed:
                raise RuntimeError(self.crashed)
            if time.time() > deadline:
                raise TimeoutError(f'waited {timeout:.0f}s for {what}')
            self.pump(poll)

    def box(self, selector: str, text: str | None = None):
        return self.js(f'__acc.box({json.dumps(selector)}, {json.dumps(text)})')

    def click(self, selector: str, text: str | None = None, timeout: float = 15.0) -> dict:
        """A real left click at the centre of the first visible match."""
        what = selector + (f' "{text}"' if text else '')
        self.wait_for(f'!!__acc.find({json.dumps(selector)}, {json.dumps(text)})', timeout, what)
        self.box(selector, text)          # scrolls it into view
        self.pump(0.25)                   # let a smooth scroll or a page fade settle
        target = self.box(selector, text)
        if not target:
            raise RuntimeError(f'{what} disappeared before the click')
        if target['disabled']:
            raise RuntimeError(f'{what} is disabled')
        point = self.QPoint(int(target['x']), int(target['y']))
        proxy = self.view.focusProxy()
        self.QTest.mouseMove(proxy, point)
        self.QTest.mouseClick(proxy, self.Qt.MouseButton.LeftButton, self.Qt.KeyboardModifier.NoModifier, point)
        self.pump(0.15)
        return target

    def type_text(self, text: str) -> None:
        self.QTest.keyClicks(self.view.focusProxy(), text)
        self.pump(0.15)

    def press(self, key, modifier=None) -> None:
        self.QTest.keyClick(self.view.focusProxy(), key, modifier or self.Qt.KeyboardModifier.NoModifier)
        self.pump(0.1)

    def select_all_and_type(self, text: str) -> None:
        self.press(self.Qt.Key.Key_A, self.Qt.KeyboardModifier.ControlModifier)
        self.press(self.Qt.Key.Key_Delete)
        if text:
            self.type_text(text)

    def shot(self, name: str) -> str:
        self.shots_dir.mkdir(parents=True, exist_ok=True)
        self.pump(0.3)  # one more paint, so the picture shows the state the checks just read
        path = self.shots_dir / f'shell-{name}.png'
        if not self.shell.grab().save(str(path)):
            raise RuntimeError(f'could not save {path.name}')
        print(f'  shot {path.name}', flush=True)
        return str(path)

    @contextlib.contextmanager
    def step(self, name: str):
        current = Step(self.phase, name)
        self.steps.append(current)
        print(f'--- {self.phase}/{name}', flush=True)
        try:
            yield current
        except Exception as exc:  # a step that cannot continue is a failed step, not a dead run
            current.error = scrub(f'{type(exc).__name__}: {exc}', self.real_key)[:600]
            print('  FAIL ' + current.error, flush=True)
            with contextlib.suppress(Exception):
                current.shots.append(self.shot(f'{name}-FAILED'))
        finally:
            current.seconds = time.time() - current.started
            self.save()

    def save(self) -> None:
        page = self.js('({errors: __acc.errors, calls: __acc.calls})') or {}
        report = {
            'phase': self.phase, 'steps': [s.as_dict() for s in self.steps], 'marks': self.marks,
            'console': self.console, 'page_errors': page.get('errors', []), 'bridge_calls': page.get('calls', []),
            'bridge_events': self.events[-4000:], 'python_errors': self.python_errors,
            'qt_messages': self.qt_messages, 'leaks': self.leaks, 'crashed': self.crashed,
        }
        text = scrub(json.dumps(report, indent=1, default=str), self.real_key)
        (Path(self.options.evidence) / f'{self.phase}.json').write_text(text, encoding='utf-8')

    # ---- reading the app
    def status(self) -> dict:
        return self.js("({label: __acc.text('.cmp-status-label'), state: __acc.text('.cmp-status-state'),"
                       " tone: (document.querySelector('.cmp-status')||{className:''}).className})") or {}

    def transcript(self) -> list[dict]:
        return self.js(TRANSCRIPT_JS.strip()) or []

    def busy(self) -> bool:
        return bool(self.js("!!document.querySelector('.cmp.is-busy')"))

    def key_in_page(self) -> bool:
        return bool(self.real_key) and bool(self.js(
            f'document.documentElement.outerHTML.includes({json.dumps(self.real_key)})'))

    def settings_file(self) -> dict:
        return json.loads((self.profile / 'STAR' / 'settings.json').read_text(encoding='utf-8'))

    def open_page(self, name: str, heading: str) -> None:
        self.click('.rail-foot .rail-item' if name == 'Settings' else 'nav.rail-group .rail-item', name)
        self.wait_for(f"(__acc.text('.page-stage .page-intro h1')||'').startsWith({json.dumps(heading)})", 15, f'{name} page')
        self.pump(0.4)

    def open_chat(self) -> None:
        self.click('.rail-brand')
        self.wait_for("!!document.querySelector('#star-prompt')", 15, 'chat page')
        self.pump(0.4)

    # ---- turns
    def start_turn(self, step: Step, prompt: str, mode: str | None = None) -> dict:
        if mode:
            self.click(f'.cmp-mode[data-mode="{mode}"]')
            step.check(self.js(f"document.querySelector('.cmp-mode[data-mode=\"{mode}\"]').getAttribute('aria-checked')") == 'true',
                       f'{mode} mode is selected')
        self.js('__acc.resetStream()')
        self.click('#star-prompt')
        self.select_all_and_type(prompt)
        typed = self.js("document.querySelector('#star-prompt').value")
        step.check(typed == prompt, 'real key events typed the prompt into the composer', typed)
        mark = len(self.events)
        sent_at = time.time()
        self.press(self.Qt.Key.Key_Return)
        return {'sent_at': sent_at, 'mark': mark, 'prompt': prompt}

    def stream_metrics(self, turn: dict) -> dict:
        stream = self.js('__acc.stream') or {}
        events = self.events[turn['mark']:]
        deltas = [e for e in events if e.get('delta_chars')]
        # Not the end of the turn: the result of the app's own warm-up, which can arrive while a turn runs.
        ended = next((e for e in events if e.get('kind') == 'error'
                      or (e.get('kind') == 'result' and 'primed' not in (e.get('data') or {}))), None)
        samples = stream.get('samples') or []
        sent_ms = turn['sent_at'] * 1000
        facts = {'bridge_delta_events': len(deltas), 'visible_updates': len(samples)}
        if deltas:
            facts['send_to_first_bridge_delta_ms'] = round(deltas[0]['t'] * 1000 - sent_ms)
        if stream.get('firstAt'):
            facts['send_to_first_visible_text_ms'] = round(stream['firstAt'] - sent_ms)
            if stream.get('paintedAt'):
                facts['first_text_to_paint_ms'] = round(stream['paintedAt'] - stream['firstAt'])
        if ended:
            facts['send_to_end_ms'] = round(ended['t'] * 1000 - sent_ms)
        if len(samples) >= 2:
            seconds = (samples[-1][0] - samples[0][0]) / 1000
            chars = samples[-1][1] - samples[0][1]
            facts.update(stream_seconds=round(seconds, 2), stream_chars=samples[-1][1])
            if seconds > 0:
                facts['visible_chars_per_s'] = round(chars / seconds, 1)
                # One bridge delta is one model token while the server is slower than the 75 ms coalescing window.
                facts['bridge_deltas_per_s'] = round((len(deltas) - 1) / seconds, 2) if len(deltas) > 1 else 0
                facts['tokens_per_s_estimate_chars_div_4'] = round(chars / 4 / seconds, 2)
        return facts

    def wait_idle(self, timeout: float) -> None:
        self.wait_for("!document.querySelector('.cmp.is-busy')", timeout, 'the turn to end', poll=0.2)
        self.pump(0.6)  # the result handler re-reads state from the host


# ------------------------------------------------------------------- the steps
def step_boot(d: Driver, expect_history: bool = False) -> None:
    with d.step('boot') as s:
        d.wait_for("!!document.querySelector('#star-prompt') && !!document.querySelector('.cmp-status')", 90,
                   'the chat composer', poll=0.05)
        ready = time.time()
        d.helpers()
        d.marks['interactive_at'] = ready
        spawned = float(d.options.spawned_at or 0)
        if spawned:
            s.fact('process_start_to_interactive_s', round(ready - spawned, 2))
        s.fact('python_main_to_interactive_s', round(ready - d.marks['python_main'], 2))
        s.fact('qt_app_to_interactive_s', round(ready - d.marks['qt_app'], 2))
        profile = d.page.profile()
        s.fact('webengine_profile_off_the_record', bool(profile.isOffTheRecord()))
        s.fact('window', d.js('({w: innerWidth, h: innerHeight, dpr: devicePixelRatio})'))
        s.fact('platform', d.app.platformName())
        s.check(d.shell.isVisible(), 'the real react_shell window is shown')
        s.check(d.js("!!window.qt && !!window.starBridge"), 'the page is connected to the Qt WebChannel bridge')
        d.js(f"(console.info({json.dumps(CONSOLE_PROBE)}), true)")
        d.pump(0.2)
        s.check(any(c['message'] == CONSOLE_PROBE for c in d.console),
                'console messages of the page reach this tool (so "no console errors" is measured)')
        if not expect_history:
            s.check(d.js("__acc.text('.thread-hello h2')") == 'What are we making?', 'chat empty state renders')
            s.check(d.js("document.querySelectorAll('.starters .starter').length") == 4, 'four starter prompts render')
        status = d.status()
        s.fact('status', status)
        settings = d.settings_file()
        on_server = settings.get('provider') == 'star_server'
        s.check(('STAR Server' if on_server else 'This PC') in (status.get('label') or '')
                and settings['model'] in (status.get('label') or ''),
                'status names ' + ('STAR Server' if on_server else 'this PC') + ' and the model', status)
        if on_server:
            # Nothing has talked to the server yet unless the app checked it by itself during start.
            checked = any(e.get('kind') == 'result' and 'steps' in (e.get('data') or {}) for e in d.events)
            s.fact('server_checked_during_start', checked)
            # The app now checks the server by itself at start (warm-up). Its light can turn "Ready" a moment
            # before the warm-up's result event arrives (priming is still running), so both are truthful then.
            # With a wrong key that same check fails, and the light then says "Needs attention": also the truth.
            wrong_key = bool(d.real_key) and d.key != d.real_key
            allowed = ('Not checked', 'Needs attention') if wrong_key else ('Not checked', 'Ready')
            s.check(status.get('state') == 'Ready' if checked else status.get('state') in allowed,
                    'status is truthful at start: "Not checked" until a real check or reply', status.get('state'))
        else:
            s.check(status.get('state') == 'Offline', 'status says the model on this PC is not running', status.get('state'))
        s.check(not d.key_in_page(), 'the server key is not in the page')
        s.shots.append(d.shot('boot' if d.phase == 'first' else f'boot-{d.phase}'))
        d.click('#star-prompt')
        focus = d.js("(()=>{const f=getComputedStyle(document.querySelector('#star-prompt'));"
                     "return {active: document.activeElement.id, outline: f.outlineStyle, width: f.outlineWidth}})()") or {}
        s.fact('composer_focus', focus)
        s.check(focus.get('active') == 'star-prompt' and (focus.get('outline') == 'none' or focus.get('width') == '0px'),
                'a real click focuses the composer and no second outline is drawn inside it', focus)
        if d.phase == 'first':
            d.click('.cmp-status')
            d.wait_for("!!document.querySelector('.cmp-status-pop')", 5, 'the status popover')
            popover = d.js("__acc.text('.cmp-status-pop')") or ''
            s.fact('status_popover', popover)
            s.check(settings['server_endpoint'].split('//')[1].split('/')[0] in popover,
                    'status popover shows the server address', popover)
            s.shots.append(d.shot('boot-status'))
            d.press(d.Qt.Key.Key_Escape)


def step_model_page(d: Driver) -> None:
    with d.step('model-page') as s:
        d.open_page('Model', 'Model & connection')
        card = "section[aria-label=\"STAR Server\"]"
        d.wait_for(f"!!document.querySelector('{card}')", 10, 'the STAR Server card')
        text = d.js(f"__acc.text('{card}')") or ''
        s.fact('card_text', text)
        settings = d.settings_file()
        s.check('STAR Server is your AI brain' in text, 'server card is shown')
        s.check(settings['server_endpoint'] in text, 'card shows the saved server address')
        s.check('Key: saved' in text, 'card says a key is present')
        # The app checks the server by itself at start (warm-up). The card must agree with the status light:
        # "not checked yet" before that check has answered, "ready" after it passed.
        # (The light itself is on the chat page; its state at boot was recorded there.)
        light = next((step.facts.get('status', {}).get('state') for step in d.steps if step.name == 'boot'), None)
        s.fact('status_light_at_boot', light)
        s.check('Status: ready' in text if light == 'Ready' else ('not checked yet' in text or 'Status: ready' in text),
                'the card agrees with the status light about the server check', [light, text[-260:]])
        s.check(d.js("(document.querySelector('details.brain-details')||{}).open") is False,
                'the local-model download is folded away as an optional backup')
        s.shots.append(d.shot('model'))
        mark = len(d.events)
        began = time.time()
        d.click(f'{card} button', 'Test server')
        d.wait_for(f"(__acc.text('{card}')||'').includes('Testing server')", 5, 'the testing state')
        s.shots.append(d.shot('model-testing'))
        d.wait_for(f"!!document.querySelector('{card} [role=\"status\"]')", d.options.turn_timeout, 'the server report', poll=0.25)
        s.fact('test_server_seconds', round(time.time() - began, 1))
        d.pump(0.6)
        rows = d.js(f"[...document.querySelectorAll('{card} .integrated-note')].map(r=>r.innerText.replace(/\\s+/g,' ').trim())") or []
        s.fact('rows', rows)
        result = next((e.get('data') for e in d.events[mark:] if e.get('kind') == 'result' and isinstance(e.get('data'), dict)
                       and 'steps' in e['data']), None) or {}
        s.fact('report', {k: result.get(k) for k in ('ok', 'code', 'message', 'models', 'context_tokens', 'slots',
                                                     'first_token_ms', 'sample', 'steps')})
        s.check(result.get('ok') is True, 'Test server passed', result.get('message'))
        for label in ('Server reachable', 'Key and model list', 'Context and slots', 'Real test reply'):
            s.check(any(row.startswith(label) for row in rows), f'step "{label}" is shown with its result')
        s.check(len(rows) == len(result.get('steps') or []), 'the page shows every step the host reported', rows)
        s.check(not d.key_in_page(), 'the server key is not in the page after the test')
        s.shots.append(d.shot('model-tested'))
        d.open_chat()
        status = d.status()
        s.fact('status_after_test', status)
        s.check(status.get('state') == 'Ready', 'status light is Ready after a passed test', status)
        s.shots.append(d.shot('status-ready'))


def step_fast_send(d: Driver, name: str = 'fast-send', prompt: str = PROMPT_FAST) -> None:
    with d.step(name) as s:
        before = read_messages(d.profile)
        turn = d.start_turn(s, prompt, 'fast')
        d.pump(1.5)
        waiting = d.js("__acc.text('.thread-status')") or ''
        s.fact('status_line_while_waiting', waiting)
        if not (d.js('__acc.stream.firstAt') or 0):
            s.check(bool(waiting) and '_' not in waiting, 'a plain status line with a clock shows while waiting for the first words', waiting)
            s.shots.append(d.shot(f'{name}-waiting'))
        d.wait_for('__acc.stream.firstAt', d.options.turn_timeout, 'the first streamed text', poll=0.03)
        s.shots.append(d.shot(f'{name}-streaming'))
        d.wait_idle(d.options.turn_timeout)
        facts = d.stream_metrics(turn)
        s.facts.update(facts)
        events = d.events[turn['mark']:]
        # The app's own warm-up can end during the turn; its result has no answer and is not this turn's.
        result = next((e for e in events if e.get('kind') == 'result' and 'answer' in (e.get('data') or {})), None)
        answer = ((result or {}).get('data') or {}).get('answer', '')
        s.fact('answer', answer[:400])
        s.fact('activity', [e.get('phase') for e in events if e.get('phase') and not e.get('delta_chars')])
        s.check(facts.get('bridge_delta_events', 0) >= 1, 'token deltas arrived over the bridge', facts)
        s.check(facts.get('visible_updates', 0) >= 1, 'the streamed text was visible in the page before the end', facts)
        s.check(bool(answer.strip()), 'the worker returned an answer')
        shown = d.transcript()
        last = shown[-1] if shown else {}
        s.check(last.get('role') == 'assistant' and bool(last.get('text')),
                'the final answer is rendered as the last message', last)
        s.fact('rendered', last.get('text', '')[:400])
        s.check(not d.busy() and bool(d.js("!!document.querySelector('.cmp-send:not(.is-stop)')")),
                'the composer is back to Send')
        rows = read_messages(d.profile)
        new = rows[len(before):]
        s.fact('db_new_rows', [{k: (v if k != 'body' else v[:120]) for k, v in row.items()} for row in new])
        s.check([r['role'] for r in new] == ['user', 'assistant'], 'SQLite has the user message and the answer', [r['role'] for r in new])
        s.check(bool(new) and new[0]['body'] == prompt, 'the stored user message is the prompt')
        s.check(len(new) == 2 and new[1]['body'] == answer and new[1]['status'] == 'complete',
                'the stored answer equals the answer shown')
        status = d.status()
        s.fact('status', status)
        s.check(status.get('state') == 'Connected', 'status light says Connected after a real answer', status)
        s.shots.append(d.shot(f'{name}-done'))


def measure_typing(d: Driver, text: str) -> dict:
    """Type into the composer with real key events and measure how long each one takes to reach the page."""
    d.js("(__acc.keys.length = 0, __acc.frames.gaps.length = 0, __acc.frames.on = true,"
         " __acc.lag.n = 0, __acc.lag.max = 0, __acc.lag.over100 = 0, __acc.lag.on = true)")
    d.click('#star-prompt')
    d.select_all_and_type('')
    d.js('(__acc.keys.length = 0, true)')
    sent = []
    proxy = d.view.focusProxy()
    for char in text:
        sent.append(time.time() * 1000)
        d.QTest.keyClicks(proxy, char)
        d.pump(0.12)
    d.pump(0.3)
    page = d.js('({keys: __acc.keys, gaps: __acc.frames.gaps, lag: __acc.lag})') or {}
    d.js('(__acc.frames.on = false, __acc.lag.on = false, true)')
    keys = [k for k in page.get('keys', []) if len(k.get('key', '')) == 1]
    delivery = [k['down'] - at for k, at in zip(keys, sent)]
    painted = [k['painted'] - at for k, at in zip(keys, sent) if k.get('painted')]
    gaps = page.get('gaps', [])
    return {'chars_sent': len(text), 'chars_seen_by_page': len(keys),
            'value': d.js("document.querySelector('#star-prompt').value"),
            'key_to_page_ms': summarize(delivery), 'key_to_painted_ms': summarize(painted),
            'frame_gap_ms': summarize(gaps), 'frames': len(gaps),
            'frames_over_50ms': sum(1 for g in gaps if g > 50),
            'timer_lag': {k: round(v, 1) if isinstance(v, float) else v for k, v in (page.get('lag') or {}).items() if k != 'on'}}


def step_stop(d: Driver) -> None:
    with d.step('stop') as s:
        before = read_messages(d.profile)
        idle = measure_typing(d, TYPED_WHILE_STREAMING)
        s.fact('typing_idle', idle)
        turn = d.start_turn(s, PROMPT_LONG, 'fast')
        d.wait_for('__acc.stream.firstAt', d.options.turn_timeout, 'the first streamed text', poll=0.03)
        d.wait_for('__acc.stream.samples.length >= 8', 120, 'a few streamed updates', poll=0.1)
        typing = measure_typing(d, TYPED_WHILE_STREAMING)
        s.fact('typing_while_streaming', typing)
        s.check(typing['value'] == TYPED_WHILE_STREAMING, 'the composer accepts typing while a reply streams', typing['value'])
        s.check(typing['key_to_painted_ms'].get('p95', 9999) < 250,
                'typed characters reach the screen within 250 ms (p95) while streaming', typing['key_to_painted_ms'])
        s.check(d.busy(), 'the reply is still streaming')
        s.shots.append(d.shot('stop-streaming'))
        partial = (d.js('__acc.stream.samples.length') or 0, d.js('(__acc.stream.samples.slice(-1)[0]||[0,0])[1]') or 0)
        s.fact('visible_before_stop', {'updates': partial[0], 'chars': partial[1]})
        stopped_at = time.time()
        d.click('.cmp-send.is-stop')
        d.wait_for("!!document.querySelector('.msg-note.is-cancelled')", 60, 'the stopped row', poll=0.05)
        s.fact('stop_click_to_row_ms', round((time.time() - stopped_at) * 1000))
        d.wait_idle(30)
        s.facts.update({'stream_' + k: v for k, v in d.stream_metrics(turn).items()})
        shown = d.transcript()
        last = shown[-1] if shown else {}
        s.fact('row', last)
        s.check(last.get('status') == 'cancelled' and last.get('text', '').startswith('Request stopped'),
                'the page shows the turn as stopped', last)
        s.check('Retry' in last.get('buttons', []) and 'Edit message' in last.get('buttons', []),
                'the stopped row offers Retry and Edit message', last.get('buttons'))
        s.check(len(shown) >= 2 and shown[-2]['role'] == 'user' and shown[-2]['text'] == PROMPT_LONG,
                'the stopped row follows the question directly; the unsaved draft is not left as an answer')
        rows = read_messages(d.profile)
        new = rows[len(before):]
        s.fact('db_new_rows', [{k: (v if k != 'body' else v[:120]) for k, v in row.items()} for row in new])
        s.check([r['role'] for r in new] == ['user', 'event'], 'SQLite has the user message and one terminal record',
                [r['role'] for r in new])
        s.check(len(new) == 2 and new[1]['status'] == 'cancelled' and new[1]['reply_to'] == new[0]['id'],
                'the terminal record is cancelled and answers that user message')
        s.check(len(new) == 2 and new[1]['body'] == last.get('text'), 'the stored text equals the text shown')
        s.check(not d.busy() and bool(d.js("!!document.querySelector('.cmp-send:not(.is-stop)')")),
                'the composer is back to Send')
        d.click('#star-prompt')
        d.select_all_and_type('still usable')
        s.check(d.js("document.querySelector('#star-prompt').value") == 'still usable' and
                d.js("document.querySelector('.cmp-send').disabled") is False,
                'the composer takes text and Send is enabled again')
        d.select_all_and_type('')
        status = d.status()
        s.fact('status', status)
        s.check(status.get('state') in ('Connected', 'Ready'), 'stopping does not mark the server as failing', status)
        s.shots.append(d.shot('stop-cancelled'))


def set_server_address(d: Driver, s: Step, address: str) -> None:
    """Change the STAR Server address the way a person does: Settings, type, Save settings."""
    d.open_page('Settings', 'Settings')
    if d.js("!!document.querySelector('.toast')"):
        d.click('.toast button')  # an older notice must not be mistaken for this save
    field = '[aria-label="STAR Server settings"] input[inputmode="url"]'
    d.click(field)
    d.select_all_and_type(address)
    s.check(d.js(f"document.querySelector('{field}').value") == address, 'the address field holds the typed address')
    d.click('.save-button')
    d.wait_for("(__acc.text('.toast')||'').includes('Settings saved')", 15, 'the "Settings saved" notice')
    s.check(d.settings_file()['server_endpoint'] == address, 'settings.json holds the new address')
    d.pump(0.5)


def step_failure(d: Driver) -> None:
    with d.step('failure') as s:
        dead = d.options.dead_endpoint
        set_server_address(d, s, dead)
        s.shots.append(d.shot('failure-settings'))
        d.open_chat()
        status = d.status()
        s.fact('status_after_address_change', status)
        s.check(status.get('state') not in ('Connected', 'Ready'),
                'status does not claim the new, unchecked address is connected', status)
        before = read_messages(d.profile)
        turn = d.start_turn(s, PROMPT_FAIL, 'fast')
        d.wait_for("!!document.querySelector('.msg-note.is-failed')", 90, 'the failure row', poll=0.05)
        s.fact('send_to_error_row_ms', round((time.time() - turn['sent_at']) * 1000))
        d.wait_idle(30)
        shown = d.transcript()
        last = shown[-1] if shown else {}
        s.fact('row', last)
        s.check(last.get('status') == 'failed', 'the page shows a failed turn', last)
        s.check(last.get('title') == "Can't reach the model", 'the row has a calm title', last.get('title'))
        s.check(last.get('text', '').startswith('Cannot reach STAR Server'), 'the message names STAR Server, not a local brain', last.get('text'))
        raw = json.dumps(last)
        s.check(not any(word in raw for word in ('Traceback', 'APIConnectionError', 'httpx', 'Errno', 'Brain tab')),
                'no exception names or local-brain advice in the row', raw)
        s.check(last.get('buttons') == ['Model & connection', 'Retry', 'Edit message'], 'the row offers Model & connection, Retry and Edit message', last.get('buttons'))
        rows = read_messages(d.profile)
        new = rows[len(before):]
        s.fact('db_new_rows', [{k: (v if k != 'body' else v[:160]) for k, v in row.items()} for row in new])
        s.check([r['role'] for r in new] == ['user', 'event'] and new[1]['status'] == 'failed' and new[1]['reply_to'] == new[0]['id'],
                'SQLite has the failed terminal record for that message')
        s.check(len(new) == 2 and new[1]['body'] == last.get('text'), 'the stored text equals the text shown')
        status = d.status()
        s.fact('status_after_failure', status)
        s.check(status.get('state') == 'Not reachable', 'status light says Not reachable', status)
        s.shots.append(d.shot('failure'))
        d.click('.msg-note.is-failed .note-button', 'Retry')
        d.wait_for("document.querySelectorAll('.msg-note.is-failed').length >= 2", 90, 'the second failure row', poll=0.05)
        d.wait_idle(30)
        shown = d.transcript()
        failed = [t for t in shown if t['status'] == 'failed']
        s.check(len(failed) == 2 and failed[0]['buttons'] == [] and 'Retry' in failed[1]['buttons'],
                'Retry sent the message again; only the newest failed row keeps its buttons', [f['buttons'] for f in failed])
        rows = read_messages(d.profile)
        retried = rows[len(before) + 2:]
        s.check([r['role'] for r in retried] == ['user', 'event'] and retried[0]['body'] == PROMPT_FAIL,
                'the retried turn is stored as a new message with its own failed record', [r['role'] for r in retried])
        s.shots.append(d.shot('failure-retry'))
        d.click('.msg-note.is-failed .note-button', 'Model & connection')
        d.wait_for("(__acc.text('.page-stage .page-intro h1')||'').startsWith('Model')", 15, 'the Model page')
        card = d.js("__acc.text('section[aria-label=\"STAR Server\"]')") or ''
        s.fact('model_card_after_failure', card)
        s.check('needs attention' in card, 'the Model page says the server needs attention', card)
        s.shots.append(d.shot('failure-model'))
        d.open_chat()


def compare_history(d: Driver, s: Step) -> list[dict]:
    """The transcript the page shows must be the rows SQLite holds for the active chat, in order."""
    shown = d.transcript()
    rows = read_messages(d.profile)
    stored = [{'role': r['role'], 'status': r['status'], 'text': r['body']} for r in rows]
    s.fact('shown', [{'role': t['role'], 'status': t['status'], 'text': t['text'][:90], 'buttons': t['buttons']} for t in shown])
    s.check(len(shown) == len(stored), 'the page shows as many rows as SQLite holds', f'{len(shown)} shown, {len(stored)} stored')
    same = all(a['role'] == b['role'] and a['status'] == b['status'] and
               (a['role'] == 'assistant' or ' '.join(a['text'].split()) == ' '.join(b['text'].split()))
               for a, b in zip(shown, stored))
    s.check(same, 'roles, outcomes and texts match the database, in order')
    return shown


def step_restart_history(d: Driver) -> None:
    with d.step('restart-history') as s:
        shown = compare_history(d, s)
        s.check(sum(1 for t in shown if t['status'] == 'cancelled') == 1, 'the stopped turn is still shown as stopped')
        failed = [t for t in shown if t['status'] == 'failed']
        s.check(len(failed) == 2, 'both failed turns are still shown', len(failed))
        last = shown[-1] if shown else {}
        s.check(last.get('status') == 'failed' and last.get('buttons') == ['Model & connection', 'Retry', 'Edit message'],
                'the newest failed row still offers Model & connection, Retry and Edit message', last.get('buttons'))
        s.check(all(t['buttons'] == [] for t in shown[:-1] if t['role'] == 'event'), 'older rows are history without buttons')
        s.check(any(t['role'] == 'assistant' and t['text'] for t in shown), 'the earlier answer is still there')
        s.fact('status', d.status())
        s.shots.append(d.shot('restart'))


def step_restart_retry(d: Driver) -> None:
    with d.step('restart-retry') as s:
        set_server_address(d, s, os.environ[ENV_SERVER])
        d.open_chat()
        before = read_messages(d.profile)
        d.js('__acc.resetStream()')
        mark = len(d.events)
        sent_at = time.time()
        d.click('.msg-note.is-failed .note-button', 'Retry')
        turn = {'sent_at': sent_at, 'mark': mark}
        d.wait_for('__acc.stream.firstAt', d.options.turn_timeout, 'the first streamed text', poll=0.03)
        d.wait_idle(d.options.turn_timeout)
        s.facts.update(d.stream_metrics(turn))
        new = read_messages(d.profile)[len(before):]
        s.check([r['role'] for r in new] == ['user', 'assistant'] and new[0]['body'] == PROMPT_FAIL,
                'Retry after a restart re-sent the stored prompt and the answer was saved', [r['role'] for r in new])
        shown = d.transcript()
        s.check(bool(shown) and shown[-1]['role'] == 'assistant' and bool(shown[-1]['text']), 'the answer is rendered')
        s.check(all(t['buttons'] == [] for t in shown if t['role'] == 'event'), 'no stale Retry buttons remain')
        s.fact('answer', shown[-1]['text'][:300] if shown else '')
        s.shots.append(d.shot('restart-retry'))


def step_agent(d: Driver) -> None:
    with d.step('agent') as s:
        before = read_messages(d.profile)
        d.click('.rail-new')
        d.wait_for("!!document.querySelector('.thread-hello')", 15, 'a new empty chat')
        turn = d.start_turn(s, PROMPT_AGENT, 'agent')
        d.wait_for("!!document.querySelector('.act, .thread-status')", 30, 'the activity view', poll=0.1)
        d.pump(4)
        s.shots.append(d.shot('agent-running'))
        running = d.js("__acc.text('.act') || __acc.text('.thread-status')") or ''
        s.fact('view_while_running', running)
        seen_tool = False
        deadline = time.time() + d.options.agent_timeout
        while d.busy():
            if time.time() > deadline:
                raise TimeoutError(f'the agent turn did not end in {d.options.agent_timeout:.0f}s')
            if not seen_tool and any((e.get('activity') or {}).get('type') == 'tool' for e in d.events[turn['mark']:]):
                seen_tool = True
                s.shots.append(d.shot('agent-tool'))
            d.pump(0.5)
        d.pump(0.8)
        events = d.events[turn['mark']:]
        activity = [e['activity'] for e in events if e.get('activity')]
        s.fact('activity_events', activity)
        s.fact('phases', [e.get('phase') for e in events if e.get('phase') and not e.get('delta_chars')])
        ended = next((e for e in events if e.get('kind') in ('result', 'error')), {})
        s.fact('send_to_end_s', round(ended.get('t', time.time()) - turn['sent_at'], 1))
        s.fact('streamed_deltas', sum(1 for e in events if e.get('delta_chars')))
        s.check(ended.get('kind') == 'result', 'the agent turn ended with an answer', ended.get('text') or ended.get('kind'))
        tools = [a for a in activity if a.get('type') == 'tool']
        s.check(any(a.get('profile') == 'agent' for a in activity if a.get('type') == 'route'), 'the host chose the Agent route')
        s.check(any(a.get('state') == 'running' for a in tools) and any(a.get('state') == 'done' for a in tools),
                'a real tool call started and finished', tools)
        s.check(sum(1 for a in activity if a.get('type') == 'turn') >= 2, 'the model was called again after the tool result')
        timeline = "section[aria-label=\"What STAR did\"]"
        s.check(bool(d.js(f"!!document.querySelector('{timeline}')")), 'the activity timeline is shown for this turn')
        if d.js(f"!!document.querySelector('{timeline} .act-toggle[aria-expanded=\"false\"]')"):
            d.click(f'{timeline} .act-toggle')
            d.pump(0.6)
        rows = d.js(f"[...document.querySelectorAll('{timeline} .act-step')].map(r=>r.innerText.replace(/\\s+/g,' ').trim())") or []
        head = d.js(f"__acc.text('{timeline} .act-head')") or ''
        s.fact('timeline_head', head)
        s.fact('timeline_rows', rows)
        s.check(len(rows) >= 2, 'the timeline lists the steps the host reported', rows)
        s.check(any('Agent Skill' in row or 'tool' in row.lower() for row in rows), 'the tool step is in the timeline', rows)
        new = read_messages(d.profile)[len(before):]
        s.check([r['role'] for r in new] == ['user', 'assistant'], 'SQLite has the agent turn and its answer', [r['role'] for r in new])
        s.fact('answer', new[1]['body'][:400] if len(new) == 2 else '')
        s.shots.append(d.shot('agent-done'))


def step_pages(d: Driver) -> None:
    for name, heading in PAGES:
        slug = name.lower()
        with d.step(f'page-{slug}') as s:
            errors_before = len(d.console)
            d.open_page(name, heading)
            d.pump(1.0)
            text = d.js("__acc.text('.page-stage')") or ''
            s.fact('text', text[:6000])
            s.check(len(text) > 120, f'the {name} page has content', len(text))
            overflow = d.js(OVERFLOW_JS.strip()) or {}
            s.fact('overflow', overflow)
            s.check(overflow.get('scrollWidth', 0) <= overflow.get('innerWidth', 0) + 1 and not overflow.get('outside'),
                    'nothing is wider than the window', overflow)
            fresh = [c for c in d.console[errors_before:] if 'Error' in c['level']]
            s.check(not fresh, 'no console errors on this page', fresh[:3])
            s.shots.append(d.shot(f'page-{slug}'))
            height = d.js("(()=>{const r=document.querySelector('.page-stage .scroll-region');return r?[r.scrollHeight,r.clientHeight]:[0,0]})()") or [0, 0]
            part = 2
            while height[0] > height[1] * (part - 1) + 40 and part <= 6:
                d.js(f"(document.querySelector('.page-stage .scroll-region').scrollTop = {int(height[1] * (part - 1) * 0.92)}, true)")
                s.shots.append(d.shot(f'page-{slug}-{part}'))
                part += 1
            if name == 'Tools':
                layout = d.js("({grid: getComputedStyle(document.querySelector('.intelligence-grid')).display,"
                              " head: getComputedStyle(document.querySelector('.integration-head')).display,"
                              " columns: getComputedStyle(document.querySelector('.intelligence-grid')).gridTemplateColumns.split(' ').length})") or {}
                s.fact('knowledge_cards', layout)
                s.check(layout.get('grid') == 'grid' and layout.get('columns', 0) >= 2 and layout.get('head') == 'flex',
                        'the knowledge cards are laid out as a grid, with the status tag beside the icon', layout)
                s.check('VRAM' not in text and 'Local specialist' not in text,
                        'no "this PC" hardware wording while STAR Server is selected')
                s.check('Protocol: \u00b7' not in text, 'a connector that is off says so, without an empty protocol')
            if name == 'Analytics':
                numbers = d.js("[...document.querySelectorAll('.metric-card')].map(c=>c.innerText.replace(/\\s+/g,' ').trim())") or []
                s.fact('metrics', numbers)
                users = sum(1 for r in read_messages(d.profile) if r['role'] == 'user')
                s.check(any(card.startswith('Messages') and f' {users} ' in f' {card} ' for card in numbers),
                        'Messages equals the user messages in SQLite', f'{users} stored; {numbers}')
    with d.step('settings-live') as s:
        d.open_page('Settings', 'Settings')
        heading = d.js("__acc.text('.settings-page .settings-section h2')") or ''
        s.check(heading == 'STAR Server model', 'Settings names the model section for STAR Server', heading)
        s.check(not d.js("!!__acc.find('.settings-page label', 'Local endpoint')"), 'no "Local endpoint" field while STAR Server is selected')
        mark = len(d.events)
        d.click('.settings-page button', 'List available models')
        d.wait_for("!!__acc.find('.settings-page small', 'Available:')", 60, 'the model list')
        listed = d.js("__acc.find('.settings-page small', 'Available:').innerText") or ''
        s.fact('models', listed)
        s.check(d.settings_file()['model'] in listed, 'List available models shows the server models', listed)
        began = time.time()
        d.click('.settings-page button', 'Test actual response')
        d.wait_for("!!document.querySelector('.settings-page .health-result')", d.options.turn_timeout, 'the live response', poll=0.25)
        s.fact('test_actual_response_s', round(time.time() - began, 1))
        s.fact('live_response', d.js("__acc.text('.settings-page .health-result')"))
        s.check(any(e.get('kind') == 'result' for e in d.events[mark:]), 'Test actual response returned a real reply')
        notice = d.js("__acc.text('.toast')") or ''
        s.fact('notice', notice)
        s.shots.append(d.shot('settings-live'))
        d.open_page('Model', 'Model & connection')
        card = d.js("__acc.text('section[aria-label=\"STAR Server\"]')") or ''
        s.check('Status: ready' in card, 'the Model page knows the test passed', card)
        d.open_chat()
        s.check(not d.js("!!document.querySelector('.toast')"), 'the notice from Settings does not follow into the chat')
        s.shots.append(d.shot('settings-live-chat'))
    with d.step('small-window') as s:
        d.shell.resize(920, 650)
        d.pump(1.0)
        s.fact('window', d.js('({w: innerWidth, h: innerHeight})'))
        for name, heading in (('Settings', 'Settings'), ('Model', 'Model & connection')):
            d.open_page(name, heading)
            overflow = d.js(OVERFLOW_JS.strip()) or {}
            s.check(overflow.get('scrollWidth', 0) <= overflow.get('innerWidth', 0) + 1 and not overflow.get('outside'),
                    f'{name}: nothing is wider than the 920 px window', overflow)
            s.shots.append(d.shot(f'small-{name.lower()}'))
        d.open_chat()
        overflow = d.js(OVERFLOW_JS.strip()) or {}
        s.check(overflow.get('scrollWidth', 0) <= overflow.get('innerWidth', 0) + 1 and not overflow.get('outside'),
                'Chat: nothing is wider than the 920 px window', overflow)
        s.shots.append(d.shot('small-chat'))
        d.shell.resize(1440, 900)
        d.pump(0.8)
    with d.step('sidebar-preference') as s:
        d.click('.rail-icon[aria-label="Hide sidebar"]')
        d.pump(0.5)
        s.check(bool(d.js("!!document.querySelector('.shell.shell-sidebar-collapsed')")), 'Hide sidebar collapses the sidebar')
        s.fact('note', 'the next phase checks whether the collapsed sidebar survives a restart')
        s.shots.append(d.shot('sidebar-collapsed'))


def step_wrong_key(d: Driver) -> None:
    with d.step('sidebar-after-restart') as s:
        collapsed = bool(d.js("!!document.querySelector('.shell.shell-sidebar-collapsed')"))
        s.fact('collapsed_after_restart', collapsed)
        s.check(collapsed, 'the collapsed sidebar survives a restart (the code says it does)',
                known='the shell uses an off-the-record WebEngine profile, so localStorage is empty on every start')
        if collapsed:
            d.click('.bar-reveal[aria-label="Show sidebar"]')
            d.pump(0.5)
    with d.step('wrong-key-test') as s:
        d.open_page('Model', 'Model & connection')
        card = "section[aria-label=\"STAR Server\"]"
        mark = len(d.events)
        d.click(f'{card} button', 'Test server')
        d.wait_for(f"!!document.querySelector('{card} [role=\"status\"]')", 120, 'the server report', poll=0.25)
        d.pump(0.6)
        text = d.js(f"__acc.text('{card} [role=\"status\"]')") or ''
        s.fact('report_text', text)
        result = next((e.get('data') for e in d.events[mark:] if e.get('kind') == 'result' and isinstance(e.get('data'), dict)), {}) or {}
        s.check(result.get('code') == 'wrong_key', 'the host reports a refused key', result.get('code'))
        s.check('refused the API key (401)' in text, 'the page explains that the server refused the key', text)
        s.check(WRONG_KEY not in (d.js('document.documentElement.outerHTML') or ''), 'the key that was tried is not shown')
        s.shots.append(d.shot('wrongkey-test'))
        d.open_chat()
        status = d.status()
        s.fact('status', status)
        s.check(status.get('state') == 'Needs attention', 'status light says Needs attention', status)
    with d.step('wrong-key-send') as s:
        before = read_messages(d.profile)
        d.click('.rail-new')
        d.wait_for("!!document.querySelector('.thread-hello')", 15, 'a new empty chat')
        d.start_turn(s, PROMPT_FAIL, 'fast')
        d.wait_for("!!document.querySelector('.msg-note.is-failed')", 120, 'the failure row', poll=0.05)
        d.wait_idle(30)
        shown = d.transcript()
        last = shown[-1] if shown else {}
        s.fact('row', last)
        s.check(last.get('title') == 'The key or access was refused', 'the row has a calm title', last.get('title'))
        s.check('refused the API key (401)' in last.get('text', ''), 'the message says the key was refused', last.get('text'))
        s.check(last.get('buttons') == ['Model & connection', 'Retry', 'Edit message'], 'the row offers the three actions', last.get('buttons'))
        new = read_messages(d.profile)[len(before):]
        s.check([r['role'] for r in new] == ['user', 'event'] and new[1]['status'] == 'failed', 'SQLite has the failed record')
        status = d.status()
        s.fact('status_after', status)
        s.check(status.get('state') == 'Access refused', 'status light says Access refused', status)
        s.shots.append(d.shot('wrongkey-send'))


def step_close_midstream(d: Driver) -> None:
    with d.step('close-midstream') as s:
        d.click('.rail-new')
        d.wait_for("!!document.querySelector('.thread-hello')", 15, 'a new empty chat')
        d.start_turn(s, PROMPT_LONG, 'fast')
        d.wait_for('__acc.stream.firstAt', d.options.turn_timeout, 'the first streamed text', poll=0.03)
        d.wait_for('__acc.stream.samples.length >= 5', 120, 'a few streamed updates', poll=0.1)
        s.shots.append(d.shot('midclose-streaming'))
        s.fact('note', 'the window is closed right after this step while the reply is still streaming')
        s.check(d.busy(), 'a reply is streaming when the window is closed')


def step_after_close(d: Driver) -> None:
    with d.step('after-close') as s:
        rows = read_messages(d.profile)
        tail = rows[-2:]
        s.fact('db_tail', [{k: (v if k != 'body' else v[:140]) for k, v in row.items()} for row in tail])
        s.check(len(tail) == 2 and tail[0]['role'] == 'user' and tail[0]['body'] == PROMPT_LONG,
                'the message sent before the window was closed is stored')
        s.check(len(tail) == 2 and tail[1]['role'] == 'event' and tail[1]['status'] == 'cancelled',
                'closing the window recorded the turn as stopped', tail[-1]['role'] + '/' + tail[-1]['status'])
        shown = d.transcript()
        last = shown[-1] if shown else {}
        s.fact('row', last)
        s.check(last.get('status') == 'cancelled' and 'Retry' in last.get('buttons', []),
                'after the relaunch the turn is shown as stopped, with Retry', last)
        title = d.js("__acc.text('.bar-title h1')") or ''
        s.fact('title', title)
        s.check(len(PROMPT_LONG) > 64 and title.endswith('\u2026') and PROMPT_LONG.startswith(title[:-1]),
                'a long first message gives a chat title that ends with an ellipsis', title)
        s.shots.append(d.shot('afterclose'))


def step_upgrade(d: Driver) -> None:
    with d.step('upgrade-history') as s:
        shown = d.transcript()
        s.fact('shown', [{'role': t['role'], 'text': t['text'][:80]} for t in shown])
        s.check([(t['role'], ' '.join(t['text'].split())) for t in shown] ==
                [(role, ' '.join(body.split())) for role, body in RELEASED_MESSAGES],
                'every message of the old conversation is shown, in order')
        chats = d.js("[...document.querySelectorAll('.rail-chats .rail-chat')].map(b => b.innerText.trim())") or []
        s.check(chats == ['Previous conversation'], 'the old conversation is listed as "Previous conversation"', chats)
        rows = read_messages(d.profile)
        s.check([(r['id'], r['role'], r['body'], r['created']) for r in rows] ==
                [(index + 1, role, body, f'2026-09-0{index + 1}T10:00:00+00:00') for index, (role, body) in enumerate(RELEASED_MESSAGES)],
                'the stored rows are byte-for-byte what the old app wrote')
        s.check(all(r['chat_id'] == 'legacy' and r['status'] == 'complete' and r['reply_to'] is None for r in rows),
                'the new columns were added with neutral values')
        settings = d.settings_file()
        s.check(settings.get('model') == 'released-local-model' and 'provider' not in settings,
                'opening the app did not rewrite settings.json', sorted(settings)[:6])
        s.shots.append(d.shot('upgrade'))
    with d.step('upgrade-model-page') as s:
        d.open_page('Model', 'Model & connection')
        text = d.js("__acc.text('.page-stage')") or ''
        s.fact('text', text)
        s.check('This PC' in text and 'released-local-model' in text, 'the Model page shows the on-device provider and the saved model')
        s.check('STAR Server' not in text.replace('Connection settings', ''), 'nothing on the page claims a STAR Server is in use', text[:300])
        s.check('Model on this PC' in text, 'the on-device model card is shown, not folded away')
        s.shots.append(d.shot('upgrade-model'))
        d.open_page('Settings', 'Settings')
        heading = d.js("__acc.text('.settings-page .settings-section h2')") or ''
        s.check(heading == 'Local model', 'Settings names the model section for the model on this PC', heading)
        s.check(d.js("document.querySelector('.settings-page select').value") == 'local', 'the provider menu shows the on-device provider')
        s.shots.append(d.shot('upgrade-settings'))
        d.open_chat()
    with d.step('upgrade-send') as s:
        before = read_messages(d.profile)
        d.start_turn(s, PROMPT_FAIL, 'fast')
        d.wait_for("!!document.querySelector('.msg-note.is-failed')", 120, 'the failure row', poll=0.05)
        d.wait_idle(30)
        last = (d.transcript() or [{}])[-1]
        s.fact('row', last)
        s.check(last.get('status') == 'failed' and last.get('title') == "Can't reach the model", 'the engine not running is a calm failure row', last)
        s.check('STAR Server' not in last.get('text', ''), 'the message does not mention a server the owner never set up', last.get('text'))
        s.check('Brain tab' not in last.get('text', ''), 'the message does not point at a page that no longer exists',
                last.get('text'), known='local-provider messages still say "Start it in the Brain tab"; the page is now "Model & connection"')
        new = read_messages(d.profile)[len(before):]
        s.check([r['role'] for r in new] == ['user', 'event'] and new[1]['status'] == 'failed' and new[0]['chat_id'] == 'legacy',
                'the new turn and its failed record went into the same old conversation')
        s.check(read_messages(d.profile)[:len(before)] == before, 'the old rows are still unchanged after a new turn')
        s.shots.append(d.shot('upgrade-send'))


def step_close_during_test(d: Driver) -> None:
    with d.step('close-during-test') as s:
        d.open_page('Settings', 'Settings')
        d.click('.settings-page button', 'Test actual response')
        d.pump(0.4)
        waiting = bool(d.js("!!__acc.find('.settings-page button .spin')")) or bool(d.js(
            "(__acc.find('.settings-page button', 'Test actual response') || {}).disabled"))
        s.check(waiting, 'a model test is waiting for the server when the window is closed')
        s.fact('note', 'the window is closed right after this step; errors-and-exit reports how long the process lived on')
        s.shots.append(d.shot('testclose'))


def run_phase(d: Driver) -> None:
    phase = d.phase
    step_boot(d, expect_history=bool(read_messages(d.profile)) if phase in ('media', 'settings', 'followup')
              else phase != 'first')
    if phase == 'first':
        step_model_page(d)
        step_fast_send(d)
        step_stop(d)
        step_failure(d)
    elif phase == 'restart':
        step_restart_history(d)
        step_restart_retry(d)
    elif phase == 'agent':
        step_agent(d)
    elif phase == 'pages':
        step_pages(d)
    elif phase == 'wrongkey':
        step_wrong_key(d)
    elif phase == 'midclose':
        step_close_midstream(d)
    elif phase == 'afterclose':
        step_after_close(d)
    elif phase == 'upgrade':
        step_upgrade(d)
    elif phase == 'testclose':
        step_close_during_test(d)
    elif phase == 'media':
        step_media(d)
    elif phase == 'settings':
        step_settings(d)
    elif phase == 'followup':
        step_followup(d)


def step_media(d: Driver) -> None:
    """Where STAR generates, and one real picture from the chat (ComfyUI on this PC, 127.0.0.1)."""
    section = 'section[aria-label="Where STAR generates"]'
    ready = False
    with d.step('media-settings') as s:
        d.open_page('Settings', 'Settings')
        d.wait_for(f"!!document.querySelector({json.dumps(section)})", 15, 'the "Where STAR generates" section')
        # The choices and notes come from the host (mediaStatus), which also asks ComfyUI for its state.
        d.wait_for(f"(__acc.text({json.dumps(section)})||'').includes('Image engine on this PC')", 40,
                   'the media status from the host')
        d.pump(0.5)
        text = d.js(f"__acc.text({json.dumps(section)})") or ''
        s.fact('text', text[:5000])
        s.check(all(title in text for title in ('Images', 'Voice', 'Video understanding')), 'three capabilities are listed')
        s.check(text.count('STAR Brains (servers)') >= 3 and text.count('This PC (your GPU)') >= 3,
                'each capability offers the servers and this PC')
        s.check('Measured on this PC' in text, 'the note for images on this PC is a measurement')
        s.check('(unavailable)' in text and 'no graphics card' in text,
                'the server option for images is shown as unavailable, with the reason')
        blocked = d.js("(()=>{const r=[...document.querySelectorAll('input[name=\"media-images\"]')];"
                       "return r.length===2&&r[0].disabled&&!r[1].disabled&&r[1].checked})()")
        s.check(bool(blocked), 'the unavailable place cannot be chosen and This PC is selected for images')
        ready = 'Ready: FLUX.2 klein' in text
        s.fact('image_engine_ready', ready)
        s.check(ready or 'not running on this PC' in text or 'model files are missing' in text,
                'the state of the image engine is stated', text[-600:])
        s.check(not d.key_in_page(), 'the server key is not in the page')
        d.box(section)
        d.pump(0.4)
        s.shots.append(d.shot('media-settings'))
    with d.step('media-image') as s:
        d.open_chat()
        d.click('button[aria-label="Add files and tools"]')
        d.click('.cmp-menu [role^="menuitem"]', 'Create image')
        d.wait_for("!!document.querySelector('select.cmp-size')", 10, 'the image size control')
        s.check(not d.js("!!__acc.find('.cmp-link', 'Set up image creation')"),
                'no workflow file has to be set up first')
        d.click('#star-prompt')
        d.select_all_and_type(PROMPT_IMAGE)
        folder = d.profile / 'STAR' / 'generated-images'
        before = set(folder.glob('*.png')) if folder.is_dir() else set()
        mark = len(d.events)
        sent = time.time()
        d.press(d.Qt.Key.Key_Return)
        d.wait_for("!!document.querySelector('.cmp.is-busy')", 10, 'the image turn to start')
        d.wait_for("!document.querySelector('.cmp.is-busy')", 240, 'the image turn to finish')
        s.fact('seconds', round(time.time() - sent, 1))
        outcome = [e for e in d.events[mark:] if e.get('kind') in ('result', 'error')]
        s.fact('outcome', [{'kind': e.get('kind'), 'data': str(e.get('data'))[:300] if e.get('kind') == 'error'
                            else {k: (v if k != 'image' else f'<{len(str(v))} chars>')
                                  for k, v in (e.get('data') or {}).items()}} for e in outcome][-1:])
        made = sorted(set(folder.glob('*.png')) - before) if folder.is_dir() else []
        if ready:
            s.check(bool(d.js("!!document.querySelector('.generated-image-button img')")),
                    'the generated picture is shown in the conversation')
            s.check(len(made) == 1 and made[0].with_suffix('.json').is_file(),
                    'the original and its note are saved under the profile\'s STAR/generated-images', [p.name for p in made])
            page = d.js("__acc.text('[role=\"log\"]')") or ''
            s.check('on this PC' in page and 'FLUX.2 klein' in page, 'the answer says where and with what it was made',
                    page[-300:])
        else:
            page = d.js("__acc.text('[role=\"log\"]')") or ''
            s.check('ComfyUI' in page and ('not running on this PC' in page or 'model file' in page),
                    'the chat shows the host\'s plain explanation instead of a picture', page[-400:])
            s.check(not made, 'nothing was saved or shown as if it had worked')
        s.shots.append(d.shot('media-image'))
        if d.js("!!__acc.find('.composer-image-chip')"):
            d.click('.composer-image-chip')         # back to ordinary messages
    # Every chat message now passes through star/chat_media.prepare_turn: a plain one must be unchanged.
    step_fast_send(d, name='media-plain-chat')
    # A link is not a video: the answer must say it was not watched (the model's words are recorded).
    step_fast_send(d, name='media-video-link', prompt=PROMPT_VIDEO_LINK)
    with d.step('media-video-link-honesty') as s:
        rows = read_messages(d.profile)
        answer = next((row['body'] for row in reversed(rows) if row['role'] == 'assistant'), '')
        s.fact('answer', answer[:700])
        s.check(bool(NOT_WATCHED.search(answer)), 'STAR says it has not watched the linked video', answer[:300])
        s.check('Based on' not in answer or 'sampled frame' not in answer,
                'no "based on sampled frames" line is added when no video file was given')
    with d.step('media-references') as s:
        d.open_page('Projects', 'Your workspaces')
        panel = 'section[aria-label="Visual references"]'
        d.wait_for(f"!!document.querySelector({json.dumps(panel)})", 15, 'the visual references panel')
        d.pump(0.5)
        shown = d.js(f"__acc.text({json.dumps(panel)})") or ''
        s.fact('text', shown[:1200])
        s.check('Visual references for' in shown and 'Pin an image' in shown, 'the panel explains itself and offers Pin an image')
        s.check('No references yet for this project' in shown and '0 of 12 pinned' in shown,
                'a new project has no references and says so')
        d.box(panel)
        d.pump(0.4)
        s.shots.append(d.shot('media-references'))


class SilentSpeaker:
    """Stands in for the loudspeaker only: it takes the synthesised sound and plays nothing."""
    received: list[tuple[int, int]] = []        # (samples, sample rate) of every block the voice engine produced

    def __init__(self, sample_rate: int):
        self.sample_rate = sample_rate

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        return None

    def play(self, pcm: bytes, sample_rate: int) -> None:
        SilentSpeaker.received.append((len(pcm) // 2, int(sample_rate)))

    def pending_seconds(self) -> float:
        return 0.0


def silence_speaker(shell) -> bool:
    """Replace the loudspeaker of the app's voice bridge; True when that was possible."""
    voice = getattr(shell.bridge, 'voice', None)
    factories = getattr(voice, '_factories', None)
    if factories is None:
        return False

    # The bridge keeps its factories as a class of static methods (or an instance of one in tests).
    class Quiet(factories if isinstance(factories, type) else type(factories)):
        @staticmethod
        def speaker(sample_rate: int, _device):
            return SilentSpeaker(sample_rate)
    voice._factories = Quiet
    return True


def step_settings(d: Driver) -> None:
    """Settings > Voice and Settings > Roblox Studio against the real host."""
    voice = 'section[aria-label="Star\'s voice"]'
    studio = 'section[aria-label="Roblox Studio"]'
    commanding = voice + ' [role=group][aria-label="Confident and commanding"] .voice-row'
    warm_use = voice + ' [role=group][aria-label="Warm and caring"] button.is-primary'
    q = json.dumps

    def calls(action: str) -> list[dict]:
        return [c for c in (d.js('__acc.calls') or []) if c.get('action') == action]

    def wait_call(action: str, count: int, timeout: float = 20.0) -> dict:
        d.wait_for(f"__acc.calls.filter(c=>c.action==={q(action)}).length>={count}", timeout, f'the answer to {action}')
        return calls(action)[count - 1]

    def wait_event(mark: int, wanted, timeout: float, what: str) -> dict:
        deadline = time.time() + timeout
        while True:
            found = next((e for e in d.events[mark:] if wanted(e)), None)
            if found:
                return found
            if time.time() > deadline:
                raise TimeoutError(f'waited {timeout:.0f}s for {what}')
            d.pump(0.1)

    def studio_result(event: dict) -> bool:
        return event.get('kind') == 'error' or (event.get('kind') == 'result' and 'state' in (event.get('data') or {}))

    def stored_command():
        path = d.profile / 'STAR' / 'studio' / 'remote.json'
        return json.loads(path.read_text(encoding='utf-8')).get('command') if path.is_file() else None

    def page_text(selector: str) -> str:
        return (d.js(f"__acc.text({q(selector)})") or '').replace('\n', ' ')

    engine_ready = False
    with d.step('settings-sections') as s:
        d.open_page('Settings', 'Settings')
        d.wait_for(f"!!document.querySelector({q(voice)}) && !!document.querySelector({q(studio)})", 15,
                   'the Voice and Roblox Studio sections')
        d.wait_for(f"document.querySelectorAll({q(voice + ' .voice-row')}).length>0", 30, 'the voice list from the host')
        d.pump(0.5)
        s.check(bool(d.js('!!document.querySelector(\'section[aria-label="Where STAR generates"]\')')),
                'the where-to-generate choice is on the same Settings page')
        listing, status = wait_call('voiceListVoices', 1), wait_call('voiceStatus', 1)
        s.check(listing.get('ok') is True and status.get('ok') is True, 'the host answered voiceListVoices and voiceStatus',
                [listing, status])
        text = page_text(voice)
        s.fact('voice_text', text[:6000])
        groups = d.js("[...document.querySelectorAll(" + q(voice + ' [role=group]') + ")].map(g=>({name:g.getAttribute('aria-label'),"
                      "rows:g.querySelectorAll('.voice-row').length,"
                      "off:[...g.querySelectorAll('.voice-row')].filter(r=>r.textContent.includes('Not usable in live calls yet')).length,"
                      "more:(g.querySelector('details.voice-more > summary')||{textContent:''}).textContent,"
                      "open:!!(g.querySelector('details.voice-more')||{}).open,"
                      "tags:[...g.querySelectorAll('h3 .voice-tag')].map(t=>t.innerText)}))") or []
        s.fact('voice_groups', groups)
        from star.voice.catalog import load_catalog
        from star.voice.settings import TTS_ENGINES
        catalog: dict = {}
        for entry in load_catalog():
            catalog.setdefault(entry.style, []).append(entry)
        s.check([g['name'] for g in groups] == ['Warm and caring', 'Confident and commanding', 'Anime-style'],
                'the three styles are listed in the catalog order', [g.get('name') for g in groups])
        by = {g['name']: g for g in groups}
        s.check(by.get('Warm and caring', {}).get('rows') == len(catalog.get('warm-caring', []))
                and by.get('Anime-style', {}).get('rows') == len(catalog.get('anime-bright', [])),
                'every warm and anime voice of the shipped catalog is listed', groups)
        s.check(by.get('Warm and caring', {}).get('tags') == ['Default'], 'the warm style is marked as the default', groups)
        s.check(by.get('Confident and commanding', {}).get('rows') == 0
                and by.get('Confident and commanding', {}).get('tags') == ['Optional']
                and d.js(f"document.querySelector({q(voice + ' .voice-opt-in input')}).checked") is False,
                'the commanding voices are not listed until their switch is on, and the switch starts off', groups)
        uncallable = sum(1 for style in ('warm-caring', 'anime-bright') for e in catalog.get(style, []) if e.engine not in TTS_ENGINES)
        s.check(by.get('Warm and caring', {}).get('off', 0) + by.get('Anime-style', {}).get('off', 0) == uncallable and uncallable > 0,
                'voices whose engine is not in calls are labelled as not usable in live calls', [groups, uncallable])
        s.check(all(not g.get('open') for g in groups) and str(by.get('Warm and caring', {}).get('off')) in by.get('Warm and caring', {}).get('more', ''),
                'those voices sit under their own closed heading, which says how many there are', groups)
        s.check('Current voice: Heart' in text, 'the saved voice of a new profile is Heart', text[:300])
        engine_ready = 'voice engine is not installed' not in text
        s.fact('voice_engine_ready', engine_ready)
        if not engine_ready:
            s.check('Missing program parts' in text or 'Missing model files' in text,
                    'the page says what the voice engine is missing', text[:600])
        d.box(voice + ' .learn-head')
        d.pump(0.4)
        s.shots.append(d.shot('settings-voice'))
        shown = page_text(studio)
        s.fact('studio_text', shown[:3000])
        radios = d.js("[...document.querySelectorAll('input[name=\"studio-target\"]')].map(r=>r.checked)")
        s.check(radios == [True, False] and 'This PC' in shown and 'STAR Studio server' in shown,
                'Roblox Studio offers this PC and the STAR Studio server, with this PC chosen', radios)
        s.check('The sandbox rule.' in shown and 'STAR only builds in its own test place' in shown
                and 'Every other place is read-only' in shown, 'the sandbox rule is stated in the section')
        s.check('Not tested yet' in shown and not d.js(f"!!document.querySelector({q(studio + ' .media-field input')})"),
                'nothing is tested by itself and the server fields are hidden for this PC')
        s.check(not d.key_in_page(), 'the server key is not in the page')
        d.box(studio + ' .learn-head')
        d.pump(0.4)
        s.shots.append(d.shot('settings-studio'))
        s.fact('overflow', d.js(OVERFLOW_JS.strip()))

    with d.step('settings-voice-preview') as s:
        preview = voice + ' button[aria-label="Preview Heart"]'
        if not engine_ready:
            s.check(bool((d.box(preview) or {}).get('disabled')), 'Preview is switched off while the voice engine is missing')
            s.fact('preview_clicked', False)
        else:
            mark = len(d.events)
            started = time.time()
            d.click(preview)
            call = wait_call('voicePreviewVoice', 1)
            s.check(call.get('ok') is True, 'the host accepted the preview (voicePreviewVoice)', call)
            during = page_text(preview)
            ended = wait_event(mark, lambda e: e.get('kind') == 'voice' and e.get('voice') in ('preview_done', 'error'), 180,
                               'the end of the preview')
            s.fact('preview_seconds', round(time.time() - started, 2))
            s.fact('button_while_previewing', during)
            s.check(ended.get('voice') == 'preview_done', 'the voice engine spoke the sample line and reported it finished',
                    ended.get('text', ''))
            s.check('Playing' in during or time.time() - started < 1.0, 'the row showed Playing while the line was spoken', during)
            d.wait_for(f"(__acc.text({q(preview)})||'').includes('Preview')", 10, 'the Preview button to come back')
            s.check(not d.js(f"!!document.querySelector({q(voice + ' [role=alert]')})"), 'no failure is shown after a preview that worked')
            if getattr(d.options, 'audible', False):
                s.fact('audio', 'played through the real speakers')
            else:
                samples = sum(n for n, _rate in SilentSpeaker.received)
                rate = SilentSpeaker.received[0][1] if SilentSpeaker.received else 0
                s.fact('audio', {'sink': 'silent (the loudspeaker was replaced, nothing was played aloud)', 'samples': samples,
                                 'sample_rate': rate, 'seconds_of_speech': round(samples / rate, 2) if rate else 0})
                s.check(samples > 0, 'the voice engine produced sound for the sample line', samples)
            s.fact('preview_clicked', True)
            s.shots.append(d.shot('settings-voice-previewed'))

    with d.step('settings-voice-choice') as s:
        d.click(voice + ' .voice-opt-in input')
        d.wait_for(f"document.querySelectorAll({q(commanding)}).length>0", 10, 'the commanding voices after their switch')
        rows = d.js(f"document.querySelectorAll({q(commanding)}).length")
        from star.voice.catalog import load_catalog
        expected = sum(1 for e in load_catalog() if e.style == 'confident-commanding')
        s.check(rows == expected, 'switching the commanding style on lists all of its voices', [rows, expected])
        s.check(not calls('voiceSelectVoice') and 'Current voice: Heart' in page_text(voice),
                'showing the commanding voices chose nothing: the voice is still Heart')
        d.box(voice + ' .voice-opt-in')
        d.pump(0.4)
        s.shots.append(d.shot('settings-voice-commanding'))
        pick = d.js("(()=>{const b=[...document.querySelectorAll(" + q(warm_use) + ")].find(b=>!b.disabled);"
                    "return b?b.getAttribute('aria-label'):''})()") or ''
        s.fact('picked', pick)
        d.click(voice + f' button[aria-label={q(pick)}]')
        call = wait_call('voiceSelectVoice', 1)
        s.check(call.get('ok') is True, 'the host stored the choice (voiceSelectVoice)', call)
        name = pick.removeprefix('Use ')
        d.wait_for(f"(__acc.text({q(voice)})||'').includes({q(name + ' is now')})", 10, 'the confirmation of the choice')
        text = page_text(voice)
        s.check(f'Current voice: {name}' in text, 'the page marks the new voice only after the host confirmed it', text[:300])
        saved_file = d.profile / 'STAR' / 'voice.json'
        saved = json.loads(saved_file.read_text(encoding='utf-8')) if saved_file.is_file() else {}
        s.fact('voice_json', {k: saved.get(k) for k in ('voice_id', 'voice', 'voice_style', 'speed')})
        s.check(bool(saved.get('voice_id')) and saved.get('voice_style') == 'warm-caring',
                'voice.json in the profile holds the chosen voice and its style', saved.get('voice_id'))
        d.box(voice + ' .voice-current')
        d.pump(0.4)
        s.shots.append(d.shot('settings-voice-chosen'))
        more = voice + ' [role=group][aria-label="Warm and caring"] details.voice-more'
        d.click(more + ' > summary')
        d.pump(0.4)
        hidden = d.js("(()=>{const r=document.querySelector(" + q(more + ' .voice-row') + ");const b=r&&[...r.querySelectorAll('button')];"
                      "return r?{text:r.innerText,disabled:b.every(x=>x.disabled)}:null})()") or {}
        s.check('Not usable in live calls yet' in hidden.get('text', '') and 'engine is not built into calls yet' in hidden.get('text', '')
                and hidden.get('disabled') is True,
                "an opened voice of that kind carries the label, the host's reason, and cannot be played or chosen", hidden)
        s.shots.append(d.shot('settings-voice-not-in-calls'))

    with d.step('settings-studio-server') as s:
        status = studio + ' .media-engine-state[role=status]'
        before = len(calls('saveSettings'))
        d.click(studio + ' .media-option', 'STAR Studio server')
        saved = wait_call('saveSettings', before + 1)
        d.wait_for(f"!!document.querySelector({q(studio + ' .media-field input')})", 10, 'the server address and command fields')
        s.check(saved.get('ok') is True and d.settings_file().get('studio_target') == 'host_launcher',
                'choosing the STAR Studio server is saved by the host (settings.json)', d.settings_file().get('studio_target'))
        d.wait_for(f"(__acc.text({q(studio)})||'').includes('No server connection is stored yet.')", 10, 'the stored state')
        s.check(stored_command() is None, 'no server connection exists in a new profile')
        # 1. Nothing stored: the host answers "not configured" and starts nothing.
        mark = len(d.events)
        d.click(studio + ' button', 'Test connection')
        first = wait_call('discoverStudio', 1)
        answer = wait_event(mark, studio_result, 30, 'the first test result')
        s.fact('test_without_connection', answer.get('data') or answer.get('text'))
        s.check(first.get('ok') is True and (answer.get('data') or {}).get('state') == 'unconfigured',
                'Test connection reached the host, which reported that no connection is stored', answer.get('data') or answer.get('text'))
        d.wait_for(f"(__acc.text({q(status)})||'').includes('nothing was started')", 10, 'the plain result of the test')
        s.shots.append(d.shot('settings-studio-unconfigured'))
        # 2. A command with a shell symbol is refused by the host and nothing is stored.
        d.click(studio + ' input[placeholder="user@address"]')
        d.select_all_and_type(STUDIO_ADDRESS)
        d.click(studio + ' input[placeholder^="the command"]')
        d.select_all_and_type(STUDIO_REFUSED_COMMAND)
        d.click(studio + ' button', 'Save server connection')
        refused = wait_call('studioHostSave', 1)
        d.wait_for(f"!!document.querySelector({q(studio + ' [role=alert]')})", 10, 'the refusal')
        alert = page_text(studio + ' [role=alert]')
        s.fact('refusal', alert)
        s.check(refused.get('ok') is False and 'shell symbols are refused' in alert and 'ValueError' not in alert,
                'a command with a shell symbol is refused by the host, in plain words', [refused, alert])
        s.check(stored_command() is None, 'the refused command was not stored')
        s.shots.append(d.shot('settings-studio-refused'))
        # 3. A valid address and command are stored, and never shown again.
        d.click(studio + ' input[placeholder^="the command"]')
        d.select_all_and_type(STUDIO_COMMAND)
        d.click(studio + ' button', 'Save server connection')
        stored = wait_call('studioHostSave', 2)
        d.wait_for(f"(__acc.text({q(studio)})||'').includes('A server connection is stored.')", 10, 'the stored state after saving')
        s.check(stored.get('ok') is True and stored_command() == ['ssh', '-o', 'BatchMode=yes', STUDIO_ADDRESS, STUDIO_COMMAND],
                'the host stored ssh in key-only mode with the typed address and command', stored_command())
        s.check(not d.js(f"document.documentElement.outerHTML.includes({q(STUDIO_ADDRESS)})"),
                'the stored address is not in the page any more')
        # 4. The stored command is what the host's own check starts: the reserved name cannot exist, so it fails.
        mark = len(d.events)
        began = time.time()
        d.click(studio + ' button', 'Test connection')
        wait_call('discoverStudio', 2)
        answer = wait_event(mark, studio_result, 120, 'the second test result')
        s.fact('test_with_placeholder', answer.get('data') or answer.get('text'))
        s.fact('test_with_placeholder_seconds', round(time.time() - began, 1))
        s.check((answer.get('data') or {}).get('state') == 'unavailable' and not (answer.get('data') or {}).get('instances'),
                'with the placeholder address the host reports that it could not connect (and no Studio)',
                answer.get('data') or answer.get('text'))
        d.wait_for(f"(__acc.text({q(status)})||'').startsWith('Could not connect')", 10, 'the plain failure text')
        line = page_text(status)
        s.fact('failure_text', line)
        s.check('Nothing was changed' in line and 'Connected.' not in page_text(studio),
                'the page says it could not connect and does not claim a connection', line)
        d.box(studio + ' .learn-head')
        d.pump(0.4)
        s.shots.append(d.shot('settings-studio-server'))
        # 5. Forget it, and go back to this PC (this PC's Studio is never tested by this tool).
        d.click(studio + ' button', 'Forget it')
        wait_call('studioHostClear', 1)
        d.wait_for(f"(__acc.text({q(studio)})||'').includes('No server connection is stored yet.')", 10, 'the state after forgetting')
        s.check(stored_command() == [], 'forgetting leaves an empty command in the profile')
        before = len(calls('saveSettings'))
        d.click(studio + ' .media-option', 'This PC')
        wait_call('saveSettings', before + 1)
        d.pump(0.6)
        s.check(d.settings_file().get('studio_target') == 'local_pc', 'this PC is the saved choice again')
        s.check(len(calls('discoverStudio')) == 2, 'this PC\'s own Studio was never contacted', len(calls('discoverStudio')))
        s.check(not d.key_in_page(), 'the server key is not in the page')

    with d.step('settings-small-window') as s:
        size = d.shell.size()
        d.shell.resize(920, 650)
        d.pump(0.8)
        overflow = d.js(OVERFLOW_JS.strip()) or {}
        s.fact('overflow_920x650', overflow)
        s.check(overflow.get('scrollWidth', 0) <= overflow.get('innerWidth', 0) + 1 and not overflow.get('outside'),
                'nothing in Settings is wider than a 920 x 650 window', overflow)
        d.box(voice + ' .voice-list')
        d.pump(0.4)
        s.shots.append(d.shot('settings-voice-small'))
        d.box(studio + ' .learn-head')
        d.pump(0.4)
        s.shots.append(d.shot('settings-studio-small'))
        d.shell.resize(size)
        d.pump(0.6)


def step_followup(d: Driver) -> None:
    """Fast mode in a new chat: how long the first words take on the first message and on follow-ups."""
    with d.step('followup-new-chat') as s:
        d.open_chat()
        d.click('.rail-new')
        d.wait_for("document.querySelectorAll('.thread-turns > .msg').length===0", 15, 'an empty new chat')
        s.check(not d.transcript(), 'a new chat is open and empty')
    names = ['followup-first', 'followup-second', 'followup-third']
    for name, prompt in zip(names, (PROMPT_FAST, *PROMPT_FOLLOW_UP)):
        step_fast_send(d, name=name, prompt=prompt)
    with d.step('followup-times') as s:
        done = {step.name: step.facts for step in d.steps if step.name in names}
        table = {name: {key: done.get(name, {}).get(key) for key in
                        ('send_to_first_bridge_delta_ms', 'send_to_first_visible_text_ms', 'send_to_end_ms')} for name in names}
        s.fact('first_words_ms', table)
        s.check(all(table[name]['send_to_first_visible_text_ms'] for name in names),
                'the first-word time of the first message and of both follow-ups was measured', table)
        s.check(len(d.transcript()) == 6, 'the three questions and three answers are one conversation', len(d.transcript()))


# ---------------------------------------------------------------------- child
def child_main(options) -> int:
    python_main = time.time()
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    profile = os.environ.get('APPDATA', '')
    if not is_acceptance_profile(profile):
        print('REFUSED: APPDATA is not a profile made by this tool; the owner\'s data is never used.')
        return 3
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    # Optional engines installed elsewhere on this PC: after everything this environment already has.
    for extra in os.environ.get(ENV_EXTRA_PATH, '').split(os.pathsep):
        if extra.strip() and Path(extra.strip()).is_dir() and extra.strip() not in sys.path:
            sys.path.append(extra.strip())
    from star.desktop_core import app_data
    if app_data().resolve() != (Path(profile) / 'STAR').resolve():
        print('REFUSED: the app would not store its data in the acceptance profile.')
        return 3
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMainWindow
    from star import react_shell

    app = QApplication(sys.argv[:1])
    state: dict = {'driver': None, 'closed_at': 0.0, 'forced_quit': False}
    qt_app = time.time()

    def drive():
        shell = next((w for w in app.topLevelWidgets()
                      if isinstance(w, QMainWindow) and hasattr(w, 'bridge') and hasattr(w, 'view')), None)
        if shell is None:
            print('FAILED: react_shell.launch() created no window')
            app.exit(4)
            return
        driver = state['driver'] = Driver(app, shell, options)
        driver.marks.update(python_main=python_main, qt_app=qt_app, shell_found=time.time())
        driver.install_hooks()
        try:
            if options.child == 'settings' and not options.audible:
                driver.marks['loudspeaker'] = 'silent sink' if silence_speaker(shell) else 'real (it could not be replaced)'
            run_phase(driver)
        except Exception:
            driver.python_errors.append('harness: ' + traceback.format_exc()[-2000:])
        finally:
            driver.save()
            state['closed_at'] = time.time()
            shell.close()  # what the owner does; the app must end by itself

            def force():
                state['forced_quit'] = True
                app.quit()
            QTimer.singleShot(20000, force)

    QTimer.singleShot(0, drive)
    code = react_shell.launch()  # the real entry point: builds the window and runs the event loop
    driver = state['driver']
    if driver is None:
        return 4
    out = Path(options.evidence) / f'{options.child}.json'
    report = json.loads(out.read_text(encoding='utf-8'))
    report['exit'] = {'app_exec_code': code, 'forced_quit': state['forced_quit'],
                      'close_to_loop_end_s': round(time.time() - state['closed_at'], 2),
                      'loop_ended_at': time.time()}
    report['python_errors'] = [scrub(e, driver.real_key) for e in driver.python_errors]
    report['qt_messages'] = driver.qt_messages
    out.write_text(json.dumps(report, indent=1, default=str), encoding='utf-8')
    failed = any(step['status'] == 'FAIL' for step in report['steps'])
    return 1 if failed else 0


# --------------------------------------------------------------------- parent
def child_environment(profile: Path, key: str, real_key: str) -> dict:
    env = dict(os.environ)
    env.update({
        'APPDATA': str(profile),
        ENV_KEY: key,
        'STAR_ACCEPTANCE_REAL_KEY': real_key,                       # only to detect leaks; never sent anywhere
        'PYTHON_KEYRING_BACKEND': 'keyring.backends.null.Keyring',  # never the owner's credential vault
        'PYTHONDONTWRITEBYTECODE': '1',
        'PYTHONUNBUFFERED': '1',
        'PYTHONUTF8': '1',
    })
    env.pop(ENV_STUDIO_COMMAND, None)                               # never an operator's real Studio
    return env


def parent_main(options) -> int:
    if options.key_file:
        os.environ[ENV_KEY] = Path(options.key_file).expanduser().read_text(encoding='utf-8').strip()
    reason = skip_reason()
    if reason:
        print('SKIPPED: ' + reason)
        return 0
    key = os.environ[ENV_KEY].strip()
    endpoint, model = os.environ[ENV_SERVER].strip(), os.environ[ENV_MODEL].strip()
    phases = [p.strip() for p in (options.phases or ','.join(PHASES)).split(',') if p.strip()]
    unknown = [p for p in phases if p not in PHASES]
    if unknown:
        print('Unknown phase: ' + ', '.join(unknown))
        return 2
    evidence = Path(options.evidence or tempfile.mkdtemp(prefix='star-shell-acceptance-')).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    shots = Path(options.shots).resolve() if options.shots else evidence / 'screenshots'
    if options.profile:
        profile = Path(options.profile).resolve()
        if not is_acceptance_profile(profile):
            print('REFUSED: --profile must be a folder this tool created earlier.')
            return 3
    else:
        profile = new_profile(evidence)
        os.environ['APPDATA'] = str(profile)
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from star.desktop_core import Settings
        # The app's own class and save path, so its validation decides whether this address is acceptable.
        Settings(provider='star_server', server_endpoint=endpoint, model=model).save(profile / 'STAR' / 'settings.json')
    dead = closed_loopback_endpoint()
    print(f'evidence: {evidence}\nprofile:  {profile}\nshots:    {shots}\nserver:   {endpoint} ({model})\n'
          f'window:   {"offscreen (no real window)" if options.offscreen else "real window"}', flush=True)
    steps: list[dict] = []
    summary = {'phases': {}, 'evidence': str(evidence), 'profile': str(profile), 'offscreen': bool(options.offscreen)}
    for phase in phases:
        phase_profile = profile
        if phase == 'upgrade':
            phase_profile = new_profile(evidence)
            seed_released_profile(phase_profile, dead)
        env = child_environment(phase_profile, WRONG_KEY if phase == 'wrongkey' else key, key)
        if options.offscreen:
            env['QT_QPA_PLATFORM'] = 'offscreen'
        log = evidence / f'{phase}.log'
        command = [sys.executable, str(Path(__file__).resolve()), '--child', phase, '--evidence', str(evidence),
                   '--shots', str(shots), '--dead-endpoint', dead, '--spawned-at', repr(time.time()),
                   '--turn-timeout', str(options.turn_timeout), '--agent-timeout', str(options.agent_timeout)]
        if options.audible:
            command.append('--audible')
        print(f'\n=== phase {phase}', flush=True)
        began = time.time()
        with log.open('w', encoding='utf-8') as sink:
            process = subprocess.Popen(command, env=env, stdout=sink, stderr=subprocess.STDOUT, cwd=str(ROOT))
            try:
                code = process.wait(timeout=options.phase_timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                code = -9
        ended = time.time()
        text = log.read_text(encoding='utf-8', errors='replace')
        leaked = key in text
        if leaked:
            log.write_text(scrub(text, key), encoding='utf-8')
        print(scrub(text, key).rstrip()[-6000:], flush=True)
        result_file = evidence / f'{phase}.json'
        report = json.loads(result_file.read_text(encoding='utf-8')) if result_file.is_file() else {'steps': []}
        info = {'exit_code': code, 'seconds': round(ended - began, 1), 'log_has_traceback': 'Traceback (most recent call last)' in text,
                'key_in_log': leaked, 'leaks': report.get('leaks', []), 'python_errors': len(report.get('python_errors', [])),
                'console_errors': sum(1 for c in report.get('console', []) if 'Error' in c.get('level', '')),
                'console_messages': sum(1 for c in report.get('console', []) if c.get('message') != CONSOLE_PROBE),
                'page_errors': len(report.get('page_errors', [])), 'crashed': report.get('crashed', '')}
        loop_end = (report.get('exit') or {}).get('loop_ended_at')
        if loop_end:
            info['window_close_to_process_exit_s'] = round(ended - loop_end + (report['exit'].get('close_to_loop_end_s') or 0), 2)
            info['forced_quit'] = report['exit'].get('forced_quit')
        summary['phases'][phase] = info
        steps.extend(report.get('steps', []))
        if not report.get('steps'):
            steps.append({'phase': phase, 'name': '(phase)', 'status': 'FAIL', 'seconds': info['seconds'],
                          'error': f'the phase produced no result (exit code {code})', 'checks': []})
        linger = info.get('window_close_to_process_exit_s', 0)
        gone = {'ok': linger <= 5, 'label': 'the process is gone within 5 s of closing the window', 'detail': f'{linger} s'}
        if not gone['ok'] and phase == 'testclose':
            # Chat turns stop at once; a model or server test has no cancel path and is waited for.
            gone.update(ok=True, known='a model test cannot be cancelled: after the window closes, the process stays until '
                                       f'the server answers or the request times out (here {linger} s)')
        hygiene = {'phase': phase, 'name': 'errors-and-exit', 'seconds': 0, 'error': '', 'facts': info, 'shots': [], 'checks': [
            {'ok': code in (0, 1), 'label': 'the app process ended by itself', 'detail': f'exit code {code}'},
            {'ok': not info.get('forced_quit'), 'label': 'closing the window ended the app without help', 'detail': ''},
            gone,
            {'ok': not leaked and not info['leaks'], 'label': 'the server key never appeared in a log or bridge event', 'detail': str(info['leaks'])},
            {'ok': info['python_errors'] == 0 and not info['log_has_traceback'], 'label': 'no Python exception', 'detail': f'{info["python_errors"]} recorded'},
            {'ok': info['console_errors'] == 0 and info['page_errors'] == 0, 'label': 'no JavaScript console error',
             'detail': f'{info["console_errors"]} console, {info["page_errors"]} page'},
            {'ok': not info['crashed'], 'label': 'the render process did not crash', 'detail': info['crashed']},
        ]}
        hygiene['status'] = 'PASS' if all(c['ok'] for c in hygiene['checks']) else 'FAIL'
        steps.append(hygiene)
    summary['steps'] = steps
    (evidence / 'report.json').write_text(scrub(json.dumps(summary, indent=1, default=str), key), encoding='utf-8')
    table = format_table(steps)
    (evidence / 'report.txt').write_text(table + '\n', encoding='utf-8')
    print('\n' + table, flush=True)
    failed = [s for s in steps if s['status'] == 'FAIL']
    print(f'\n{len(steps) - len(failed)} passed, {len(failed)} failed. Evidence: {evidence}', flush=True)
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Real-shell acceptance run of STAR Desktop against a STAR Server.')
    parser.add_argument('--phases', help='comma-separated subset of: ' + ', '.join(PHASES))
    parser.add_argument('--key-file', help=f'read the server key from this file into {ENV_KEY} (never printed)')
    parser.add_argument('--evidence', help='folder for logs, JSON results and the temporary profile (default: a new temp folder)')
    parser.add_argument('--shots', help='folder for shell-<step>.png screenshots (default: <evidence>/screenshots)')
    parser.add_argument('--profile', help='reuse a profile folder made by an earlier run (to repeat single phases)')
    parser.add_argument('--offscreen', action='store_true', help='run Qt offscreen instead of showing a real window')
    parser.add_argument('--audible', action='store_true',
                        help='settings phase: play the voice preview through the real speakers instead of a silent sink')
    parser.add_argument('--turn-timeout', type=float, default=900.0, help='seconds to wait for one plain reply')
    parser.add_argument('--agent-timeout', type=float, default=2400.0, help='seconds to wait for the Agent turn')
    parser.add_argument('--phase-timeout', type=float, default=3600.0, help='seconds before a phase process is killed')
    parser.add_argument('--child', choices=PHASES, help=argparse.SUPPRESS)
    parser.add_argument('--dead-endpoint', help=argparse.SUPPRESS)
    parser.add_argument('--spawned-at', help=argparse.SUPPRESS)
    return parser


def main(argv=None) -> int:
    options = build_parser().parse_args(argv)
    return child_main(options) if options.child else parent_main(options)


if __name__ == '__main__':
    sys.exit(main())
