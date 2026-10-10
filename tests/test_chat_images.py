"""Chat-generated media is safe, durable and scoped to a conversation."""
import base64
import io

import pytest
from PIL import Image

from star.chat_images import PREFIX, chat_image, generate_chat_image, preview_image
from star.desktop_core import Conversations, Settings


def test_image_preview_restores_in_chat(tmp_path):
    output = tmp_path / "generated-images"
    output.mkdir()
    path = output / "example.png"
    Image.new("RGB", (1900, 1800), (38, 48, 60)).save(path)
    restored = chat_image(tmp_path, PREFIX + path.name)
    assert restored["image"].startswith("data:image/webp;base64,")
    decoded = base64.b64decode(restored["image"].split(",", 1)[1])
    with Image.open(io.BytesIO(decoded)) as picture:
        assert picture.width <= 820 and picture.height <= 820


def test_untrusted_image_refs_cannot_traverse(tmp_path):
    assert "invalid" in chat_image(tmp_path, PREFIX + "../secret.txt")["text"]
    assert "missing" in chat_image(tmp_path, PREFIX + "unknown.png")["text"]
    assert chat_image(tmp_path, "Ordinary STAR response") is None


def test_generated_image_persists_in_originating_thread(tmp_path, monkeypatch):
    workflow = tmp_path / "workflow.json"
    workflow.write_text('{"6": {"class_type": "CLIPTextEncode", "inputs": {"text": "test"}}}')
    settings = Settings(comfy_workflow=str(workflow), comfy_prompt_node="6", comfy_port=8188)

    def generate_fake(_path, *, prompt, node_id, output, **_kwargs):
        output.mkdir(parents=True, exist_ok=True)
        result = output / "fake-output.png"
        Image.new("RGB", (640, 480), (18, 40, 55)).save(result)
        return [result]

    monkeypatch.setattr("star.comfy.generate", generate_fake)
    db = Conversations(tmp_path / "chats.sqlite")
    try:
        origin = db.active_chat("My project")
        result = generate_chat_image(settings, "a stylized starship", tmp_path)
        db.add("My project", "user", "a stylized starship", chat_id=origin)
        db.add("My project", "assistant", result["message"], chat_id=origin)
        other = db.new_chat("My project")
        assert db.recent("My project", chat_id=other) == []
        history = db.recent("My project", chat_id=origin)
        assert history[-1][1].startswith(PREFIX)
        assert chat_image(tmp_path, history[-1][1])["image"].startswith("data:image/")
    finally:
        db.close()


def test_invalid_workflow_and_settings_rejected(tmp_path):
    settings = Settings(comfy_workflow=str(tmp_path / "missing.json"))
    with pytest.raises(FileNotFoundError):
        generate_chat_image(settings, "create a sunset", tmp_path)
    with pytest.raises(ValueError):
        Settings(comfy_port=0).validate()
    with pytest.raises(ValueError):
        Settings(comfy_prompt_node="../secret").validate()
