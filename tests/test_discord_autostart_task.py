"""The Task Scheduler script for the Discord bot: it builds the task and calls schtasks only when told to.

A fake runner stands in for schtasks.exe, so nothing is created on the machine running the tests.
"""
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("discord_autostart_task", ROOT / "scripts" / "discord_autostart_task.py")
task = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(task)
NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


class Runner:
    def __init__(self, code=0):
        self.calls, self.code, self.xml = [], code, None

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        if "/XML" in argv:                      # the file only exists during the call
            self.xml = Path(argv[argv.index("/XML") + 1]).read_bytes()
        return SimpleNamespace(returncode=self.code)


def run(*argv, runner=None):
    runner = runner or Runner()
    out = io.StringIO()
    code = task.main(list(argv), runner=runner, python="C:\\Py\\python.exe", checkout=Path("C:/STAR/checkout"),
                     user="PC\\owner", out=out)
    return code, runner, out.getvalue()


def test_print_shows_the_task_and_calls_nothing():
    code, runner, text = run("print")
    assert code == 0 and runner.calls == []
    root = ET.fromstring(text.replace('encoding="UTF-16"', ""))
    assert root.find("t:Triggers/t:LogonTrigger/t:UserId", NS).text == "PC\\owner"
    assert root.find("t:Triggers/t:LogonTrigger/t:Delay", NS).text == "PT30S"


def test_task_runs_as_the_user_with_ordinary_rights_and_restarts_after_failures():
    root = ET.fromstring(task.build_task_xml(user="PC\\o&w", python="C:\\Py\\pythonw.exe",
                                             checkout=Path("C:/STAR/c"), log=Path("C:/logs/discord-bot.log"))
                         .replace('encoding="UTF-16"', ""))
    principal = root.find("t:Principals/t:Principal", NS)
    assert principal.find("t:LogonType", NS).text == "InteractiveToken"      # no stored password
    assert principal.find("t:RunLevel", NS).text == "LeastPrivilege"          # not administrator
    assert principal.find("t:UserId", NS).text == "PC\\o&w"                   # escaped, then parsed back
    settings = root.find("t:Settings", NS)
    assert settings.find("t:MultipleInstancesPolicy", NS).text == "IgnoreNew"
    assert settings.find("t:RestartOnFailure/t:Count", NS).text == "99"
    assert settings.find("t:ExecutionTimeLimit", NS).text == "PT0S"
    exe = root.find("t:Actions/t:Exec", NS)
    assert exe.find("t:Command", NS).text.endswith("pythonw.exe")
    arguments = exe.find("t:Arguments", NS).text
    assert arguments.startswith("-m star.discord_bot --log-file ") and "token" not in arguments.lower()


def test_install_creates_the_named_task_from_an_xml_file_and_says_so():
    code, runner, text = run("install")
    assert code == 0 and len(runner.calls) == 1
    argv = runner.calls[0]
    assert argv[:2] == ["schtasks", "/Create"] and argv[argv.index("/TN") + 1] == "STAR Discord bot" and "/F" in argv
    assert runner.xml.startswith(b"\xff\xfe")                                 # UTF-16 with BOM
    assert "installed" in text


def test_install_failure_is_reported_and_returned():
    code, _, text = run("install", runner=Runner(code=1))
    assert code == 1 and "refused" in text


@pytest.mark.parametrize("command, flag", [("remove", "/Delete"), ("status", "/Query"), ("start", "/Run"), ("stop", "/End")])
def test_other_commands_map_to_one_schtasks_call(command, flag):
    code, runner, _ = run(command)
    assert code == 0 and len(runner.calls) == 1 and runner.calls[0][:2] == ["schtasks", flag]
    assert "STAR Discord bot" in runner.calls[0]


def test_windowless_python_prefers_pythonw_when_it_exists(tmp_path):
    (tmp_path / "python.exe").write_text("")
    assert task.windowless_python(str(tmp_path / "python.exe")) == str(tmp_path / "python.exe")
    (tmp_path / "pythonw.exe").write_text("")
    assert task.windowless_python(str(tmp_path / "python.exe")) == str(tmp_path / "pythonw.exe")


def test_unknown_command_is_refused():
    with pytest.raises(SystemExit):
        run("delete-everything")
