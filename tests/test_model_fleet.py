"""No network, model weights or GPU are required for these model-fleet tests."""
from pathlib import Path
from types import SimpleNamespace
import asyncio
import pytest

from star.model_fleet import inspect_models_dir, configured_models, probe_model_team
from star.local_runtime import Runtime
from star.desktop_core import Settings
from star.react_shell import ALLOWED_ACTIONS


def make_gguf(path: Path, size: int = 110_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'x' * size)


def test_model_directory_scans_real_files_and_projectors(tmp_path):
    root = tmp_path / "models"
    make_gguf(root / "qwen-4b.gguf")
    make_gguf(root / "large" / "qwen-27b.gguf")
    make_gguf(root / "large" / "mmproj-F16.gguf")
    inventory = inspect_models_dir(root)
    assert inventory.weights == 2
    assert inventory.projectors == 1
    assert inventory.total_bytes == 330_000
    assert inventory.directory == root.resolve()


def test_model_directory_fails_closed_without_weights_or_if_truncated(tmp_path):
    root = tmp_path / "models"
    root.mkdir()
    with pytest.raises(ValueError, match="no usable GGUF"):
        inspect_models_dir(root)
    make_gguf(root / "mmproj-F16.gguf")
    with pytest.raises(ValueError, match="no usable GGUF"):
        inspect_models_dir(root)
    (root / "tiny.gguf").write_text("invalid", encoding="utf-8")
    with pytest.raises(ValueError, match="too small"):
        inspect_models_dir(root)
    (root / "tiny.gguf").unlink()
    make_gguf(root / "usable.gguf")
    assert inspect_models_dir(root).weights == 1


def test_model_directory_blocks_symlink_escape(tmp_path):
    root = tmp_path / "models"
    root.mkdir()
    outside = tmp_path / "private"
    make_gguf(outside / "secret.gguf")
    link = root / "external"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable on this test host")
    with pytest.raises(ValueError, match="symlink"):
        inspect_models_dir(root)
    with pytest.raises(ValueError, match="symlink"):
        inspect_models_dir(link)


def test_runtime_router_arguments_limit_resident_models(tmp_path):
    exe = tmp_path / "llama-server.exe"
    exe.write_bytes(b"binary placeholder")
    root = tmp_path / "models"
    make_gguf(root / "qwen.gguf")
    args = Runtime.router_arguments(exe, root, port=8080, context=4096, gpu_layers=12)
    assert args[0] == str(exe.resolve())
    assert args[args.index("--host") + 1] == "127.0.0.1"
    assert args[args.index("--models-max") + 1] == "1"
    assert args[args.index("--models-dir") + 1] == str(root.resolve())
    assert "-m" not in args and "--jinja" in args
    assert args[args.index("-ngl") + 1] == "12"
    for kwargs in ({"max_loaded": 2}, {"context": 40000}, {"port": 80},
                   {"gpu_layers": -1}, {"context": True}):
        with pytest.raises(ValueError):
            Runtime.router_arguments(exe, root, **kwargs)


def test_runtime_router_lifecycle_no_shell_and_stop_preserves_files(tmp_path, monkeypatch):
    exe = tmp_path / "llama-server.exe"
    exe.write_bytes(b"binary")
    root = tmp_path / "models"
    make_gguf(root / "small.gguf")
    calls = []
    class FakeProcess:
        pid = 555
        returncode = 0
        stopped = False
        def poll(self):
            return 0 if self.stopped else None
        def terminate(self):
            self.stopped = True
        def wait(self, timeout=None):
            return 0
    def fake_popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return FakeProcess()
    monkeypatch.setattr("star.local_runtime.subprocess.Popen", fake_popen)
    runtime = Runtime()
    assert runtime.start_router(exe, root, tmp_path / "router.log") == 555
    assert runtime.router_running()
    assert calls[0][1]["stdin"] is not None
    assert not calls[0][1].get("shell")
    with pytest.raises(RuntimeError):
        runtime.start_router(exe, root, tmp_path / "another.log")
    runtime.stop()
    assert not runtime.router_running()
    assert runtime.status() == "not started"
    assert (root / "small.gguf").exists()


def test_new_settings_are_backward_compatible_and_scoped(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"provider":"local","model":"qwen","project":"STAR"}')
    old = Settings.load(path)
    assert old.router_models_dir == "" and old.router_context == 4096
    old.router_models_dir = str(tmp_path / "my-models")
    old.router_context = 8192
    old.gpu_layers = 8
    old.save(path)
    loaded = Settings.load(path)
    assert loaded.router_models_dir == old.router_models_dir
    assert loaded.router_context == 8192 and loaded.gpu_layers == 8
    loaded.router_context = 90000
    with pytest.raises(ValueError, match="Router context"):
        loaded.validate()
    loaded.router_context = 4096
    loaded.router_models_dir = "https://evil.example/model"
    with pytest.raises(ValueError, match="local folder"):
        loaded.validate()


def test_desktop_only_exposes_specific_router_actions():
    assert {"startModelRouter", "stopBrain", "testModelTeam"} <= ALLOWED_ACTIONS
    assert "executeShell" not in ALLOWED_ACTIONS


def settings():
    return SimpleNamespace(model="primary", fast_model="fast", reasoning_model="fast",
                           roblox_model="", vision_model="vision")


def test_model_roles_are_deduplicated_without_mutating_configuration():
    assert configured_models(settings()) == {
        "primary": "primary", "fast": "fast", "reasoning": "fast", "vision": "vision"}


def test_team_text_probes_each_model_once_and_reports_errors():
    calls = []
    async def create(*, model, **_):
        calls.append(model)
        if model == "vision":
            raise ConnectionError("redacted secret token should not be returned")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="STAR ready"))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    async def exercise():
        return await probe_model_team(client, settings())
    report = asyncio.run(exercise())
    assert calls == ["primary", "fast", "vision"]
    assert not report["all_text_ready"]
    assert report["roles"]["reasoning"]["ok"]
    assert not report["roles"]["vision"]["ok"]
    assert report["roles"]["vision"]["error_type"] == "ConnectionError"
    assert "secret token" not in str(report)
    assert "Vision" in report["note"]


def test_no_claim_that_text_probe_confirms_vision_or_studio():
    async def create(**_):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="OK"))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    result = asyncio.run(probe_model_team(client, settings()))
    assert result["all_text_ready"]
    assert "untested" in result["note"]
