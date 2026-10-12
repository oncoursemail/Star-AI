"""Offline runner tests. Real VM cases skip explicitly when prerequisites are absent."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "knowledge"))
from starkb import luaurun


@pytest.mark.parametrize("fields", [
    {"code": ""}, {"code": False}, {"tests": None}, {"code": "\x00"},
    {"code": "\ud800"}, {"tests": "x" * luaurun.MAX_SOURCE_BYTES},
    {"time_limit_s": True}, {"time_limit_s": 0}, {"time_limit_s": 10.01},
    {"time_limit_s": float("nan")}, {"time_limit_s": float("inf")},
    {"memory_limit_mb": True}, {"memory_limit_mb": 31}, {"memory_limit_mb": 257},
    {"memory_limit_mb": 64.0},
])
def test_bad_inputs_never_run(fields):
    service = luaurun.RunService(enabled=True, runner=lambda *a, **k: pytest.fail("spawned"))
    status, result = service.handle({"code": "return 1", **fields}, "peer")
    assert status == 400 and result["executed"] is False


def test_defaults_and_disabled(monkeypatch):
    monkeypatch.delenv("STAR_KB_LUAU_RUN", raising=False)
    assert luaurun.validate({"code": "return 1"}) == ("return 1", "", 3.0, 256)
    service = luaurun.RunService(runner=lambda *a, **k: pytest.fail("spawned"))
    assert service.handle({"code": "return 1"}, "peer")[0] == 503
    monkeypatch.setenv("STAR_KB_LUAU_RUN", "true")
    assert not luaurun.RunService().enabled


def test_bootstrap_quotes_all_source_bytes():
    source = '\"); require("../outside"); --\n]===] café'
    bootstrap = luaurun.bootstrap(source, "assert(result == 1)")
    assert source not in bootstrap
    assert luaurun._literal(source).startswith('"\\034')
    assert 'setfenv(chunk, safe)' in bootstrap
    assert 'safe._G = safe' in bootstrap


def test_service_forwards_options_and_cleans_queue_on_failure():
    calls = []
    def runner(*args, **kwargs):
        calls.append((args, kwargs))
        raise luaurun.Unavailable("operator details must not leak")
    service = luaurun.RunService(enabled=True, runner=runner)
    for _ in range(2):
        status, result = service.handle({"code": "return 1", "tests": "assert(result == 1)",
                                         "time_limit_s": 10, "memory_limit_mb": 64}, "peer")
        assert status == 503 and "operator" not in result["error"]
    assert len(calls) == 2
    assert calls[0] == (("return 1", "assert(result == 1)"),
                        {"time_limit_s": 10.0, "memory_limit_mb": 64})


def _wait_for(predicate):
    deadline = time.monotonic() + 2
    while not predicate():
        assert time.monotonic() < deadline, "worker did not reach the queue"
        time.sleep(0.005)


def test_queue_fifo_capacity_same_client_and_cleanup():
    queue = luaurun.RunQueue(capacity=2, wait=2)
    entered, release = threading.Event(), threading.Event()
    order = []
    def worker(peer):
        with queue.slot(peer):
            order.append(peer)
            if peer == "first":
                entered.set()
                assert release.wait(2)
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(worker, "first")
        assert entered.wait(2)
        with pytest.raises(luaurun.Busy):
            with queue.slot("first"):
                pytest.fail("duplicate admitted")
        second = pool.submit(worker, "second")
        _wait_for(lambda: len(queue._waiting) == 1)
        third = pool.submit(worker, "third")
        _wait_for(lambda: len(queue._waiting) == 2)
        with pytest.raises(luaurun.Busy, match="full"):
            with queue.slot("fourth"):
                pytest.fail("over-capacity request admitted")
        with pytest.raises(luaurun.Busy):
            with queue.slot("second"):
                pytest.fail("queued duplicate admitted")
        release.set()
        for future in (first, second, third):
            future.result(timeout=2)
    assert order == ["first", "second", "third"]
    assert not queue._clients and not queue._waiting and not queue._running


def test_queue_timeout_and_exception_release():
    queue = luaurun.RunQueue(wait=0.02)
    with queue.slot("first"):
        with pytest.raises(luaurun.Busy, match="deadline"):
            with queue.slot("second"):
                pytest.fail("overlap")
    with pytest.raises(RuntimeError):
        with queue.slot("second"):
            raise RuntimeError("test")
    with queue.slot("second"):
        pass
    assert not queue._clients


@pytest.fixture(scope="module")
def probe(tmp_path_factory):
    """A real child (not a mocked Popen) exercises Linux resource enforcement."""
    cc = shutil.which("cc")
    if sys.platform != "linux" or not cc or not shutil.which("prlimit"):
        pytest.skip("Linux, prlimit and a C compiler are required for OS probes")
    directory = tmp_path_factory.mktemp("luau-limit-probe")
    source = directory / "probe.c"
    source.write_text(r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/resource.h>
int main(int argc, char **argv) {
    const char *mode = argv[1];
    if (!strcmp(mode, "loop")) { for (;;) {} }
    if (!strcmp(mode, "memory")) {
        for (;;) {
            void *p = malloc(1024 * 1024);
            if (!p) return 7;
            memset(p, 1, 1024 * 1024);
        }
    }
    if (!strcmp(mode, "output")) { for (;;) puts("0123456789abcdef"); }
    if (!strcmp(mode, "fork")) {
        pid_t p = fork();
        if (p < 0) return 0;
        if (!p) _exit(9);
        return 9;
    }
    if (!strcmp(mode, "limits")) {
        int resources[] = {RLIMIT_AS, RLIMIT_CPU, RLIMIT_FSIZE,
                           RLIMIT_NOFILE, RLIMIT_CORE, RLIMIT_NPROC};
        for (int i=0; i<6; ++i) {
            struct rlimit r; getrlimit(resources[i], &r);
            printf("%llu %llu\n", (unsigned long long)r.rlim_cur,
                                  (unsigned long long)r.rlim_max);
        }
        printf("%s\n", getenv("STAR_RUN_TEST_SECRET") ? "leaked" : "clean");
        printf("%s\n", getcwd(NULL, 0));
    }
    if (!strcmp(mode, "fail")) { fputs("code:2: assertion failed!\n", stderr); return 1; }
    return 0;
}
''', encoding="utf-8")
    binary = directory / "probe"
    subprocess.run([cc, "-O0", str(source), "-o", str(binary)], check=True, capture_output=True)
    return binary


def test_real_prlimit_all_limits_and_empty_environment(probe, tmp_path, monkeypatch):
    monkeypatch.setenv("STAR_RUN_TEST_SECRET", "must-not-be-inherited")
    result = luaurun._execute([str(probe), "limits"], tmp_path, seconds=3, memory_mb=64)
    assert result["ok"]
    lines = result["output"].splitlines()
    assert lines[:6] == [f"{64*1024*1024} {64*1024*1024}", "3 3", "65536 65536",
                         "32 32", "0 0", "0 0"]
    assert lines[6:] == ["clean", str(tmp_path)]
    assert result["usage"]["cpu_seconds"] >= 0
    assert result["usage"]["max_rss_bytes"] > 0


@pytest.mark.parametrize("mode", ["loop", "memory", "output", "fail"])
def test_actual_resource_limits(probe, tmp_path, mode):
    result = luaurun._execute([str(probe), mode], tmp_path, seconds=0.2, memory_mb=32)
    assert not result["ok"] and result["status"] == "fail"
    assert result["usage"]["wall_seconds"] < 2
    assert len(result["output"].encode("utf-8")) <= 65536
    if mode == "loop":
        assert result["timed_out"]
    elif mode == "memory":
        assert result["exit_code"] == 7  # malloc refused under RLIMIT_AS
    elif mode == "output":
        assert result["output_limited"]
    else:
        assert result["errors"] == [{"source": "code", "line": 2, "message": "assertion failed!"}]


def test_actual_fork_denied(probe, tmp_path):
    if os.geteuid() == 0:
        pytest.skip("RLIMIT_NPROC does not constrain root; public runner refuses root")
    assert luaurun._execute([str(probe), "fork"], tmp_path, seconds=1, memory_mb=32)["ok"]


def test_missing_tools_fail_closed(tmp_path):
    with pytest.raises(luaurun.Unavailable):
        luaurun.run("return 1", tools_dir=tmp_path)


def test_temp_directory_removed_on_success_and_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(luaurun, "available", lambda *a: True)
    seen = []
    def execute(argv, cwd, **kwargs):
        seen.append(cwd)
        assert (cwd / "runner.luau").is_file()
        assert set(p.name for p in cwd.iterdir()) == {"runner.luau"}
        if len(seen) == 2:
            raise OSError("test")
        return {"ok": True}
    monkeypatch.setattr(luaurun, "_execute", execute)
    assert luaurun.run("return 1", tools_dir=tmp_path)["ok"]
    with pytest.raises(OSError):
        luaurun.run("return 1", tools_dir=tmp_path)
    assert seen[0] != seen[1] and all(not p.exists() for p in seen)


@pytest.fixture
def vm():
    tools = luaurun.TOOLS_DIR
    if not luaurun.available(tools):
        pytest.skip("real standalone Luau needs STAR_LUAU_TOOLS, Linux prlimit and non-root")
    return tools


@pytest.mark.parametrize("code, tests, passed", [
    ("return 21 * 2", "assert(result == 42)", True),
    ("return 41", "assert(result == 42)", False),
    ("return 1\nlocal =", "", False),
    ("error('boom')", "", False),
    ("os.execute('exit')", "", False),
    ("io.open('outside.txt', 'w')", "", False),
    ("require('../outside')", "", False),
    ("getfenv(0).require('../outside')", "", False),
    ("loadfile('../outside')", "", False),
    ("return _G.require or _G.os or _G.io", "assert(result == nil)", True),
    ("assert(socket == nil and package == nil and debug == nil and loadstring == nil)", "", True),
])
def test_real_vm_library_boundary(vm, code, tests, passed):
    result = luaurun.run(code, tests, tools_dir=vm)
    assert result["ok"] is passed
    if not passed:
        assert result["errors"]
        assert result["errors"][0]["source"] in ("code", "tests")
        assert result["errors"][0]["line"] >= 1


@pytest.mark.parametrize("code", [
    "while true do end",
    "local t = {}; while true do table.insert(t, string.rep('x', 1024 * 1024)) end",
    "while true do print(string.rep('x', 4096)) end",
])
def test_real_vm_bombs_contained(vm, code):
    result = luaurun.run(code, time_limit_s=0.3, memory_limit_mb=32, tools_dir=vm)
    assert not result["ok"] and result["usage"]["wall_seconds"] < 2
    assert result["usage"]["output_bytes"] <= luaurun.OUTPUT_BYTES
