from pathlib import Path
import subprocess

import pytest

import star.local_runtime as local_runtime
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


# ---------- process lifecycle, with a fake process instead of llama-server ----------


class FakeProcess:
    """Stands in for subprocess.Popen; records how it was started and stopped."""
    started = []

    def __init__(self, argv, **kwargs):
        self.argv, self.kwargs = argv, kwargs
        self.returncode = None
        self.pid = 4000 + len(FakeProcess.started)
        self.terminated = self.killed = False
        self.ignore_terminate = False
        FakeProcess.started.append(self)

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        if not self.ignore_terminate:
            self.returncode = 0

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("llama-server", timeout)
        return self.returncode


@pytest.fixture
def fake_popen(monkeypatch):
    FakeProcess.started = []
    monkeypatch.setattr(local_runtime.subprocess, "Popen", FakeProcess)
    return FakeProcess


@pytest.fixture
def engine(tmp_path):
    exe = tmp_path / "llama-server.exe"
    exe.write_bytes(b"binary placeholder")
    model = tmp_path / "model.gguf"
    model.write_bytes(b"a" * 100_100)
    return exe, model


def test_start_runs_the_fixed_loopback_command_without_a_shell(tmp_path, engine, fake_popen):
    runtime = Runtime()
    assert runtime.status() == "not started"
    pid = runtime.start(*engine, tmp_path / "logs" / "llama.log", gpu_layers=12)
    process = fake_popen.started[0]
    assert pid == process.pid and runtime.status() == "running" and runtime.mode == "single"
    assert process.argv[process.argv.index("--host") + 1] == "127.0.0.1"
    assert "shell" not in process.kwargs and process.kwargs["stdin"] is subprocess.DEVNULL
    assert process.kwargs["stderr"] is subprocess.STDOUT and not runtime.log_file.closed
    with pytest.raises(RuntimeError, match="already running"):
        runtime.start(*engine, tmp_path / "logs" / "llama.log")
    assert len(fake_popen.started) == 1


def test_an_engine_that_exits_on_its_own_is_reported_and_its_log_closed_on_restart(tmp_path, engine, fake_popen):
    runtime = Runtime()
    runtime.start(*engine, tmp_path / "first.log")
    first_log = runtime.log_file
    fake_popen.started[0].returncode = 3                    # crashed: bad model, missing CUDA, ...
    assert runtime.status() == "exited (3)"
    runtime.start(*engine, tmp_path / "second.log")
    # Regression: the first log file stayed open (and locked on Windows) after the restart.
    assert first_log.closed and not runtime.log_file.closed
    assert runtime.log_path == tmp_path / "second.log" and runtime.status() == "running"


def test_stop_terminates_then_kills_an_engine_that_will_not_exit(tmp_path, engine, fake_popen):
    runtime = Runtime()
    runtime.start(*engine, tmp_path / "llama.log")
    process = fake_popen.started[0]
    process.ignore_terminate = True
    log = runtime.log_file
    runtime.stop()
    assert process.terminated and process.killed and log.closed
    assert runtime.status() == "not started" and runtime.mode is None and runtime.log_file is None
    runtime.stop()                                           # stopping twice is harmless


def test_a_failed_launch_closes_the_log_and_leaves_nothing_running(tmp_path, engine, monkeypatch):
    opened = []
    original_open = local_runtime.Path.open

    def tracking_open(self, *args, **kwargs):
        handle = original_open(self, *args, **kwargs)
        opened.append(handle)
        return handle

    def broken(*args, **kwargs):
        raise OSError("missing CUDA runtime")

    monkeypatch.setattr(local_runtime.Path, "open", tracking_open)
    monkeypatch.setattr(local_runtime.subprocess, "Popen", broken)
    runtime = Runtime()
    with pytest.raises(OSError):
        runtime.start(*engine, tmp_path / "llama.log")
    assert opened and opened[-1].closed and runtime.log_file is None
    assert runtime.status() == "not started" and runtime.mode is None


@pytest.mark.parametrize("limits", [
    {"port": 80}, {"port": 8080.5}, {"port": "8080"}, {"context": 256}, {"context": 4096.0},
    {"gpu_layers": -1}, {"gpu_layers": 1.5},
])
def test_arguments_accept_only_whole_numbers_in_range(engine, limits):
    with pytest.raises(ValueError, match="Invalid port"):
        Runtime.arguments(*engine, **limits)


def test_a_vision_projector_must_be_a_gguf_file(tmp_path, engine):
    projector = tmp_path / "mmproj.bin"
    projector.write_bytes(b"x")
    with pytest.raises(ValueError, match="projector"):
        Runtime.arguments(*engine, projector=projector)
    projector = tmp_path / "mmproj.gguf"
    projector.write_bytes(b"x")
    args = Runtime.arguments(*engine, projector=projector)
    assert args[-2:] == ["--mmproj", str(projector.resolve())]


def test_router_serves_one_resident_model_from_the_folder(tmp_path, engine, fake_popen):
    exe, model = engine
    models = tmp_path / "models"
    models.mkdir()
    (models / "small.gguf").write_bytes(b"a" * 100_100)
    runtime = Runtime()
    runtime.start_router(exe, models, tmp_path / "router.log", context=8192)
    argv = fake_popen.started[0].argv
    assert argv[argv.index("--models-max") + 1] == "1" and argv[argv.index("-np") + 1] == "1"
    assert argv[argv.index("--host") + 1] == "127.0.0.1" and argv[argv.index("--ctx-size") + 1] == "8192"
    assert runtime.router_running() and runtime.mode == "router"
    with pytest.raises(RuntimeError, match="Stop the current"):
        runtime.start_router(exe, models, tmp_path / "router.log")
    runtime.stop()
    assert not runtime.router_running()


@pytest.mark.parametrize("limits", [{"port": 1023}, {"context": 40000}, {"gpu_layers": True}, {"max_loaded": 2}])
def test_router_refuses_out_of_range_limits(tmp_path, engine, limits):
    models = tmp_path / "models"
    models.mkdir()
    (models / "small.gguf").write_bytes(b"a" * 100_100)
    with pytest.raises(ValueError, match="router limits"):
        Runtime.router_arguments(engine[0], models, **limits)


def test_router_refuses_a_folder_without_models_and_a_wrong_executable(tmp_path, engine):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError):
        Runtime.router_arguments(engine[0], empty)
    other = tmp_path / "server.exe"
    other.write_bytes(b"x")
    with pytest.raises(ValueError, match="llama-server.exe"):
        Runtime.router_arguments(other, empty)


def test_a_failed_router_launch_resets_the_mode(tmp_path, engine, monkeypatch):
    models = tmp_path / "models"
    models.mkdir()
    (models / "small.gguf").write_bytes(b"a" * 100_100)

    def broken(*args, **kwargs):
        raise OSError("blocked by antivirus")

    monkeypatch.setattr(local_runtime.subprocess, "Popen", broken)
    runtime = Runtime()
    with pytest.raises(OSError):
        runtime.start_router(engine[0], models, tmp_path / "router.log")
    assert runtime.mode is None and runtime.log_file is None and not runtime.router_running()
