"""Executable offline workbench regressions. No network, root, GPU or keyring."""
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import replace

import pytest

# Standalone server is intentionally not a dependency of the desktop package.
SPEC = importlib.util.spec_from_file_location(
    "star_workbench_test_app", Path(__file__).parents[1] / "server/workbench/app.py")
app = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = app
SPEC.loader.exec_module(app)
pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux-only isolated server")


@pytest.fixture
def bench(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    instance = app.Workbench(root, tmp_path / "state", tmp_path / "audit.jsonl",
                             tmp_path / "PAUSED", sandbox=False)
    yield instance
    instance.close()


def call(bench, name, **args):
    return bench.invoke(name, args)


def test_file_roundtrip_listing_search_and_delete(bench):
    content = "first\nsecond\nthird\n"
    result = call(bench, "ws_write", path="folder/file.py", content=content)
    assert result == {"bytes": len(content), "sha256": hashlib.sha256(content.encode()).hexdigest()}
    assert call(bench, "ws_read", path="folder/file.py", start_line=2, max_lines=1)["text"] == "second\n"
    assert call(bench, "ws_list", depth=2)[1] == {"path": "folder/file.py", "kind": "file"}
    assert call(bench, "ws_search", pattern="second")["matches"][0]["line"] == 2
    assert call(bench, "ws_search", pattern=".*")["matches"] == []  # literal, no regex/ReDoS
    assert call(bench, "ws_delete", path="folder/file.py")["deleted"]
    assert call(bench, "ws_delete", path="folder")["deleted"]
    with pytest.raises(PermissionError):
        call(bench, "ws_delete", path=".")


@pytest.mark.parametrize("attempt", range(20))
def test_twenty_escape_attempts_on_actual_file_tools(bench, tmp_path, attempt):
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "payload"
    target.write_text("untouched")
    root = bench.ws.root
    (root / "escape").symlink_to(outside, target_is_directory=True)
    (root / "file-link").symlink_to(target)
    (root / "chain").symlink_to(root / "escape", target_is_directory=True)
    (root / "loop").symlink_to(root / "loop", target_is_directory=True)
    (root / "inside").mkdir()
    (root / "inside/link").symlink_to(outside, target_is_directory=True)
    paths = ["../outside/payload", "inside/../../outside/payload", "./../outside/payload",
             str(target), str(root) + "-other/payload", "/etc/passwd", "/proc/self/environ",
             "escape/payload", "escape/nested/payload", "file-link", "chain/payload",
             "loop/payload", "inside/link/payload", "inside/link/../payload", "..",
             "../work/escape/payload", "inside\\..\\outside\\payload", "bad\0path",
             "inside/../../../payload", str(root / "escape/payload")]
    for tool in ("ws_read", "ws_write", "ws_delete"):
        args = {"path": paths[attempt]}
        if tool == "ws_write":
            args["content"] = "must not escape"
        with pytest.raises((OSError, ValueError, RuntimeError)):
            call(bench, tool, **args)
    assert target.read_text() == "untouched"


def test_hardlinks_fifos_and_symlink_directories_refused(bench, tmp_path):
    original = tmp_path / "outside"
    original.write_text("original")
    os.link(original, bench.ws.root / "hard")
    os.mkfifo(bench.ws.root / "pipe")
    for path in ("hard", "pipe"):
        with pytest.raises(PermissionError):
            call(bench, "ws_read", path=path)
        with pytest.raises(PermissionError):
            call(bench, "ws_write", path=path, content="no")
    (bench.ws.root / "link").symlink_to(tmp_path)
    with pytest.raises(OSError):
        call(bench, "ws_list", path="link")
    assert original.read_text() == "original"


def test_descriptor_walk_survives_parent_swap(bench, tmp_path, monkeypatch):
    root = bench.ws.root
    (root / "nested").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    original = app.os.open
    swapped = False
    def swapping(path, flags, *args, **kwargs):
        nonlocal swapped
        fd = original(path, flags, *args, **kwargs)
        if path == "nested" and not swapped:
            swapped = True
            (root / "nested").rename(root / "original")
            (root / "nested").symlink_to(outside)
        return fd
    monkeypatch.setattr(app.os, "open", swapping)
    call(bench, "ws_write", path="nested/file", content="safe")
    assert not list(outside.iterdir())
    assert (root / "original/file").read_text() == "safe"


@pytest.mark.parametrize("program", sorted(app.DENIED))
def test_deny_list_reaches_real_run(bench, program):
    with pytest.raises(PermissionError):
        call(bench, "run", argv=[program, "anything"])
    with pytest.raises(PermissionError):
        call(bench, "run", argv=["/usr/bin/" + program])


def test_argv_shape_alias_no_shell_and_scrubbed_environment(bench, monkeypatch):
    for argv in ([], "echo hi", [None], [""], ["python", "\0"], ["x" * 70000]):
        with pytest.raises(ValueError):
            call(bench, "run", argv=argv)
    alias = bench.ws.root / "alias"
    alias.symlink_to("/usr/bin/sudo")
    with pytest.raises(PermissionError):
        call(bench, "run", argv=[str(alias)])
    with pytest.raises(PermissionError):
        call(bench, "run", argv=["git", "push"])
    sentinel = secrets.token_hex(24)
    monkeypatch.setenv("WORKBENCH_TEST_SECRET", sentinel)
    result = call(bench, "run", argv=[sys.executable, "-c", "import os,sys;print(sys.argv[1]);print(os.environ.get('WORKBENCH_TEST_SECRET'))",
                                      "literal; $(touch forbidden) | cat"])
    assert result["exit_code"] == 0 and "literal; $(touch forbidden) | cat" in result["output"]
    assert "None" in result["output"] and sentinel not in result["output"]
    assert not (bench.ws.root / "forbidden").exists()
    for env in ({"PATH": "/tmp"}, {"LD_PRELOAD": "bad"}, {"PYTHONPATH": "bad"}, {"CI": "\0"}):
        with pytest.raises((PermissionError, ValueError)):
            call(bench, "run", argv=[sys.executable, "-V"], env=env)
    result = call(bench, "run", argv=[sys.executable, "-c", "import os;print(os.environ['NO_COLOR'])"], env={"NO_COLOR": "1"})
    assert result["output"].strip() == "1"


def test_timeout_output_file_size_and_resource_limits(bench):
    result = call(bench, "run", argv=[sys.executable, "-c", "import time;time.sleep(10)"], timeout_s=.1)
    assert result["state"] == "timed_out" and result["exit_code"] != 0
    assert .09 <= result["duration_s"] < 5
    assert set(result["usage"]) == {"user_s", "system_s", "max_rss_kib"}
    result = call(bench, "run", argv=[sys.executable, "-c", "import os;os.write(1,b'x'*70000+b'END')"])
    assert result["exit_code"] == 0 and result["output_bytes"] == 70003
    assert len(result["output"].encode()) == app.TAIL and result["output"].endswith("END")
    assert result["truncated"] and "70003" in result["note"]
    source = "import json,resource; print(json.dumps([resource.getrlimit(x) for x in [resource.RLIMIT_AS,resource.RLIMIT_CPU,resource.RLIMIT_FSIZE,resource.RLIMIT_NPROC]]))"
    result = call(bench, "run", argv=[sys.executable, "-c", source], timeout_s=2)
    assert json.loads(result["output"]) == [[bench.limits.memory_bytes]*2, [2]*2,
                                           [bench.limits.file_bytes]*2, [bench.limits.processes]*2]
    bench.limits = replace(bench.limits, file_bytes=32768)
    result = call(bench, "run", argv=[sys.executable, "-c", "import os;os.write(1,b'x'*65536)"])
    assert result["output_bytes"] <= 32768 and result["file_limit_reached"]


def test_memory_limit_actually_prevents_allocation(bench):
    bench.limits = replace(bench.limits, memory_bytes=128 * 1024**2)
    result = call(bench, "run", argv=["/usr/bin/python3", "-c", "bytearray(512*1024*1024)"], timeout_s=3)
    assert result["exit_code"] != 0
    assert "MemoryError" in result["output"]


@pytest.mark.parametrize("timeout", [0, -1, 901, float("nan"), float("inf")])
def test_timeout_validation(bench, timeout):
    with pytest.raises(ValueError):
        call(bench, "run", argv=[sys.executable, "-V"], timeout_s=timeout)


def test_job_lifecycle_concurrency_output_and_stop(bench):
    jobs = [call(bench, "job_start", argv=[sys.executable, "-u", "-c", "import time;print('started');time.sleep(20)"]) for _ in range(3)]
    assert all(call(bench, "job_status", id=j["id"])["state"] == "running" for j in jobs)
    with pytest.raises(RuntimeError, match="three"):
        call(bench, "job_start", argv=[sys.executable, "-V"])
    with pytest.raises(RuntimeError, match="three"):
        call(bench, "run", argv=[sys.executable, "-V"])
    assert len(call(bench, "info")["running_jobs"]) == 3
    deadline = time.monotonic() + 3
    while "started" not in call(bench, "job_output", id=jobs[0]["id"], tail_bytes=100)["output"]:
        assert time.monotonic() < deadline, "child never became ready"
        time.sleep(.02)
    for job in jobs:
        assert call(bench, "job_stop", id=job["id"])["state"] == "stopped"
    done = call(bench, "run", argv=[sys.executable, "-c", "print(42)"])
    assert done["state"] == "finished" and done["output"].strip() == "42"
    with pytest.raises(ValueError):
        call(bench, "job_output", id=done["id"], tail_bytes=app.TAIL + 1)
    with pytest.raises(ValueError):
        call(bench, "job_status", id="unknown")


def test_completed_job_retention(bench):
    bench.limits = replace(bench.limits, retained_jobs=2)
    first = call(bench, "run", argv=[sys.executable, "-V"])
    for _ in range(2):
        call(bench, "run", argv=[sys.executable, "-V"])
    assert len(bench.jobs) == 2
    assert not (bench.state / (first["id"] + ".log")).exists()
    with pytest.raises(ValueError):
        call(bench, "job_output", id=first["id"])


def test_audit_is_append_only_redacted_and_fail_closed(bench):
    sentinel = secrets.token_hex(32)
    call(bench, "ws_write", path="content.txt", content=sentinel)
    before = bench.audit_path.read_bytes()
    call(bench, "run", argv=[sys.executable, "-c", f"print({sentinel!r})"])
    after = bench.audit_path.read_bytes()
    assert after.startswith(before) and len(after) > len(before)
    assert sentinel.encode() not in after
    assert hashlib.sha256(sentinel.encode()).hexdigest().encode() in after
    records = [json.loads(line) for line in after.splitlines()]
    assert {"time", "tool", "arguments", "exit_code", "event"} == set(records[0])
    assert any(r["tool"] == "run" and r["exit_code"] == 0 for r in records)
    bench.limits = replace(bench.limits, audit_bytes=len(after))
    with pytest.raises(RuntimeError, match="audit capacity"):
        call(bench, "ws_write", path="must-not-exist", content="no")
    assert not (bench.ws.root / "must-not-exist").exists()


def test_kill_switch_refuses_every_tool_and_stops_active_jobs(bench):
    job = call(bench, "job_start", argv=[sys.executable, "-c", "import time;time.sleep(20)"])
    bench.kill_switch.touch()
    for name in app.TOOLS:
        with pytest.raises(PermissionError, match="paused"):
            call(bench, name)
    assert bench.lookup(job["id"])["done"].wait(3)
    assert bench.lookup(job["id"])["state"] == "stopped"
    bench.kill_switch.unlink()
    assert call(bench, "ws_list") == []


def test_file_request_response_and_search_caps(bench):
    with pytest.raises(ValueError):
        call(bench, "ws_write", path="huge", content="x" * (app.REQUEST + 1))
    (bench.ws.root / "huge").write_bytes(b"x" * (app.REQUEST + 1))
    with pytest.raises(ValueError):
        call(bench, "ws_read", path="huge")
    result = call(bench, "ws_search", pattern="x")
    assert result["skipped"] >= 1
    call(bench, "ws_write", path="lines", content="x\n" * 20)
    result = call(bench, "ws_search", pattern="x", max_results=2)
    assert result["limited"] and len(result["matches"]) == 2
    for args in ({"depth": 9}, {"depth": -1}):
        with pytest.raises(ValueError):
            call(bench, "ws_list", **args)


def test_strict_patch_creation_modification_deletion_and_no_newline(bench):
    call(bench, "ws_write", path="a.txt", content="alpha\nbeta\n")
    patch = "--- a/a.txt\n+++ b/a.txt\n@@ -1,2 +1,2 @@\n alpha\n-beta\n+gamma\n"
    assert call(bench, "ws_apply_patch", unified_diff=patch)["changed"] == ["a.txt"]
    assert bench.ws.read("a.txt") == "alpha\ngamma\n"
    call(bench, "ws_apply_patch", unified_diff="--- /dev/null\n+++ b/new\n@@ -0,0 +1 @@\n+new\n\\ No newline at end of file\n")
    assert bench.ws.read("new") == "new"
    call(bench, "ws_apply_patch", unified_diff="--- a/new\n+++ /dev/null\n@@ -1 +0,0 @@\n-new\n\\ No newline at end of file\n")
    assert not (bench.ws.root / "new").exists()
    with pytest.raises(ValueError):
        call(bench, "ws_apply_patch", unified_diff=patch)  # stale context must fail
    assert bench.ws.read("a.txt") == "alpha\ngamma\n"


@pytest.mark.parametrize("patch", [
    "--- /dev/null\n+++ b/../escape\n@@ -0,0 +1 @@\n+x\n",
    "--- /dev/null\n+++ /etc/escape\n@@ -0,0 +1 @@\n+x\n",
    "--- a/a.txt\n+++ b/renamed\n@@ -1 +1 @@\n-a\n+b\n",
    "old mode 100644\nnew mode 100755\n", "GIT binary patch\n", "",
    "--- a/a.txt\n+++ b/a.txt\n@@ -1,2 +1 @@\n-a\n+b\n",
])
def test_patch_rejects_escapes_unsupported_formats_and_bad_counts(bench, patch):
    call(bench, "ws_write", path="a.txt", content="a\n")
    with pytest.raises((ValueError, OSError)):
        call(bench, "ws_apply_patch", unified_diff=patch)
    assert bench.ws.read("a.txt") == "a\n"


def test_patch_validates_all_hunks_before_replacing_files(bench):
    call(bench, "ws_write", path="one", content="a\n")
    call(bench, "ws_write", path="two", content="b\n")
    patch = "--- a/one\n+++ b/one\n@@ -1 +1 @@\n-a\n+c\n--- a/two\n+++ b/two\n@@ -1 +1 @@\n-not-b\n+d\n"
    with pytest.raises(ValueError):
        call(bench, "ws_apply_patch", unified_diff=patch)
    assert bench.ws.read("one") == "a\n" and bench.ws.read("two") == "b\n"


def test_startup_refuses_root_and_requires_sandbox(monkeypatch):
    monkeypatch.setattr(app.os, "geteuid", lambda: 0)
    with pytest.raises(SystemExit, match="Refusing root"):
        app.main()


def test_production_launcher_hides_control_state_and_has_no_shell(bench):
    bench.sandbox = True
    argv, cwd, env = bench.command(["python3", "-V"], ".", 120, None)
    assert argv[0] == "/usr/bin/prlimit" and "/usr/bin/bwrap" in argv
    for flag in ("--unshare-all", "--share-net", "--die-with-parent", "--new-session", "--cap-drop"):
        assert flag in argv
    assert str(bench.state) not in argv and str(bench.audit_path) not in argv
    assert not any("CREDENTIAL" in key for key in env)
    assert "--bind" in argv and str(bench.ws.root) in argv


def test_test_shortcuts_call_actual_runner_with_bounded_arguments(bench, monkeypatch):
    observed = []
    def capture(argv, cwd=".", timeout_s=120, env=None):
        observed.append((argv, cwd, timeout_s, env))
        return {"exit_code": 0}
    monkeypatch.setattr(bench, "run", capture)
    call(bench, "test_python", path_or_k="tests/test_example.py")
    assert observed[-1] == (["/work/.venv/bin/python", "-m", "pytest", "-q", "tests/test_example.py"], "Star-AI", 900, {"PYTHONHASHSEED": "0"})
    call(bench, "test_python", path_or_k="unit and not slow")
    assert observed[-1][0][-2:] == ["-k", "unit and not slow"]
    call(bench, "test_frontend")
    assert observed[-1][:3] == (["npm", "test", "--", "--reporter=dot"], "Star-AI/frontend", 900)
    for selector in ("--anything", "../../escape", "/etc"):
        with pytest.raises((ValueError, PermissionError)):
            call(bench, "test_python", path_or_k=selector)


def test_repo_sync_status_diff_with_local_fixture_only(bench, tmp_path, monkeypatch):
    if not shutil.which("git"):
        pytest.skip("git not installed")
    source = tmp_path / "origin"
    source.mkdir()
    def git(*args):
        return subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *args], cwd=source,
                              capture_output=True, check=True, env={"PATH": os.defpath, "HOME": str(tmp_path)})
    git("init", "-b", "fixture")
    (source / "file").write_text("first\n")
    git("add", "file")
    git("commit", "-m", "fixture")
    real_git = bench.git
    fetches = []
    def local_transport(arguments):
        if arguments[0] == "fetch":
            assert arguments[3] == app.REPOSITORY
            fetches.append(arguments)
            arguments = ["-c", "protocol.file.allow=always", *arguments[:3], str(source), *arguments[4:]]
        return real_git(arguments)
    monkeypatch.setattr(bench, "git", local_transport)
    assert call(bench, "repo_sync", branch="fixture")["exit_code"] == 0
    assert call(bench, "repo_status")["output"] == ""
    assert (bench.ws.root / "Star-AI/file").read_text() == "first\n"
    (source / "file").write_text("second\n")
    git("commit", "-am", "fixture update")
    assert call(bench, "repo_sync", branch="fixture")["exit_code"] == 0
    assert (bench.ws.root / "Star-AI/file").read_text() == "second\n"
    call(bench, "ws_write", path="Star-AI/file", content="changed\n")
    assert "file" in call(bench, "repo_status")["output"]
    assert "+changed" in call(bench, "repo_diff")["output"]
    with pytest.raises(RuntimeError, match="dirty"):
        call(bench, "repo_sync", branch="fixture")
    assert len(fetches) == 2
    for branch in ("-option", "other;command", "../escape", "refs//heads", "branch/", "https://example.invalid/repo"):
        with pytest.raises(ValueError):
            call(bench, "repo_sync", branch=branch)


