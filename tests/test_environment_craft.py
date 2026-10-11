"""Environment craft is deterministic, read-only and uses synthetic local images."""
from pathlib import Path

import pytest
from PIL import Image

from star.environment_craft import (PRESETS, compare_render, foliage_script,
                                    inspect_reference, lighting_recipe, main)


def _picture(path: Path, color, *, size=(160, 90), split=None):
    image = Image.new("RGB", size, color)
    if split is not None:
        from PIL import ImageDraw
        ImageDraw.Draw(image).rectangle((size[0] // 2, 0, size[0], size[1]), fill=split)
    image.save(path)
    return path


def test_inspect_is_stable_and_contains_no_fake_3d_measurements(tmp_path):
    reference = _picture(tmp_path / "reference.png", (30, 60, 120))
    first = inspect_reference(reference)
    assert first == inspect_reference(reference)
    assert first["reference"] == "reference.png"
    assert len(first["sha256"]) == 64
    assert first["size"] == [160, 90]
    assert len(first["measures"]["luminance_grid_3x3"]) == 9
    assert sum(p["share"] for p in first["measures"]["palette"]) == pytest.approx(1, abs=.001)
    assert "no scene geometry" in first["limitations"]


def test_identical_comparison_has_zero_disagreement(tmp_path):
    picture = _picture(tmp_path / "same.png", (80, 120, 150), split=(20, 20, 40))
    comparison = compare_render(picture, picture)
    assert not comparison["proposed_review"]
    assert all(number == 0 for number in comparison["metrics"].values())
    assert "not a verified 1:1" in comparison["limitations"]


def test_comparison_detects_regional_change_even_if_mean_is_similar(tmp_path):
    left = _picture(tmp_path / "left.png", (0, 0, 0), split=(255, 255, 255))
    right = _picture(tmp_path / "right.png", (255, 255, 255), split=(0, 0, 0))
    result = compare_render(left, right)
    assert result["metrics"]["pixel_rgb_mae"] > .9
    assert result["metrics"]["layout_luminance_mae"] > .65
    assert any("camera framing" in hint for hint in result["proposed_review"])


def test_rejects_wrong_aspect_ratio(tmp_path):
    wide = _picture(tmp_path / "wide.png", "white")
    square = _picture(tmp_path / "square.png", "white", size=(80, 80))
    with pytest.raises(ValueError, match="aspect ratios"):
        compare_render(wide, square)


def test_rejects_oversized_or_unknown_or_symlink(tmp_path):
    invalid = tmp_path / "not-picture.png"
    invalid.write_text("not actually a png", encoding="utf-8")
    with pytest.raises(ValueError, match="decode"):
        inspect_reference(invalid)
    invalid.write_bytes(b"x" * 20_000_001)
    with pytest.raises(ValueError, match="20 MB"):
        inspect_reference(invalid)
    valid = _picture(tmp_path / "valid.png", "navy")
    linked = tmp_path / "link.png"
    linked.symlink_to(valid)
    with pytest.raises(ValueError, match="regular file"):
        inspect_reference(linked)


def test_lighting_recipes_are_reviewable_and_never_claim_1_to_1():
    assert len(PRESETS) >= 8
    for name in PRESETS:
        luau = lighting_recipe(name)
        assert 'Lighting:FindFirstChildOfClass("Atmosphere")' in luau
        assert 'Lighting:FindFirstChild("STAR_CraftBloom")' in luau
        assert "Lighting.Technology is not scriptable" in luau
        assert 'game:GetService("Lighting")' in luau
        assert "HttpService" not in luau and "loadstring" not in luau
    with pytest.raises(ValueError, match="Unknown"):
        lighting_recipe('name"; require(1) --')


def test_foliage_script_uses_bone_weights_culling_cleanup_and_is_client_only():
    low = foliage_script("low")
    high = foliage_script("high")
    assert "MAX_DISTANCE = 100" in low and "MAX_DISTANCE = 220" in high
    assert "MAX_BONES = 128" in low and "MAX_BONES = 512" in high
    assert "Bone" in high and 'GetAttribute("WindWeight")' in high
    assert "workspace.GlobalWind" in high
    assert 'GetInstanceRemovedSignal(TAG):Connect(remove)' in high
    assert "Heartbeat" in high and "CFrame.identity" in high
    assert "ServerScriptService" not in high and "RemoteEvent" not in high
    with pytest.raises(ValueError, match="Unknown"):
        foliage_script("unbounded")


def test_cli_does_not_overwrite_and_produces_real_reports(tmp_path, capsys):
    ref = _picture(tmp_path / "img.png", (50, 100, 150))
    assert main(["inspect", str(ref)]) == 0
    assert '"edge_density_proxy"' in capsys.readouterr().out
    target = tmp_path / "lighting.luau"
    assert main(["lighting", "winter-shrine", "--out", str(target)]) == 0
    assert "Lighting.ClockTime" in target.read_text(encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(["lighting", "winter-shrine", "--out", str(target)])
    assert exc.value.code == 2
