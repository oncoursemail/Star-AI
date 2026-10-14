"""STAR Desktop's Discord supervisor: process start/stop, crash backoff and status, all with fakes.

No real process is started, no Discord connection is made, and the real %APPDATA%\\STAR and
~/.star are never read: every path lives under pytest's tmp_path.
"""
import json
import subprocess

import pytest

from star import discord_supervisor as sup
from star.discord_bot import instance_lock, runtime_status
from star.discord_bot.__main__ import EXIT_ALREADY_RUNNING, _run, _take_log_file
from star.discord_bot.bot import BotConfig
from star.desktop_core import Settings

TOKEN = "SECRET-TOKEN-VALUE-1234567890"  # star:allow (a dummy value the tests look for)
OWNER = "424242424242"


class FakeProcess:
    def __init__(self, pid):
        self.pid = pid
        self.code = None
        self.killed = False

    def poll(self):
        return self.code

    def kill(self):
        self.killed = True
        self.code = -9

    def wait(self, timeout=None):
        return self.code


class Rig:
    """A supervisor wired to fakes, with a clock the test moves by hand."""

    def __init__(self, tmp_path, *, missing=(), held=False):
        self.now = 1000.0
        self.wall = 5_000_000.0
        self.home = tmp_path / "appdata"
        self.config = tmp_path / "dotstar"
        self.config.mkdir()
        self.spawned = []
        self.killed = []
        self.missing = list(missing)
        self.held = held
        self.next_pid = 100
        self.launch_error = None
        self.sup = sup.DiscordSupervisor(
            self.home, env={}, config_folder=self.config, popen=self._popen,
            clock=lambda: self.now, wall=lambda: self.wall,
            launch=self._launch, settings_check=lambda: list(self.missing),
            held_elsewhere=lambda folder: self.held, kill=self._kill)

    def _launch(self):
        if self.launch_error:
            raise self.launch_error
        return sup.LaunchPlan(["python", "-m", "star.discord_bot", "--log-file", "x.log"], str(self.home))

    def _popen(self, argv, **kwargs):
        process = FakeProcess(self.next_pid)
        self.next_pid += 1
        self.spawned.append((process, argv, kwargs))
        return process

    def _kill(self, process):
        self.killed.append(process)
        process.kill()

    @property
    def process(self):
        return self.spawned[-1][0]

    def advance(self, seconds):
        self.now += seconds
        self.wall += seconds
        self.sup.tick()

    def report(self, state="connected", pid=None):
        runtime_status.StatusReporter(self.config, pid=pid or self.process.pid, clock=lambda: self.wall).write(state)


# -- backoff -----------------------------------------------------------------------------------

def test_backoff_grows_and_is_capped():
    assert [sup.backoff_seconds(n) for n in range(1, 9)] == [5, 10, 20, 40, 80, 160, 300, 300]
    assert sup.backoff_seconds(0) == 5


# -- start, status, stop -------------------------------------------------------------------------

def test_start_runs_one_bot_and_reports_connected_only_after_the_bot_says_so(tmp_path):
    rig = Rig(tmp_path)
    assert rig.sup.status()["state"] == "stopped"
    status = rig.sup.start()
    assert status["state"] == "starting" and status["running"] and not status["connected"]
    rig.sup.start()                      # pressing Start again does not start a second bot
    rig.advance(1)
    assert len(rig.spawned) == 1
    rig.report("connected")
    assert rig.sup.status()["state"] == "connected" and rig.sup.status()["connected"]
    rig.advance(runtime_status.FRESH_SECONDS + 1)   # no heartbeat any more: no longer "connected"
    assert rig.sup.status()["state"] == "starting"


def test_a_report_from_another_process_does_not_count_as_connected(tmp_path):
    rig = Rig(tmp_path)
    rig.sup.start()
    rig.report("connected", pid=99999)
    assert rig.sup.status()["state"] == "starting"


