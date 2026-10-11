"""Voice model download: official sources only, and nothing is installed unless size and hash match."""
import hashlib
from contextlib import contextmanager

import pytest

from star.voice import setup_models
from star.voice.setup_models import MODEL_FILES, ModelFile, download, missing


def test_model_list_is_pinned_to_official_https_sources():
    assert {m.name for m in MODEL_FILES} == {"kokoro-v1.0.onnx", "voices-v1.0.bin", "silero_vad.onnx",
                                             "smart-turn-v3.2-cpu.onnx"}
    for item in MODEL_FILES:
        assert item.url.startswith(("https://github.com/thewh1teagle/kokoro-onnx/releases/download/",
                                    "https://github.com/snakers4/silero-vad/raw/v6.0/",
                                    "https://huggingface.co/pipecat-ai/smart-turn-v3/resolve/"))
        assert item.size > 1_000_000 and len(item.sha256) == 64 and int(item.sha256, 16)


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def iter_bytes(self, _size):
        yield self.body[: len(self.body) // 2]
        yield self.body[len(self.body) // 2:]


def test_download_installs_verified_files_and_rejects_tampered_ones(tmp_path, monkeypatch):
    good, bad = b"A" * 2000, b"B" * 2000
    items = (ModelFile("good.onnx", "https://example.invalid/good", len(good), hashlib.sha256(good).hexdigest(), "ok"),
             ModelFile("bad.onnx", "https://example.invalid/bad", len(bad), hashlib.sha256(b"other").hexdigest(), "no"))
    monkeypatch.setattr(setup_models, "MODEL_FILES", items)
    requested = []

    @contextmanager
    def opener(method, url, **_kwargs):
        requested.append(url)
        yield FakeResponse(good if url.endswith("good") else bad)

    assert [m.name for m in missing(tmp_path)] == ["good.onnx", "bad.onnx"]
    messages = []
    with pytest.raises(RuntimeError, match="bad.onnx did not match"):
        download(tmp_path, report=messages.append, opener=opener)
    assert (tmp_path / "good.onnx").read_bytes() == good
    assert not (tmp_path / "bad.onnx").exists() and not (tmp_path / "bad.onnx.part").exists()
    assert [m.name for m in missing(tmp_path)] == ["bad.onnx"]

    requested.clear()
    monkeypatch.setattr(setup_models, "MODEL_FILES", items[:1])
    assert download(tmp_path, report=messages.append, opener=opener) == [] and requested == []   # nothing to fetch
