"""The Star mascot image assets: every file named in docs/mascot/manifest.json exists in the folder it is listed for,
is a PNG of the stated size, none is larger than 1.5 MB, no unlisted file sits in the asset folders, and every image the
website (SiteMascot.tsx) and the chat pet (StarPet.tsx) load is present in the ONE shipped folder
frontend/public/assets/mascot. That folder holds exactly what the code loads and nothing else: the rest of the approved art
is kept under docs/mascot/art, which is not copied into the app or the installer."""
import json
import re
import struct
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "docs" / "mascot" / "manifest.json"
MAX_BYTES = 1_500_000
MAX_SHIPPED_BYTES = 6_000_000  # was about 24 MB when the art was stored twice and unused art was shipped
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
    # fix sheet 3 replaced land, run-1, run-2 and point (docs/mascot/ASSETS.md): nothing is pending replacement any more
    assert doc["to_be_replaced"] == []
    assert set(doc["poses_from_fix_sheet_3"]) == {"land", "point", "run-1", "run-2"}
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


def _images_loaded_by_the_code():
    """Relative paths (under the shipped folder) of every image SiteMascot.tsx and StarPet.tsx can request."""
    site_source = (REPO / "frontend" / "src" / "SiteMascot.tsx").read_text(encoding="utf-8")
    pet_source = (REPO / "frontend" / "src" / "StarPet.tsx").read_text(encoding="utf-8")
    for source in (site_source, pet_source):
        assert "const assets='./assets/mascot'" in source
    wanted = {m.lstrip("/") for m in re.findall(r"assets\+'(/[a-z0-9/_.-]+\.png)'", site_source)}
    wanted |= {f"faces/{face}.png" for face in re.findall(r"\{id:'([a-z-]+)',name:", site_source)}
    # The pet displays full-body art only, through an explicit static pose allowlist.
    # Face names in petImage describe expressions/status, not separate downloaded sprites.
    match = re.search(r"const poses=\[(.*?)\] as const", pet_source)
    assert match, "pet sprite allowlist is required"
    assert "petPosePath(image.pose)" in pet_source
    names = set(re.findall(r"'([a-z0-9-]+)'", match.group(1)))
    assert {"stand", "blink", "breathe-out", "wave-a", "wave-b", "think", "jump"} <= names
    wanted |= {f"poses/{name}.png" for name in names}
    return wanted


def test_every_image_the_website_and_the_pet_load_exists():
    site_root = REPO / _manifest()["roots"]["site"]
    wanted = _images_loaded_by_the_code()
    assert {"star-hero.png", "faces/normal.png", "poses/stand.png", "poses/blink.png",
            "poses/breathe-out.png", "poses/wave-a.png", "poses/wave-b.png",
            "poses/think.png", "poses/jump.png", "poses/letter.png"} <= wanted
    assert len(wanted) >= 19
    for rel in sorted(wanted):
        assert (site_root / rel).is_file(), f"the app loads ./assets/mascot/{rel} but it is missing"


def test_shipped_folder_holds_exactly_what_the_code_loads_and_stays_small():
    doc = _manifest()
    site_root = REPO / doc["roots"]["site"]
    shipped = {p.relative_to(site_root).as_posix() for p in site_root.rglob("*") if p.is_file()}
    assert shipped == _images_loaded_by_the_code(), "shipping an image no code loads (or loading one that is not shipped)"
    size = sum((site_root / rel).stat().st_size for rel in shipped)
    assert size == doc["shipped_bytes"]
    assert size <= MAX_SHIPPED_BYTES, f"the shipped art is {size} bytes"


def test_art_not_loaded_by_the_code_is_kept_outside_the_app():
    doc = _manifest()
    art_root = REPO / doc["roots"]["art"]
    assert doc["roots"]["art"].startswith("docs/")
    shipped_names = _images_loaded_by_the_code()
    kept = {p.relative_to(art_root).as_posix() for p in art_root.rglob("*") if p.is_file()}
    assert kept, "the unused art must stay in the repository"
    assert not (kept & shipped_names), "an image is stored twice"
    # one copy only: the old second folder must be gone and no code may point at it
    assert not (REPO / "frontend" / "public" / "mascot").exists()
    for source in (REPO / "frontend" / "src").glob("*.ts*"):
        text = source.read_text(encoding="utf-8")
        assert "'./mascot/" not in text and '"./mascot/' not in text, f"{source.name} loads from the removed ./mascot folder"
