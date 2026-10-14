from pathlib import Path
import pytest
from star.local_runtime import Runtime


def test_local_runtime_args(tmp_path):
    exe=tmp_path/'llama-server.exe';exe.write_bytes(b'binary placeholder')
    gguf=tmp_path/'vision.gguf';gguf.write_bytes(b'a'*100100)
    args=Runtime.arguments(exe,gguf,port=8080,context=4096,gpu_layers=20)
    assert '--host' in args and '127.0.0.1' in args
    assert args[args.index('-ngl')+1]=='20'
    assert args.count('--jinja')==1


def test_local_runtime_refuses_nonserver_exe(tmp_path):
    exe=tmp_path/'somefile.exe';exe.write_bytes(b'binary')
    gguf=tmp_path/'vision.gguf';gguf.write_bytes(b'a'*100100)
    with pytest.raises(ValueError):Runtime.arguments(exe,gguf)


def test_local_runtime_refuses_bad_model(tmp_path):
    exe=tmp_path/'llama-server.exe';exe.write_bytes(b'x')
    model=tmp_path/'model.gguf';model.write_bytes(b'bad')
    with pytest.raises(ValueError):Runtime.arguments(exe,model)


# -- stopping does not freeze the UI thread ---------------------------------------------------------------------
import subprocess
import threading

from star import local_runtime


class SlowProcess:
    """A llama-server stand-in that takes as long to exit as the test wants (`release`)."""
    def __init__(self, exits_on_terminate=False):
        self.release = threading.Event()
        self.terminated = threading.Event()
        self.exits_on_terminate = exits_on_terminate
        self.returncode = None
        self.pid = 4242

    def poll(self):
        return 0 if self.release.is_set() else None

    def terminate(self):
        self.terminated.set()
        if self.exits_on_terminate:
            self.release.set()

    def kill(self):
        self.release.set()

    def wait(self, timeout=None):
        if not self.release.wait(timeout):
            raise subprocess.TimeoutExpired("llama-server", timeout)
        self.returncode = 0
        return 0


def _call_soon(function, limit=1.0):
    """Run `function` on another thread; its result, or 'BLOCKED' if it did not return within `limit` s."""
    box = []
    worker = threading.Thread(target=lambda: box.append(function()), daemon=True)
    worker.start()
    worker.join(limit)
    return box[0] if box else "BLOCKED"


def test_status_answers_while_stop_waits_for_the_process(tmp_path):
    runtime = Runtime()
    process = SlowProcess()
    runtime.process, runtime.mode = process, "router"
    runtime.log_file = (tmp_path / "brain.log").open("ab")
    log = runtime.log_file
    stopper = threading.Thread(target=runtime.stop, daemon=True)
    stopper.start()
    assert process.terminated.wait(2)
    assert _call_soon(runtime.status) == "stopping"
    assert _call_soon(runtime.router_running) is False
    with pytest.raises(RuntimeError, match="still stopping"):
        runtime.start(tmp_path / "llama-server.exe", tmp_path / "m.gguf", tmp_path / "brain.log")
    process.release.set()
    stopper.join(2)
    assert not stopper.is_alive()
    assert runtime.status() == "not started" and runtime.mode is None
    assert log.closed and runtime.log_file is None


def test_a_second_stop_waits_for_the_first(tmp_path):
    runtime = Runtime()
    process = SlowProcess()
    runtime.process = process
    first = threading.Thread(target=runtime.stop, daemon=True)
    first.start()
    assert process.terminated.wait(2)
    second_done = threading.Event()
    second = threading.Thread(target=lambda: (runtime.stop(), second_done.set()), daemon=True)
    second.start()
    assert not second_done.wait(0.3)          # still waiting: the process has not exited
    process.release.set()
    assert second_done.wait(2)
    first.join(2)
    assert runtime.status() == "not started"


def test_starting_again_after_a_crash_closes_the_old_log(tmp_path, monkeypatch):
    runtime = Runtime()
    crashed = SlowProcess()
    crashed.release.set()
    runtime.process = crashed
    old_log = (tmp_path / "old.log").open("ab")
    runtime.log_file = old_log
    started = []
    monkeypatch.setattr(Runtime, "arguments", staticmethod(lambda *a, **k: ["llama-server.exe"]))
    monkeypatch.setattr(local_runtime.subprocess, "Popen",
                        lambda argv, **kwargs: started.append(argv) or SlowProcess())
    assert runtime.start(tmp_path / "llama-server.exe", tmp_path / "m.gguf", tmp_path / "new.log") == 4242
    assert old_log.closed
    assert started == [["llama-server.exe"]] and runtime.status() == "running"
    runtime.process.release.set()
    runtime.stop()
