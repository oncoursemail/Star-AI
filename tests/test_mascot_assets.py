"""The Star mascot image assets: every file named in docs/mascot/manifest.json exists in the folders it is listed for,
is a PNG of the stated size, none is larger than 1.5 MB, no unlisted file sits in the asset folders, and every image the
public website's SiteMascot.tsx loads is present."""
import json
import re
import struct
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "docs" / "mascot" / "manifest.json"
MAX_BYTES = 1_500_000
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _png_size(path: Path):
    with path.open("rb") as handle:
        head = handle.read(24)
    assert head[:8] == PNG_MAGIC, f"{path} is not a PNG"
    assert head[12:16] == b"IHDR"
    return struct.unpack(">II", head[16:24])


def _entries():
    doc = _manifest()
    for entry in doc["files"]:
        for root in entry["in"]:
            yield pytest.param(doc["roots"][root], entry, id=f"{root}:{entry['file']}")


def test_manifest_lists_the_expected_drawings():
    doc = _manifest()
    count = {}
    for entry in doc["files"]:
        count[entry["group"]] = count.get(entry["group"], 0) + 1
    assert count["faces"] == 24
    assert count["poses"] == 24
    assert count["forms"] == 8
    assert count["hero"] == 2
    assert count["pfp"] == 6
    assert set(doc["to_be_replaced"]) == {"land", "run-1", "run-2"}
    for entry in doc["files"]:
        assert entry["in"], entry["file"]
        assert set(entry["in"]) <= set(doc["roots"])
        assert (entry.get("status") == "to be replaced") == (entry["name"] in doc["to_be_replaced"]
                                                              and entry["group"] == "poses")


@pytest.mark.parametrize("root,entry", list(_entries()))
def test_file_exists_is_png_of_stated_size_and_small(root, entry):
    path = REPO / root / entry["file"]
    assert path.is_file(), f"missing {path}"
    assert _png_size(path) == tuple(entry["size"])
    assert path.stat().st_size <= MAX_BYTES, f"{path} is larger than 1.5 MB"


def test_asset_folders_contain_no_unlisted_files():
    doc = _manifest()
    for root, rel in doc["roots"].items():
        listed = {entry["file"] for entry in doc["files"] if root in entry["in"]}
        base = REPO / rel
        found = {p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file()}
        assert found == listed, f"{rel}: unlisted {sorted(found - listed)}, missing {sorted(listed - found)}"


def test_every_image_the_website_loads_exists():
    source = (REPO / "frontend" / "src" / "SiteMascot.tsx").read_text(encoding="utf-8")
    assert "const assets='./assets/mascot'" in source
    site_root = REPO / _manifest()["roots"]["site"]
    wanted = {m.lstrip("/") for m in re.findall(r"assets\+'(/[a-z0-9/_.-]+\.png)'", source)}
    wanted |= {f"faces/{face}.png" for face in re.findall(r"\{id:'([a-z-]+)',name:", source)}
    assert "star-hero.png" in wanted and "faces/normal.png" in wanted and "poses/wave-a.png" in wanted
    assert len(wanted) >= 11
    for rel in sorted(wanted):
        assert (site_root / rel).is_file(), f"the website loads ./assets/mascot/{rel} but it is missing"
