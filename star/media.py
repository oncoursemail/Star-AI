"""Safe image ingestion for locally served multimodal models."""
import base64
import io
from pathlib import Path
from PIL import Image, ImageOps

MAX_FILE = 8 * 1024 * 1024
OWN_HARDWARE_MAX_SIDE = 1280        # default cap for pictures read by the STAR Server or the on-device brain
MAX_PIXELS = 20_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def image_part(filename: Path, max_side: int | None = None) -> dict:
    """The picture as a data URL for the model: re-encoded PNG, no metadata.

    `max_side` scales a larger picture down so its longer side is at most that many pixels.
    The file on disk is never changed; only the copy the model reads is smaller. A model on a
    processor reads a picture at roughly its pixel count (measured on the STAR Server: about
    1,000 tokens and 30 s for one megapixel), so an uncapped 2560 x 1600 screenshot took minutes.
    """
    if not filename.is_file() or filename.stat().st_size > MAX_FILE:
        raise ValueError("Image missing or larger than 8 MiB")
    with Image.open(filename) as source:
        if source.format not in {"PNG", "JPEG", "WEBP"}:
            raise ValueError("Use PNG, JPEG or WebP image")
        if getattr(source, "n_frames", 1) != 1 or source.width * source.height > MAX_PIXELS:
            raise ValueError("Animated images or images over 20 MP aren't supported")
        sanitized = ImageOps.exif_transpose(source).convert("RGB")
        if max_side and max(sanitized.size) > max_side:
            sanitized.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        sanitized.save(buffer, "PNG")
    raw = buffer.getvalue()
    if len(raw) > MAX_FILE:
        raise ValueError("Converted image is too large")
    return {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(raw).decode("ascii")}}


def mcp_images(result: dict) -> list[dict]:
    """Forward actual MCP image bytes, not a filename or a claimed screenshot."""
    images = []
    for block in result.get("content", []):
        if block.get("type") != "image":
            continue
        if len(images) >= 4:
            break
        data = block.get("data", "")
        if len(data) > MAX_FILE * 2:
            continue
        try:
            raw = base64.b64decode(data, validate=True)
            with Image.open(io.BytesIO(raw)) as im:
                if im.width * im.height > MAX_PIXELS:
                    continue
                buf = io.BytesIO()
                ImageOps.exif_transpose(im).convert("RGB").save(buf, "PNG")
                normalized = buf.getvalue()
            if len(normalized) <= MAX_FILE:
                images.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(normalized).decode("ascii")}})
        except (ValueError, OSError, TypeError):
            continue
    return images