def test_frontend_preparation_does_not_need_a_lock_file_and_leaves_none(tmp_path):
    # Seen on a real install: `npm ci` exits with EUSAGE because the project has no lock file.
    assert app.frontend_install(tmp_path)[:3] == ["npm", "install", "--no-package-lock"]
    (tmp_path / "package-lock.json").write_text("{}")
    assert app.frontend_install(tmp_path)[:2] == ["npm", "ci"]
    for argv in (app.frontend_install(tmp_path), app.frontend_install(tmp_path / "absent")):
        app.validate_argv(argv)


def test_search_explicitly_reports_depth_limit(bench):
    path = "/".join(["level"] * 9) + "/deep"
    call(bench, "ws_write", path=path, content="needle")
    assert call(bench, "ws_search", pattern="needle")["limited"]
    assert call(bench, "ws_search", pattern="needle", path="level")["matches"] == []
    assert call(bench, "ws_search", pattern="needle", path="level/level")["matches"]


def test_file_limit_allows_package_and_repository_sized_files(bench):
    result = call(bench, "run", argv=[sys.executable, "-c",
                  "from pathlib import Path; Path('pack').write_bytes(b'x'*(16*1024*1024))"])
    assert result["exit_code"] == 0
    assert (bench.ws.root / "pack").stat().st_size == 16 * 1024**2
    assert bench.limits.file_bytes == 64 * 1024**2
