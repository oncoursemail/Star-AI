"""Safe generated-image chat previews. Full-size images stay in STAR user data."""
from __future__ import annotations
import base64
import io
from pathlib import Path
import re
from PIL import Image, ImageOps

PREFIX = "STAR_GENERATED_IMAGE:"
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,190}$")

def preview_image(path: Path) -> str:
    """Return a small thumbnail for Qt WebChannel, not the full output bytes."""
    path = path.resolve(strict=True)
    if path.stat().st_size > 25_000_000:
        raise ValueError("Generated image is too large for a chat preview")
    with Image.open(path) as opened:
        if opened.width * opened.height > 55_000_000:
            raise ValueError("Generated image dimensions exceed safety limit")
        im = ImageOps.exif_transpose(opened)
        im.thumbnail((960, 960), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        im.convert("RGB").save(out, format="WEBP", quality=76, method=4)
    return "data:image/webp;base64," + base64.b64encode(out.getvalue()).decode("ascii")

def chat_image(home: Path, body: str) -> dict | None:
    if not body.startswith(PREFIX):
        return None
    name = body[len(PREFIX):]
    if not NAME.fullmatch(name) or name in (".", ".."):
        return {"text": "Generated image unavailable (invalid reference)."}
    directory = (home / "generated-images").resolve()
    path = (directory / name).resolve()
    if not path.is_relative_to(directory) or not path.is_file():
        return {"text": "Generated image unavailable (file missing)."}
    try:
        return {"text": "Image generated locally · original saved in STAR/generated-images", "image": preview_image(path)}
    except (OSError, ValueError):
        return {"text": "Generated image saved; preview unavailable. Open STAR data folder to view."}

def generate_chat_image(settings, prompt: str, home: Path, cancel_event=None) -> dict:
    """Local, explicit ComfyUI opt-in; never downloads unreviewed custom nodes."""
    if not settings.comfy_workflow.strip():
        raise ValueError("Configure a ComfyUI API-format workflow in Settings → Image generation first.")
    if not 1 <= len(prompt.strip()) <= 1500:
        raise ValueError("Image prompt must be 1–1500 characters")
    from .comfy import generate
    output = home / "generated-images"
    images = generate(Path(settings.comfy_workflow), prompt=prompt,
                      node_id=settings.comfy_prompt_node, output=output,
                      port=settings.comfy_port, timeout_seconds=240, cancel_event=cancel_event)
    first = images[0]
    if not NAME.fullmatch(first.name):
        raise RuntimeError("Unexpected generated image filename")
    return {"answer": "Image generated locally · original saved in STAR/generated-images",
            "image": preview_image(first), "message": PREFIX + first.name}
