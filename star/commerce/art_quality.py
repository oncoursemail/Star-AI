"""Deterministic local raster preflight for Etsy print artwork and Fiverr thumbnails.

This scanner checks geometry and file integrity, NOT spelling, copyrights,
appearance, originality, design quality or whether a buyer will like the art.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import warnings
from typing import Literal

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_FILE_SIZE = 40 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000


def inspect_artwork(
    path: str | Path,
    *,
    use: Literal["etsy_print", "fiverr_thumbnail"],
    print_width_in: float | None = None,
    print_height_in: float | None = None,
    min_dpi: int = 300,
    require_transparency: bool = True,
) -> dict[str, object]:
    """Inspect a local user-selected image without writing or making network requests.

    Print sizes must be supplied in inches. Geometry checks are deterministic,
    while copyright, spelling, placement, anatomy and commercial suitability
    remain subject to independent human review.
    """
    if use not in ("etsy_print", "fiverr_thumbnail"):
        raise ValueError("use must be 'etsy_print' or 'fiverr_thumbnail'")
    source = Path(path)
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise ValueError("Image file is unavailable") from exc
    if size < 1 or size > MAX_FILE_SIZE:
        raise ValueError("Image file must be 1 byte to 40 MiB")
    if use == "etsy_print":
        if (print_width_in is None or print_height_in is None
                or not 0 < print_width_in <= 100 or not 0 < print_height_in <= 100
                or not 72 <= min_dpi <= 1200):
            raise ValueError("Provide valid print dimensions and target DPI for physical artwork")

    issues: list[str] = []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(source) as image:
                image_format = image.format or "unknown"
                width, height = image.size
                if width * height > MAX_IMAGE_PIXELS:
                    raise ValueError("Image exceeds pixel safety limit")
                if image_format not in ("PNG", "JPEG", "WEBP"):
                    issues.append("Use a PNG, JPEG or WebP output with suitable commercial rights.")
                image.load()
                rgba = image.convert("RGBA")
                alpha_min, alpha_max = rgba.getchannel("A").getextrema()
                # Composite a *small* preview onto white so transparent ink is not
                # accidentally considered the same as black/empty pixels.
                rgba.thumbnail((160, 160))
                background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                preview = Image.alpha_composite(background, rgba).convert("RGB")
                entropy = ImageOps.grayscale(preview).entropy()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ValueError("Image cannot be safely decoded") from exc

    if alpha_max == 0 or entropy < 0.15:
        issues.append("Image appears blank, uniform or completely transparent.")
    if use == "fiverr_thumbnail":
        if width < 1280 or height < 720:
            issues.append("Thumbnail is below the 1280×720 target resolution.")
        if abs((width / height) - (16 / 9)) > 0.025:
            issues.append("Thumbnail is not close enough to a 16:9 canvas.")
    else:
        assert print_width_in is not None and print_height_in is not None
        required_width = int(print_width_in * min_dpi)
        required_height = int(print_height_in * min_dpi)
        if width < required_width or height < required_height:
            issues.append(
                f"Print artwork {width}x{height} is smaller than "
                f"{required_width}x{required_height} target pixels."
            )
        if require_transparency and alpha_min == 255:
            issues.append("Print artwork needs genuine transparent areas.")
    try:
        with source.open("rb") as handle:
            file_hash = sha256(handle.read()).hexdigest()
    except OSError as exc:
        raise ValueError("Image file became unreadable") from exc
    return {
        "classification": "local_raster_preflight_not_artwork_approval",
        "use": use,
        "width_px": width,
        "height_px": height,
        "file_format": image_format,
        "has_transparent_pixels": alpha_min < 255,
        "sha256": file_hash,
        "issues": issues,
        "passed_deterministic_checks": not issues,
        "independent_visual_rights_and_client_review_required": True,
        "checks_not_performed": [
            "Typography, spelling, anatomy, palette or design quality",
            "Originality, licensing, trademarks, likeness and client permissions",
            "Physical print sample, texture, print-provider color and placement",
        ],
    }