def test_bot_is_started_hidden_with_logs_in_stars_log_folder(tmp_path):
    rig = Rig(tmp_path)
    rig.sup.start()
    process, argv, kwargs = rig.spawned[0]
    assert argv[:3] == ["python", "-m", "star.discord_bot"] and "--log-file" in argv
    assert kwargs["stdin"] is subprocess.DEVNULL and kwargs["stderr"] is subprocess.STDOUT
    assert kwargs["env"]["PYTHONUTF8"] == "1"
    assert kwargs["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)
    assert (rig.home / "logs" / sup.CONSOLE_LOG_NAME).is_file()
    assert rig.sup.status()["logFile"] == sup.LOG_NAME


def test_stop_ends_the_bot_does_not_restart_it_and_clears_the_connected_report(tmp_path):
    rig = Rig(tmp_path)
    rig.sup.start()
    rig.report("connected")
    status = rig.sup.stop()
    assert rig.killed == [rig.process] and status["state"] == "stopped" and not status["wantsRunning"]
    assert runtime_status.read_status(rig.config)["state"] == "stopped"
    rig.advance(600)
    assert len(rig.spawned) == 1


def test_closing_stops_the_bot_started_by_this_app(tmp_path):
    rig = Rig(tmp_path)
    rig.sup.start()
    rig.sup.close()
    assert rig.killed == [rig.process]
    rig.advance(600)
    assert len(rig.spawned) == 1


# -- crash and restart ---------------------------------------------------------------------------

def test_crash_restarts_with_growing_pauses(tmp_path):
    rig = Rig(tmp_path)
    rig.sup.start()
    for expected_pause in (5, 10, 20):
        rig.process.code = 1
        rig.advance(1)
        status = rig.sup.status()
        assert status["state"] == "backoff" and status["lastExitCode"] == 1
        assert status["retryInSeconds"] == expected_pause
        before = len(rig.spawned)
        rig.advance(expected_pause - 2)
        assert len(rig.spawned) == before       # still waiting
        rig.advance(2)
        assert len(rig.spawned) == before + 1   # started again
        assert rig.sup.status()["state"] == "starting"
    assert rig.sup.status()["restarts"] == 3


def test_a_long_healthy_run_resets_the_crash_count(tmp_path):
    rig = Rig(tmp_path)
    rig.sup.start()
    rig.process.code = 1
    rig.advance(1)
    rig.advance(5)
    assert rig.sup.status()["crashes"] == 1
    rig.advance(sup.STABLE_SECONDS + 1)
    assert rig.sup.status()["crashes"] == 0
    rig.process.code = 1
    rig.advance(1)
    assert rig.sup.status()["retryInSeconds"] == 5     # back to the short pause


def test_gives_up_after_too_many_quick_crashes_until_the_owner_presses_start(tmp_path):
    rig = Rig(tmp_path)
    rig.sup.start()
    for _ in range(sup.MAX_QUICK_FAILURES + 1):
        rig.process.code = 1
        rig.advance(1)
        rig.advance(sup.BACKOFF_CAP)
    status = rig.sup.status()
    assert status["state"] == "error" and "gave up" in status["problem"]
    count = len(rig.spawned)
    rig.advance(3600)
    assert len(rig.spawned) == count
    rig.sup.start()
    assert len(rig.spawned) == count + 1 and rig.sup.status()["state"] == "starting"


@pytest.mark.parametrize("code", [2, 3])
def test_configuration_and_missing_library_exits_are_not_retried(tmp_path, code):
    rig = Rig(tmp_path)
    rig.sup.start()
    rig.process.code = code
    rig.advance(1)
    status = rig.sup.status()
    assert status["state"] == "error" and status["problem"] and status["lastExitCode"] == code
    rig.advance(3600)
    assert len(rig.spawned) == 1


def test_exit_4_means_another_bot_is_running_and_is_not_a_crash(tmp_path):
    rig = Rig(tmp_path)
    rig.sup.start()
    rig.process.code = sup.EXIT_ALREADY_RUNNING
    rig.held = True
    rig.advance(1)
    status = rig.sup.status()
    assert status["state"] == "external" and status["crashes"] == 0 and status["restarts"] == 0
    rig.advance(sup.EXTERNAL_RECHECK_SECONDS + 1)
    assert len(rig.spawned) == 1                  # still held: no second bot
    rig.held = False                               # the other bot ended: STAR takes over
    rig.advance(sup.EXTERNAL_RECHECK_SECONDS + 1)
    assert len(rig.spawned) == 2 and rig.sup.status()["state"] == "starting"


# -- not configured / running elsewhere --------------------------------------------------------------

def test_not_configured_starts_nothing_and_says_what_is_missing(tmp_path):
    rig = Rig(tmp_path, missing=["the bot token (discord.env)"])
    status = rig.sup.start()
    assert rig.spawned == []
    assert status["state"] == "not_configured" and status["missing"] == ["the bot token (discord.env)"]
    assert not status["wantsRunning"]


def test_a_bot_already_running_elsewhere_is_shown_not_duplicated(tmp_path):
    rig = Rig(tmp_path, held=True)
    status = rig.sup.start()
    assert rig.spawned == [] and status["state"] == "external" and status["external"]
    rig.advance(sup.EXTERNAL_RECHECK_SECONDS + 1)
    assert rig.spawned == []
    runtime_status.StatusReporter(rig.config, pid=7, clock=lambda: rig.wall).write("connected")
    assert rig.sup.status()["state"] == "connected" and rig.sup.status()["external"]


def test_start_problems_are_shown_and_not_retried(tmp_path):
    rig = Rig(tmp_path)
    rig.launch_error = sup.StartProblem("No Python with the Discord library was found.")
    status = rig.sup.start()
    assert status["state"] == "error" and "No Python" in status["problem"] and rig.spawned == []
    rig.launch_error = None
    assert rig.sup.start()["state"] == "starting"


def test_os_errors_when_starting_are_reported_without_paths(tmp_path):
    rig = Rig(tmp_path)
    rig.sup._popen = lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("C:\\Users\\someone\\python.exe"))
    status = rig.sup.start()
    assert status["state"] == "error" and "FileNotFoundError" in status["problem"]
    assert "someone" not in json.dumps(status)


