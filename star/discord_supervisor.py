"""STAR Desktop's supervisor for the Discord bot (Settings > Discord).

The bot is a separate process (``python -m star.discord_bot``). This module starts it when the
owner asks (or when "Start the Discord bot with STAR" is on), restarts it with a growing pause
after a crash, stops it when STAR closes, and answers "is it connected?" for the Settings page.

What it never does:
  * show, log or return the bot token, the owner's Discord IDs, or the STAR Server key. The bot
    reads the token and IDs from ``~/.star`` itself and the brain key from the keyring or the key
    file; the supervisor only checks that the files hold the settings it needs;
  * run a second bot: the bot takes a lock file (star/discord_bot/instance_lock.py), so a bot that
    is already running in a terminal or in Task Scheduler is shown as "running elsewhere";
  * retry a bot that exits because its configuration or library is wrong (exit codes 2 and 3).

Everything with side effects is injectable (process starter, clock, lock probe, kill), so the tests
use fakes and never start a real process.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from .discord_bot import instance_lock, runtime_status
from .discord_bot.local_config import config_dir, load_merged_env

EXIT_CONFIG, EXIT_MISSING_LIBRARY, EXIT_ALREADY_RUNNING = 2, 3, 4
NO_RETRY_EXITS = {
    EXIT_CONFIG: "The bot's settings are wrong. Run scripts\\star_discord.cmd doctor to see what to fix, then press Start.",
    EXIT_MISSING_LIBRARY: "The Discord library is not installed for the Python that runs the bot. "
                          "See docs/STAR_DISCORD_SETUP.md, then press Start.",
}
BACKOFF_FIRST, BACKOFF_CAP = 5.0, 300.0
STABLE_SECONDS = 120.0       # a run this long counts as healthy and resets the crash count
MAX_QUICK_FAILURES = 10      # then stop trying until the owner presses Start
EXTERNAL_RECHECK_SECONDS = 30.0
CONSOLE_LOG_LIMIT = 1_000_000

LOG_NAME = "discord-bot.log"                 # the bot's own rotating log (STAR log folder)
CONSOLE_LOG_NAME = "discord-bot-console.log"  # raw stdout/stderr: start-up errors and tracebacks


class StartProblem(Exception):
    """The bot cannot be started yet; the message is safe to show (no secrets, no paths)."""


def backoff_seconds(failures: int) -> float:
    """5, 10, 20, 40, 80, 160, then 300 seconds."""
    return min(BACKOFF_CAP, BACKOFF_FIRST * (2 ** max(0, failures - 1)))


def missing_settings(env: Mapping[str, str] | None = None) -> list[str]:
    """What the bot still needs, as plain words. Reads the files; returns no values."""
    try:
        merged = load_merged_env(dict(os.environ if env is None else env))
    except ValueError:
        return ["a Discord settings file with a mistake in it (run scripts\\star_discord.cmd doctor)"]
    missing = []
    if not str(merged.get("STAR_DISCORD_BOT_TOKEN", "")).strip():
        missing.append("the bot token (discord.env)")
    if not str(merged.get("STAR_DISCORD_OWNER_IDS", "")).strip():
        missing.append("your Discord user ID (discord-settings.env)")
    return missing


@dataclass(frozen=True)
class LaunchPlan:
    argv: list[str]
    cwd: str


def resolve_launch(home: Path, env: Mapping[str, str] | None = None, *, frozen: bool | None = None) -> LaunchPlan:
    """Which Python runs the bot, and from which folder.

    Order: STAR_DISCORD_PYTHON (as the terminal launcher uses it), this Python when it is a normal
    interpreter that has discord.py, a .venv in the checkout, then ``discord-venv`` in STAR's data
    folder. The packaged STAR.exe cannot run ``-m star.discord_bot`` by itself, so it needs one of
    the explicit routes (STAR_DISCORD_PYTHON with STAR_CHECKOUT).
    """
    source = os.environ if env is None else env
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    checkout = Path(source.get("STAR_CHECKOUT") or Path(__file__).resolve().parent.parent)
    if not (checkout / "star" / "discord_bot" / "__main__.py").is_file():
        raise StartProblem("The STAR code for the Discord bot was not found. Set STAR_CHECKOUT to a STAR "
                           "checkout (see docs/STAR_DISCORD_SETUP.md).")
    python = str(source.get("STAR_DISCORD_PYTHON") or "").strip()
    if not python and not is_frozen and importlib.util.find_spec("discord") is not None:
        python = sys.executable
    if not python:
        for candidate in (checkout / ".venv" / "Scripts" / "python.exe", checkout / ".venv" / "bin" / "python",
                          home / "discord-venv" / "Scripts" / "python.exe", home / "discord-venv" / "bin" / "python"):
            if candidate.is_file():
                python = str(candidate)
                break
    if not python:
        raise StartProblem("No Python with the Discord library was found. Install requirements-discord.txt "
                           "or set STAR_DISCORD_PYTHON (see docs/STAR_DISCORD_SETUP.md).")
    log = home / "logs" / LOG_NAME
    return LaunchPlan([python, "-m", "star.discord_bot", "--log-file", str(log)], str(checkout))


def kill_tree(process) -> None:
    """End the bot and anything it started (a venv's python.exe is a launcher with a child)."""
    pid = getattr(process, "pid", None)
    if os.name == "nt" and pid:
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        process.kill()
    except OSError:
        pass


class DiscordSupervisor:
    """Keeps at most one bot process running while the owner wants it."""

    def __init__(self, home: Path, *, env: Mapping[str, str] | None = None,
                 config_folder: Path | None = None,
                 popen: Callable = subprocess.Popen,
                 clock: Callable[[], float] = time.monotonic,
                 wall: Callable[[], float] = time.time,
                 launch: Callable[[], LaunchPlan] | None = None,
                 settings_check: Callable[[], list[str]] | None = None,
                 held_elsewhere: Callable[[Path], bool] = instance_lock.held_elsewhere,
                 kill: Callable = kill_tree):
        self.home = Path(home)
        self._env = dict(os.environ if env is None else env)
        if config_folder is not None:
            self._env["STAR_DISCORD_CONFIG_DIR"] = str(config_folder)
        self._config_folder = config_dir(self._env)
        self._popen, self._clock, self._wall, self._kill = popen, clock, wall, kill
        self._launch = launch or (lambda: resolve_launch(self.home, self._env))
        self._settings_check = settings_check or (lambda: missing_settings(self._env))
        self._held_elsewhere = held_elsewhere
        self._lock = threading.RLock()
        self._process = None
        self._console = None
        self._desired = False
        self._started_at = 0.0
        self._failures = 0
        self._restarts = 0
        self._next_try: float | None = None
        self._waiting_for_other = False
        self._problem = ""
        self._last_exit: int | None = None
        self._stop_thread = threading.Event()
        self._thread: threading.Thread | None = None

    # -- owner actions ---------------------------------------------------------------------

    def start(self) -> dict:
        """Start now (the Start button, or autostart at launch). Clears an earlier give-up."""
        with self._lock:
            self._desired = True
            self._failures = 0
            self._problem = ""
            self._next_try = None
            self._waiting_for_other = False
            self.tick()
            return self.status()

    def stop(self) -> dict:
        """Stop the bot this supervisor started and do not restart it."""
        with self._lock:
            self._desired = False
            self._next_try = None
            self._waiting_for_other = False
            self._end_process()
            return self.status()

    def close(self) -> None:
        """STAR is closing: stop the thread and the bot."""
        self._stop_thread.set()
        with self._lock:
            self._desired = False
            self._end_process()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3)

    def begin(self, interval: float = 1.0) -> None:
        """Start the thread that calls tick() every `interval` seconds."""
        if self._thread is not None:
            return

        def loop():
            while not self._stop_thread.wait(interval):
                try:
                    self.tick()
                except Exception:  # supervision must outlive any one surprise
                    self._problem = "The Discord supervisor hit an unexpected error; see STAR's logs."

        self._thread = threading.Thread(target=loop, name="star-discord-supervisor", daemon=True)
        self._thread.start()

    # -- one supervision step --------------------------------------------------------------

    def tick(self) -> None:
        with self._lock:
            if not self._desired:
                return
            now = self._clock()
            if self._process is not None:
                self._watch(now)
                return
            if self._next_try is not None and now < self._next_try:
                return
            self._spawn(now)

    def _watch(self, now: float) -> None:
        assert self._process is not None  # tick() only calls this with a process
        code = self._process.poll()
        if code is None:
            if now - self._started_at >= STABLE_SECONDS:
                self._failures = 0
            return
        self._last_exit = code
        ran = now - self._started_at
        self._release_process()
        if code in NO_RETRY_EXITS:
            self._desired = False
            self._problem = NO_RETRY_EXITS[code]
            return
        if code == EXIT_ALREADY_RUNNING:
            self._wait_for_other(now)
            return
        if ran >= STABLE_SECONDS:
            self._failures = 0
        self._failures += 1
        if self._failures > MAX_QUICK_FAILURES:
            self._desired = False
            self._problem = (f"The bot stopped {MAX_QUICK_FAILURES} times in a row and STAR gave up. "
                             f"Look at {LOG_NAME} in STAR's log folder, then press Start.")
            return
        self._restarts += 1
        self._next_try = now + backoff_seconds(self._failures)

    def _wait_for_other(self, now: float) -> None:
        self._waiting_for_other = True
        self._next_try = now + EXTERNAL_RECHECK_SECONDS

    def _spawn(self, now: float) -> None:
        missing = self._settings_check()
        if missing:
            self._desired = False  # status() reports "not_configured" and what is missing
            return
        if self._held_elsewhere(self._config_folder):
            self._wait_for_other(now)
            return
        self._waiting_for_other = False
        try:
            plan = self._launch()
            logs = self.home / "logs"
            logs.mkdir(parents=True, exist_ok=True)
            console_path = logs / CONSOLE_LOG_NAME
            mode = "wb" if console_path.is_file() and console_path.stat().st_size > CONSOLE_LOG_LIMIT else "ab"
            self._console = open(console_path, mode)
            child_env = {**self._env, "PYTHONUTF8": "1"}
            self._process = self._popen(
                plan.argv, cwd=plan.cwd, env=child_env, stdout=self._console, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except StartProblem as exc:
            self._release_process()
            self._desired = False
            self._problem = str(exc)
            return
        except OSError as exc:
            self._release_process()
            self._desired = False
            self._problem = f"The bot process could not be started ({type(exc).__name__}). Check the Python path."
            return
        self._started_at = now
        self._next_try = None

    def _release_process(self) -> None:
        self._process = None
        console, self._console = self._console, None
        if console is not None:
            try:
                console.close()
            except OSError:
                pass

    def _end_process(self) -> None:
        process = self._process
        if process is None:
            return
        pid = getattr(process, "pid", 0)
        if process.poll() is None:
            self._kill(process)
            try:
                process.wait(timeout=5)
            except Exception:
                pass
        self._release_process()
        # The killed bot cannot say goodbye; the file would otherwise claim "connected" until it ages out.
        if isinstance(pid, int) and pid:
            runtime_status.StatusReporter(self._config_folder, pid=pid, clock=self._wall).write("stopped")

    # -- what the Settings page shows -----------------------------------------------------------

    def status(self) -> dict:
        """State words for the page. No token, no IDs, no paths."""
        with self._lock:
            now = self._clock()
            report = runtime_status.read_status(self._config_folder)
            fresh = bool(report) and self._wall() - float(report["updated_at"]) <= runtime_status.FRESH_SECONDS
            base = {
                "running": False, "connected": False, "external": False, "wantsRunning": self._desired,
                "restarts": self._restarts, "crashes": self._failures, "lastExitCode": self._last_exit,
                "retryInSeconds": None, "problem": self._problem, "logFile": LOG_NAME,
                "missing": [],
            }
            process = self._process
            if process is not None and process.poll() is None:
                own = bool(report and report["pid"] == getattr(process, "pid", None) and fresh)
                connected = bool(own and report and report["state"] == "connected")
                return {**base, "state": "connected" if connected else "starting", "running": True,
                        "connected": connected,
                        "message": "STAR is connected to Discord." if connected
                        else "Starting. Connecting to Discord takes a few seconds."}
            if self._desired and self._next_try is not None and not self._waiting_for_other:
                return {**base, "state": "backoff", "retryInSeconds": max(0, int(self._next_try - now + 0.999)),
                        "message": "The bot stopped unexpectedly. STAR will start it again shortly."}
            if self._problem:
                return {**base, "state": "error", "message": self._problem}
            if self._held_elsewhere(self._config_folder):
                connected = bool(report) and fresh and report["state"] == "connected"
                return {**base, "state": "connected" if connected else "external", "external": True,
                        "connected": connected, "running": True,
                        "message": "The bot is running in another window (a terminal or Task Scheduler). "
                                   "Stop it there; STAR will not start a second one."
                        + ("" if not self._desired else " STAR will take over if it stops.")}
            missing = self._settings_check()
            if missing:
                return {**base, "state": "not_configured", "missing": missing,
                        "message": "Not set up yet. See docs/STAR_DISCORD_SETUP.md."}
            return {**base, "state": "stopped", "message": "The bot is not running."}


# -- the desktop bridge's three actions (Settings > Discord) -----------------------------------------

DISCORD_ACTIONS = frozenset({"discordStatus", "discordStart", "discordStop", "discordSetAutostart"})


def handle_action(action: str, supervisor: DiscordSupervisor, *, autostart: bool) -> dict:
    """Answer a Settings > Discord request. `autostart` is the saved opt-in; the reply echoes it."""
    if action == "discordStart":
        status = supervisor.start()
    elif action == "discordStop":
        status = supervisor.stop()
    elif action in {"discordStatus", "discordSetAutostart"}:
        # Turning the opt-in on starts the bot now; turning it off leaves a running bot alone.
        status = supervisor.start() if action == "discordSetAutostart" and autostart else supervisor.status()
    else:
        raise PermissionError("Action not permitted")
    return {**status, "autostart": bool(autostart)}


def start_if_opted_in(supervisor: DiscordSupervisor, autostart: bool) -> bool:
    """On launch: start the bot only when the owner switched the opt-in on."""
    if not autostart:
        return False
    supervisor.start()
    return True
