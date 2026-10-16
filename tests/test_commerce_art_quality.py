"""Real image bytes are checked locally; QA is not a proof of artistic quality."""
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from star.commerce.art_quality import inspect_artwork


def make_image(path: Path, size=(1280, 720), *, transparent=False):
    if transparent:
        image = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((size[0] // 5, size[1] // 5,
                        size[0] * 4 // 5, size[1] * 4 // 5),
                       fill=(255, 40, 40, 255))
    else:
        image = Image.new("RGB", size, (250, 250, 250))
        draw = ImageDraw.Draw(image)
        draw.rectangle((size[0] // 5, size[1] // 5,
                        size[0] * 4 // 5, size[1] * 4 // 5),
                       fill=(10, 20, 200))
    image.save(path)


def test_thumbnail_preflight_can_pass_geometry_but_still_requires_human_review(tmp_path):
    path = tmp_path / "thumbnail.png"
    make_image(path)
    result = inspect_artwork(path, use="fiverr_thumbnail")
    assert result["passed_deterministic_checks"]
    assert result["independent_visual_rights_and_client_review_required"]
    assert len(result["sha256"]) == 64
    assert result["width_px"] == 1280


def test_print_design_checks_alpha_and_print_size(tmp_path):
    path = tmp_path / "design.png"
    make_image(path, (2400, 3000), transparent=True)
    result = inspect_artwork(path, use="etsy_print", print_width_in=8, print_height_in=10)
    assert result["passed_deterministic_checks"]
    assert result["has_transparent_pixels"]
    assert not inspect_artwork(path, use="etsy_print",
                               print_width_in=12, print_height_in=12)["passed_deterministic_checks"]


def test_blank_and_wrong_aspect_ratio_are_flagged(tmp_path):
    path = tmp_path / "blank.png"
    Image.new("RGB", (1400, 1000), (255, 255, 255)).save(path)
    result = inspect_artwork(path, use="fiverr_thumbnail")
    assert not result["passed_deterministic_checks"]
    assert any("blank" in issue.lower() for issue in result["issues"])
    assert any("16:9" in issue for issue in result["issues"])


def test_print_art_needing_transparency_rejects_opaque(tmp_path):
    path = tmp_path / "opaque.png"
    make_image(path, (2400, 3000))
    result = inspect_artwork(path, use="etsy_print", print_width_in=8, print_height_in=10)
    assert not result["passed_deterministic_checks"]
    assert any("transparent" in issue for issue in result["issues"])


def test_unreadable_file_is_rejected(tmp_path):
    path = tmp_path / "fake.png"
    path.write_bytes(b"this is not a valid image")
    with pytest.raises(ValueError, match="decoded"):
        inspect_artwork(path, use="fiverr_thumbnail")


@pytest.mark.parametrize("size", [(None, 10), (0, 10), (8, -1), (200, 9)])
def test_physical_print_requires_sensible_size(tmp_path, size):
    path = tmp_path / "valid.png"
    make_image(path)
    with pytest.raises(ValueError, match="dimensions"):
        inspect_artwork(path, use="etsy_print", print_width_in=size[0], print_height_in=size[1])


def test_missing_image_and_invalid_kind_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="unavailable"):
        inspect_artwork(tmp_path / "missing.png", use="fiverr_thumbnail")
    with pytest.raises(ValueError, match="use must"):
        inspect_artwork(tmp_path / "missing.png", use="random")