def test_status_never_carries_the_token_or_the_owner_id(tmp_path):
    rig = Rig(tmp_path, missing=[])
    (rig.config / "discord.env").write_text(f"DISCORD_BOT_TOKEN={TOKEN}\n", encoding="utf-8")
    (rig.config / "discord-settings.env").write_text(f"DISCORD_OWNER_ID={OWNER}\n", encoding="utf-8")
    rig.sup.start()
    rig.report("connected")
    dump = json.dumps(rig.sup.status()) + json.dumps(sup.handle_action("discordStatus", rig.sup, autostart=True))
    assert TOKEN not in dump and OWNER not in dump
    log_text = "".join(path.read_text(errors="ignore") for path in (rig.home / "logs").glob("*"))
    assert TOKEN not in log_text and OWNER not in log_text


# -- settings files, launch plan -----------------------------------------------------------------

def test_missing_settings_reads_the_files_and_returns_no_values(tmp_path):
    env = {"STAR_DISCORD_CONFIG_DIR": str(tmp_path)}
    assert len(sup.missing_settings(env)) == 2
    (tmp_path / "discord.env").write_text(f"DISCORD_BOT_TOKEN={TOKEN}\n", encoding="utf-8")
    missing = sup.missing_settings(env)
    assert missing == ["your Discord user ID (discord-settings.env)"]
    (tmp_path / "discord-settings.env").write_text(f"DISCORD_OWNER_ID={OWNER}\n", encoding="utf-8")
    assert sup.missing_settings(env) == []
    (tmp_path / "discord-settings.env").write_text("nonsense\n", encoding="utf-8")
    problem = sup.missing_settings(env)
    assert len(problem) == 1 and "mistake" in problem[0] and TOKEN not in problem[0]


