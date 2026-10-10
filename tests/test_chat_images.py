"""Generated media previews never turn untrusted file paths into URL access."""
import base64
import io
from pathlib import Path
from PIL import Image
from star.chat_images import PREFIX, chat_image, preview_image

def test_generated_image_message_is_restored(tmp_path):
    folder=tmp_path/"generated-images"
    folder.mkdir()
    image=folder/"test-output.png"
    Image.new("RGB",(2000,1800),(32,55,72)).save(image)
    item=chat_image(tmp_path,PREFIX+image.name)
    assert item["image"].startswith("data:image/webp;base64,")
    decoded=base64.b64decode(item["image"].split(",",1)[1])
    opened=Image.open(io.BytesIO(decoded))
    assert opened.width <= 960 and opened.height <= 960

def test_previews_cannot_escape_generated_folder(tmp_path):
    assert "invalid" in chat_image(tmp_path,PREFIX+"../secrets.txt")["text"]
    assert "missing" in chat_image(tmp_path,PREFIX+"no-image.png")["text"]
    assert chat_image(tmp_path,"ordinary chat text") is None
