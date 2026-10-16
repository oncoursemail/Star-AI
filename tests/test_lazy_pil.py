"""Pillow loads on first image use, not when the desktop starts (proposal #325 item 21).

STAR's decompression-bomb limit (20 megapixels) used to be set as a side effect of importing star.media at
start-up. It is now set by star/pil_safe.py, the only way STAR modules reach PIL.Image, so it is in place
before any STAR code opens a picture.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("media", "chat_images", "image_gen", "diagnostics", "references", "roblox_research", "environment_craft")


def run(code: str, tmp_path) -> list:
    env = {**os.environ, "APPDATA": str(tmp_path), "XDG_DATA_HOME": str(tmp_path)}
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True,
                         check=True, timeout=180)
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("module", ["star.react_shell", "star.desktop_core", "star.agent"])
def test_desktop_start_up_does_not_import_pillow(module, tmp_path):
    assert run(f"import sys, json\nimport {module}\nprint(json.dumps('PIL' in sys.modules))", tmp_path) is False


def test_every_picture_module_gets_pillow_with_the_pixel_limit(tmp_path):
    code = ("import json, importlib\n"
            f"limits = [importlib.import_module('star.' + m).Image.MAX_IMAGE_PIXELS for m in {MODULES!r}]\n"
            "import PIL.Image\nprint(json.dumps(limits + [PIL.Image.MAX_IMAGE_PIXELS]))")
    assert run(code, tmp_path) == [20_000_000] * (len(MODULES) + 1)


def test_reading_a_picture_works_and_applies_the_limit_first(tmp_path):
    picture = tmp_path / "p.png"
    code = ("import json\nfrom pathlib import Path\n"
            "import PIL.Image as raw\nraw.new('RGB', (40, 30), (200, 10, 10)).save(" + repr(str(picture)) + ")\n"
            "raw.MAX_IMAGE_PIXELS = 1\n"            # Pillow loaded first, by someone else: STAR's first use still sets it
            "from star import media\npart = media.image_part(Path(" + repr(str(picture)) + "))\n"
            "print(json.dumps([part['type'], raw.MAX_IMAGE_PIXELS]))")
    assert run(code, tmp_path) == ["image_url", 20_000_000]