def test_launch_plan_prefers_the_explicit_python_and_checkout(tmp_path):
    checkout = tmp_path / "checkout"
    (checkout / "star" / "discord_bot").mkdir(parents=True)
    (checkout / "star" / "discord_bot" / "__main__.py").write_text("", encoding="utf-8")
    plan = sup.resolve_launch(tmp_path / "home", {"STAR_DISCORD_PYTHON": "py-explicit", "STAR_CHECKOUT": str(checkout)})
    assert plan.argv[:3] == ["py-explicit", "-m", "star.discord_bot"] and plan.cwd == str(checkout)
    assert plan.argv[-1].endswith("discord-bot.log")


def test_launch_plan_finds_a_venv_and_refuses_when_nothing_fits(tmp_path):
    checkout = tmp_path / "checkout"
    (checkout / "star" / "discord_bot").mkdir(parents=True)
    (checkout / "star" / "discord_bot" / "__main__.py").write_text("", encoding="utf-8")
    env = {"STAR_CHECKOUT": str(checkout)}
    with pytest.raises(sup.StartProblem, match="No Python"):
        sup.resolve_launch(tmp_path / "home", env, frozen=True)     # the packaged app cannot run -m itself
    venv = tmp_path / "home" / "discord-venv" / "Scripts"
    venv.mkdir(parents=True)
    (venv / "python.exe").write_text("", encoding="utf-8")
    assert sup.resolve_launch(tmp_path / "home", env, frozen=True).argv[0].endswith("python.exe")
    with pytest.raises(sup.StartProblem, match="not found"):
        sup.resolve_launch(tmp_path / "home", {"STAR_CHECKOUT": str(tmp_path / "nowhere")})


# -- bridge actions and the opt-in ---------------------------------------------------------------------

def test_actions_start_stop_status_and_the_autostart_echo(tmp_path):
    rig = Rig(tmp_path)
    assert sup.handle_action("discordStatus", rig.sup, autostart=False) == {**rig.sup.status(), "autostart": False}
    assert sup.handle_action("discordStart", rig.sup, autostart=False)["state"] == "starting"
    assert sup.handle_action("discordStop", rig.sup, autostart=True)["state"] == "stopped"
    with pytest.raises(PermissionError):
        sup.handle_action("discordDelete", rig.sup, autostart=True)


def test_switching_the_opt_in_on_starts_the_bot_and_off_leaves_it_alone(tmp_path):
    rig = Rig(tmp_path)
    assert sup.handle_action("discordSetAutostart", rig.sup, autostart=False)["state"] == "stopped"
    assert rig.spawned == []
    assert sup.handle_action("discordSetAutostart", rig.sup, autostart=True)["state"] == "starting"
    assert sup.handle_action("discordSetAutostart", rig.sup, autostart=False)["state"] == "starting"
    assert len(rig.spawned) == 1


def test_launch_starts_the_bot_only_when_the_owner_opted_in(tmp_path):
    rig = Rig(tmp_path)
    assert sup.start_if_opted_in(rig.sup, False) is False and rig.spawned == []
    assert sup.start_if_opted_in(rig.sup, True) is True and len(rig.spawned) == 1


def test_the_opt_in_is_off_by_default_and_must_be_a_real_boolean(tmp_path):
    settings = Settings()
    assert settings.discord_autostart is False
    settings.discord_autostart = "yes"
    with pytest.raises(ValueError):
        settings.validate()
    settings.discord_autostart = True
    settings.validate()
    file = tmp_path / "settings.json"
    settings.save(file)
    assert Settings.load(file).discord_autostart is True


