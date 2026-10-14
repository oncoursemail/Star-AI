"""Download the pinned Rojo release for STAR's headless Roblox pipeline. Optional.

STAR builds small script-only test places by itself (star/roblox_place.py). Rojo is only needed for
places with geometry, UI or assets described by a default.project.json.

    python scripts/fetch_rojo.py            # shows what would be downloaded, downloads nothing
    python scripts/fetch_rojo.py --yes      # downloads, checks size and SHA-256, unpacks the one binary

Source: the official release page github.com/rojo-rbx/rojo/releases (version and checksums are pinned
in star/roblox_place.py). The file is refused unless its size and SHA-256 match the pinned values.
"""
from __future__ import annotations

import argparse
import hashlib
import io
from pathlib import Path
import sys
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from star.roblox_place import ROJO_ASSETS, ROJO_RELEASE, ROJO_VERSION, rojo_binary, rojo_platform  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--yes", action="store_true", help="download and install")
    parser.add_argument("--home", type=Path, help="STAR data folder (default: the desktop app's)")
    arguments = parser.parse_args()
    if arguments.home is None:
        from star.desktop_core import app_data
        arguments.home = app_data()
    name, size, digest = ROJO_ASSETS[rojo_platform()]
    target = rojo_binary(arguments.home)
    print(f"Rojo {ROJO_VERSION}: {name}, {size:,} bytes, from {ROJO_RELEASE}")
    print(f"SHA-256 {digest}\nInstalls to {target}")
    if target.is_file():
        print("Already installed.")
        return 0
    if not arguments.yes:
        print("Nothing downloaded. Run again with --yes to download.")
        return 0
    with urllib.request.urlopen(ROJO_RELEASE + name, timeout=120) as response:   # noqa: S310 (fixed https URL)
        data = response.read(size + 1)
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        print("Refused: the download does not match the pinned size and SHA-256.")
        return 1
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        member = next((item for item in archive.namelist() if Path(item).name == target.name), None)
        if member is None:
            print("Refused: the archive does not contain " + target.name)
            return 1
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(member))
    if sys.platform != "win32":
        target.chmod(0o755)
    print("Installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
