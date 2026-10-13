"""Create, show or remove the Windows Task Scheduler entry that starts STAR's Discord bot at logon.

Run it through scripts\\star_discord_autostart.cmd (PowerShell scripts are not needed). It does nothing
until you run `install`; `print` shows the task without creating it.

    star_discord_autostart.cmd print     show the task definition (creates nothing)
    star_discord_autostart.cmd install   create or replace the task "STAR Discord bot" (your account only)
    star_discord_autostart.cmd status    show whether the task exists and when it last ran
    star_discord_autostart.cmd start     run the task now          stop   end the running task
    star_discord_autostart.cmd remove    delete the task

The task runs in your own logged-in session with ordinary rights (no password stored, no
administrator), 30 seconds after you sign in, without a console window (pythonw.exe), and Windows
restarts it up to 99 times, a minute apart, if it ends with an error. The bot keeps its own
log in STAR's log folder (discord-bot.log). Only one bot can run at a time: if STAR Desktop or a
terminal already runs it, the extra start exits at once (see docs/STAR_DISCORD_SETUP.md).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

TASK_NAME = "STAR Discord bot"
LOGON_DELAY = "PT30S"
RESTART_INTERVAL = "PT1M"
RESTART_COUNT = 99
ROOT = Path(__file__).resolve().parent.parent


def windowless_python(python: str) -> str:
    """pythonw.exe next to python.exe (no console window), when it exists."""
    path = Path(python)
    candidate = path.with_name("pythonw.exe")
    return str(candidate) if path.name.lower() == "python.exe" and candidate.is_file() else python


def log_file() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    return base / "STAR" / "logs" / "discord-bot.log"


def build_task_xml(*, user: str, python: str, checkout: Path, log: Path) -> str:
    """The task definition. Every value is escaped; nothing here is a secret."""
    arguments = f'-m star.discord_bot --log-file "{log}"'
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Starts STAR's Discord bot when you sign in. Remove it with star_discord_autostart.cmd remove.</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{escape(user)}</UserId>
      <Delay>{LOGON_DELAY}</Delay>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{escape(user)}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>{RESTART_INTERVAL}</Interval>
      <Count>{RESTART_COUNT}</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(python)}</Command>
      <Arguments>{escape(arguments)}</Arguments>
      <WorkingDirectory>{escape(str(checkout))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def current_user() -> str:
    domain, name = os.environ.get("USERDOMAIN", ""), os.environ.get("USERNAME", "")
    return f"{domain}\\{name}" if domain and name else name


def setup_notes(checkout: Path) -> list[str]:
    """Plain warnings (never values) so the owner knows before the first sign-in."""
    notes = []
    sys.path.insert(0, str(checkout))
    try:
        from star.discord_supervisor import missing_settings
        notes += [f"Not set up yet: {item}." for item in missing_settings()]
    except Exception:
        notes.append("Could not check the Discord settings files.")
    finally:
        sys.path.pop(0)
    try:
        import importlib.util
        if importlib.util.find_spec("discord") is None:
            notes.append("This Python has no discord.py: install requirements-discord.txt into it first.")
    except Exception:
        pass
    return notes


def run_schtasks(args: list[str], runner=subprocess.run) -> int:
    done = runner(["schtasks", *args], text=True)
    return int(done.returncode)


def main(argv: list[str] | None = None, *, runner=subprocess.run, python: str | None = None,
         checkout: Path | None = None, user: str | None = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="star_discord_autostart.cmd", description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["print", "install", "remove", "status", "start", "stop"])
    parser.add_argument("--python", default="", help="the Python to run the bot with (default: the one running this script)")
    args = parser.parse_args(argv)
    checkout = checkout or ROOT
    command = args.command
    if command in {"print", "install"}:
        interpreter = windowless_python(args.python or python or sys.executable)
        xml = build_task_xml(user=user or current_user(), python=interpreter, checkout=checkout, log=log_file())
        if command == "print":
            print(xml, file=out)
            return 0
        for note in setup_notes(checkout):
            print("NOTE:", note, file=out)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "star-discord-task.xml"
            path.write_text(xml, encoding="utf-16")
            code = run_schtasks(["/Create", "/TN", TASK_NAME, "/XML", str(path), "/F"], runner)
        print("The task is installed. It starts the bot 30 seconds after you sign in." if code == 0
              else "Windows refused to create the task (see the message above).", file=out)
        return code
    if command == "remove":
        return run_schtasks(["/Delete", "/TN", TASK_NAME, "/F"], runner)
    if command == "status":
        return run_schtasks(["/Query", "/TN", TASK_NAME, "/V", "/FO", "LIST"], runner)
    if command == "start":
        return run_schtasks(["/Run", "/TN", TASK_NAME], runner)
    return run_schtasks(["/End", "/TN", TASK_NAME], runner)


if __name__ == "__main__":
    raise SystemExit(main())