def test_the_supervisor_thread_runs_ticks_and_stops(tmp_path):
    rig = Rig(tmp_path)
    rig.sup.begin(interval=0.01)
    rig.sup.start()
    rig.process.code = 1
    rig.sup.close()                       # ends the thread and the bot without hanging
    assert rig.sup._thread is not None and not rig.sup._thread.is_alive()


# -- the bot side: single-instance lock, status file, exit code ------------------------------------------

def test_second_bot_cannot_take_the_lock_and_release_frees_it(tmp_path):
    first, second = instance_lock.InstanceLock(tmp_path), instance_lock.InstanceLock(tmp_path)
    assert not instance_lock.held_elsewhere(tmp_path)
    assert first.acquire()
    assert instance_lock.held_elsewhere(tmp_path)
    assert not second.acquire()
    first.release()
    assert not instance_lock.held_elsewhere(tmp_path)
    assert second.acquire()
    second.release()


def test_running_a_second_bot_exits_with_code_4_before_touching_discord(tmp_path, monkeypatch):
    monkeypatch.setenv("STAR_DISCORD_CONFIG_DIR", str(tmp_path))
    env = {"STAR_DISCORD_BOT_TOKEN": "dummy-token", "STAR_DISCORD_OWNER_IDS": "123",
           "STAR_DISCORD_CONFIG_DIR": str(tmp_path)}
    held = instance_lock.InstanceLock(tmp_path)
    assert held.acquire()
    monkeypatch.setattr("star.discord_bot.__main__.create_bot",
                        lambda *a, **k: pytest.fail("a second bot must not be created"))
    try:
        assert _run(BotConfig.from_env(env), env) == EXIT_ALREADY_RUNNING == sup.EXIT_ALREADY_RUNNING
    finally:
        held.release()


def test_status_file_round_trip_and_garbage_is_ignored(tmp_path):
    runtime_status.StatusReporter(tmp_path, pid=5, clock=lambda: 12.5).write("connected", guilds=1, latency_ms=40, secret=1)
    data = runtime_status.read_status(tmp_path)
    assert data == {"pid": 5, "state": "connected", "updated_at": 12.5, "guilds": 1, "latency_ms": 40}
    with pytest.raises(ValueError):
        runtime_status.StatusReporter(tmp_path).write("exploded")
    (tmp_path / runtime_status.STATUS_FILE).write_text("{not json", encoding="utf-8")
    assert runtime_status.read_status(tmp_path) is None
    (tmp_path / runtime_status.STATUS_FILE).write_text(json.dumps({"state": "connected"}), encoding="utf-8")
    assert runtime_status.read_status(tmp_path) is None


def test_log_file_argument_is_split_off():
    assert _take_log_file(["--log-file", "a.log", "doctor"]) == (["doctor"], "a.log")
    assert _take_log_file(["smoke"]) == (["smoke"], "")
    assert _take_log_file(["--log-file"]) == (["--log-file"], "")


def test_the_bot_reports_connected_and_reconnecting_through_the_status_file(tmp_path):
    pytest.importorskip("discord")
    import asyncio
    from star.discord_bot.bot import create_bot
    config = BotConfig.from_env({"STAR_DISCORD_BOT_TOKEN": "dummy-token", "STAR_DISCORD_OWNER_IDS": "123"})
    bot = create_bot(config, reporter=runtime_status.StatusReporter(tmp_path, pid=77, clock=lambda: 50.0))
    asyncio.run(bot.on_disconnect())
    assert runtime_status.read_status(tmp_path)["state"] == "reconnecting"
    bot.is_ready = lambda: True                      # a connected gateway, without connecting to Discord
    asyncio.run(bot.on_ready())
    data = runtime_status.read_status(tmp_path)
    assert data["state"] == "connected" and data["pid"] == 77 and data["guilds"] == 0
    assert "dummy-token" not in (tmp_path / runtime_status.STATUS_FILE).read_text(encoding="utf-8")
