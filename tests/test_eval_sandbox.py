"""The server sandbox for model-written Luau: limits, command shape, failure handling (no network, no ssh)."""
import base64
import subprocess

import pytest

from star import eval_sandbox as sb


class FakeRun:
    def __init__(self, stdout=b"", returncode=0, raises=None):
        self.stdout, self.returncode, self.raises, self.calls = stdout, returncode, raises, []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if self.raises:
            raise self.raises
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, b"")


def test_remote_script_applies_limits_and_runs_in_a_fresh_directory():
    script = sb.build_remote_script("print(1)", mem_mb=128, cpu_s=5, wall_s=9)
    assert f"--as={128 * 1024 * 1024}" in script and "--cpu=5" in script and "timeout -s KILL 9" in script
    assert "--fsize=" in script and "--nofile=" in script and "--core=0" in script
    assert "mktemp -d" in script and "rm -rf" in script
    assert "--nproc" not in script          # user `star` already runs the model servers: a low limit breaks fork
    assert base64.b64encode(b"print(1)").decode() in script
    assert "PIPESTATUS[0]" in script


def test_remote_script_never_contains_the_model_code_verbatim():
    code = "os.execute('rm -rf /') ; $(reboot) ; STAR_EOF"
    script = sb.build_remote_script(code)
    assert "reboot" not in script and "rm -rf /" not in script


@pytest.mark.parametrize("limits", [{"mem_mb": 0}, {"cpu_s": -1}, {"wall_s": 10_000}, {"mem_mb": "256"}])
def test_remote_script_rejects_bad_limits(limits):
    with pytest.raises(ValueError):
        sb.build_remote_script("x", **limits)


def test_remote_script_rejects_bad_binary_path():
    with pytest.raises(ValueError):
        sb.build_remote_script("x", luau="/bin/luau; reboot")


def test_parse_status():
    assert sb.parse_status("a\nb\n@@RC 137\n") == (137, "a\nb")
    assert sb.parse_status("no status") == (-1, "no status")


def test_container_sandbox_command_runs_as_user_star_in_the_container():
    run = FakeRun(b"@@T\tpass\ta\n@@DONE\n@@RC 0\n")
    box = sb.ContainerSandbox("someone@192.168.1.10", runner=run)
    result = box.run("print(1)")
    argv, kwargs = run.calls[0]
    assert argv[:3] == ["ssh", "-o", "BatchMode=yes"]
    assert "lxc exec starai -- runuser -u star -- bash -s" in argv[-1]
    assert kwargs["input"].decode().count("base64 -d") == 1
    assert result.rc == 0 and "@@DONE" in result.stdout and not result.timed_out and not result.error


def test_container_sandbox_marks_kills_as_timeouts():
    box = sb.ContainerSandbox("a@b.c", runner=FakeRun(b"partial\n@@RC 137\n"))
    assert box.run("while true do end").timed_out
    finished = sb.ContainerSandbox("a@b.c", runner=FakeRun(b"@@DONE\n@@RC 137\n"))
    assert not finished.run("x").timed_out


def test_container_sandbox_reports_infrastructure_errors():
    assert "timed out" in sb.ContainerSandbox("a@b.c", runner=FakeRun(raises=subprocess.TimeoutExpired("ssh", 1))).run("x").error
    assert sb.ContainerSandbox("a@b.c", runner=FakeRun(raises=FileNotFoundError())).run("x").error
    assert sb.ContainerSandbox("a@b.c", runner=FakeRun(b"", returncode=255)).run("x").error


def test_lock_probe():
    assert sb.ContainerSandbox("a@b.c", runner=FakeRun(b"LOCKED\n")).lock_present() is True
    assert sb.ContainerSandbox("a@b.c", runner=FakeRun(b"FREE\n")).lock_present() is False
    assert sb.ContainerSandbox("a@b.c", runner=FakeRun(b"", returncode=255)).lock_present() is None
    assert sb.ContainerSandbox("a@b.c", runner=FakeRun(raises=OSError())).lock_present() is None
    with pytest.raises(ValueError):
        sb.ContainerSandbox("a@b.c", runner=FakeRun()).lock_present("/opt/star/lock; reboot")


@pytest.mark.parametrize("target", ["", "no-at-sign", "a b@c", "a@b;reboot", "-oProxyCommand=x@y"])
def test_ssh_target_is_validated(target):
    with pytest.raises(ValueError):
        sb.ContainerSandbox(target)
