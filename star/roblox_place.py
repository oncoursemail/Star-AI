"""Build a small Roblox place file (.rbxlx) from a folder of Luau source. No external tool needed.

Layout of the source folder (a subset of what Rojo calls a project):

    ServerScriptService/Main.server.luau      -> Script "Main"
    ReplicatedStorage/Shared/Wallet.luau      -> Folder "Shared" / ModuleScript "Wallet"
    StarterPlayer/StarterPlayerScripts/Hud.client.luau -> LocalScript "Hud"
    ServerScriptService/Shop/init.luau        -> ModuleScript "Shop" (the folder becomes the script)

Top-level folders must be Roblox services from SERVICES. `.lua` works like `.luau`. The output is the
XML place format, the same shape Rojo and Studio write: only scripts and folders, which is all a
server-side test needs. Anything with geometry, UI or assets is built with Rojo or in Studio.

Rojo is optional: `rojo_build` runs a pinned, checksum-verified binary that
scripts/fetch_rojo.py puts under STAR's data folder. Nothing here downloads anything.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import subprocess
import sys
from xml.sax.saxutils import escape, quoteattr

SERVICES = ("Workspace", "ReplicatedFirst", "ReplicatedStorage", "ServerScriptService", "ServerStorage",
            "StarterGui", "StarterPack", "StarterPlayer")
# Folders that are instances of their own class, by the path from the service.
_SPECIAL = {("StarterPlayer", "StarterPlayerScripts"): "StarterPlayerScripts",
            ("StarterPlayer", "StarterCharacterScripts"): "StarterCharacterScripts"}
_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_ .\-]{0,79}")
MAX_FILES = 400
MAX_SOURCE_BYTES = 3_000_000

# Official release, read from the GitHub API on 2026-10-11 (github.com/rojo-rbx/rojo/releases/tag/v7.7.1,
# published 2026-10-02). name -> (bytes, sha256 of the zip).
ROJO_VERSION = "7.7.1"
ROJO_RELEASE = "https://github.com/rojo-rbx/rojo/releases/download/v7.7.1/"
ROJO_ASSETS = {
    "windows-x86_64": ("rojo-7.7.1-windows-x86_64.zip", 4572329,
                       "d4dfa3493a1613a43fc87312d6dac660d7c8bf38e6a99aa5dcd0d26154ba0b82"),
    "linux-x86_64": ("rojo-7.7.1-linux-x86_64.zip", 5832480,
                     "00feb4fa0829a1dd72b49df2639da519a352bfe13cadcd83969e2ba2bb5693c4"),
}


class BuildError(ValueError):
    pass


@dataclass
class Node:
    name: str
    class_name: str
    source: str | None = None
    children: list | None = None

    def __post_init__(self):
        self.children = self.children if self.children is not None else []


@dataclass(frozen=True)
class Build:
    data: bytes
    sha256: str
    files: tuple[str, ...]        # source files that went in, relative, sorted
    instances: int
    builder: str


def _script(name: str) -> tuple[str, str] | None:
    """('Main', 'Script') for 'Main.server.luau'; None for a file that is not Luau source."""
    for suffix in (".luau", ".lua"):
        if name.endswith(suffix):
            stem = name[:-len(suffix)]
            for marker, class_name in ((".server", "Script"), (".client", "LocalScript")):
                if stem.endswith(marker):
                    return stem[:-len(marker)], class_name
            return stem, "ModuleScript"
    return None


def _read(path: Path, root: Path, files: list, budget: list) -> str:
    if path.is_symlink():
        raise BuildError(f"Links are not followed: {path.relative_to(root).as_posix()}")
    if len(files) >= MAX_FILES:
        raise BuildError("The source folder is larger than STAR builds into a test place")
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_SOURCE_BYTES - budget[0] + 1)
    except OSError:
        raise BuildError(f"Could not read script: {path.relative_to(root).as_posix()}") from None
    budget[0] += len(raw)
    if budget[0] > MAX_SOURCE_BYTES:
        raise BuildError("The source folder is larger than STAR builds into a test place")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        raise BuildError(f"Not UTF-8 text: {path.relative_to(root).as_posix()}") from None
    if "\x00" in text:
        raise BuildError(f"Not text: {path.relative_to(root).as_posix()}")
    if any((ord(char) < 32 and char not in "\t\n\r") or char in "\ufffe\uffff"
           for char in text):
        raise BuildError(f"Invalid XML character in: {path.relative_to(root).as_posix()}")
    files.append(path.relative_to(root).as_posix())
    # CRLF -> LF: a Windows (git autocrlf) checkout and a Linux one must build the same place bytes.
    # A lone CR is kept and survives XML parsing through the &#13; reference in _cdata.
    return text.replace("\r\n", "\n")


def _folder(path: Path, root: Path, trail: tuple, files: list, budget: list) -> Node:
    if path.is_symlink():
        raise BuildError(f"Links are not followed: {path.relative_to(root).as_posix()}")
    node = Node(path.name, _SPECIAL.get(trail, "Folder" if len(trail) > 1 else trail[0]))
    for child in sorted(path.iterdir(), key=lambda item: item.name):
        if child.name.startswith("."):
            continue
        if child.is_dir():
            node.children.append(_folder(child, root, (*trail, child.name), files, budget))
            continue
        kind = _script(child.name)
        if kind is None:
            continue                      # notes, JSON, images: not part of a script-only place
        name, class_name = kind
        if name == "init":
            if len(trail) < 2 or node.source is not None:
                raise BuildError(f"init script in the wrong place: {child.relative_to(root).as_posix()}")
            node.class_name, node.source = class_name, _read(child, root, files, budget)
            continue
        if not _NAME.fullmatch(name):
            raise BuildError(f"Unsupported script name: {child.relative_to(root).as_posix()}")
        node.children.append(Node(name, class_name, _read(child, root, files, budget)))
    if len(trail) > 1 and not _NAME.fullmatch(node.name):
        raise BuildError(f"Unsupported folder name: {path.relative_to(root).as_posix()}")
    names = [item.name for item in node.children]
    if len(names) != len(set(names)):
        raise BuildError(f"Two things would get the same name in {path.relative_to(root).as_posix()}")
    return node


def read_tree(source: Path) -> tuple[list[Node], list[str]]:
    source = Path(source)
    if not source.is_dir() or source.is_symlink():
        raise BuildError("The place source must be an existing folder")
    files: list[str] = []
    budget = [0]
    services = [_folder(source / name, source, (name,), files, budget)
                for name in SERVICES if (source / name).is_dir()]
    if not files:
        raise BuildError("No Luau source found. Put scripts under ServerScriptService, ReplicatedStorage, ...")
    return services, sorted(files)


def _cdata(text: str) -> str:
    # XML parsers normalize literal CR even inside CDATA; a character reference preserves it.
    return "<![CDATA[" + text.replace("]]>", "]]]]><![CDATA[>").replace(
        "\r", "]]>&#13;<![CDATA[") + "]]>"


def to_rbxlx(services: list[Node]) -> tuple[bytes, int]:
    """The XML place file. Referents are numbered in document order, so equal input gives equal bytes."""
    out = ['<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" '
           'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
           'xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">']
    count = 0

    def emit(node: Node, depth: int) -> None:
        nonlocal count
        pad = "\t" * depth
        out.append(f"{pad}<Item class={quoteattr(node.class_name)} referent=\"RBX{count:08d}\">")
        count += 1
        out.append(f"{pad}\t<Properties>")
        out.append(f"{pad}\t\t<string name=\"Name\">{escape(node.name)}</string>")
        if node.source is not None:
            out.append(f"{pad}\t\t<ProtectedString name=\"Source\">{_cdata(node.source)}</ProtectedString>")
        out.append(f"{pad}\t</Properties>")
        for child in node.children:
            emit(child, depth + 1)
        out.append(f"{pad}</Item>")

    for service in services:
        emit(service, 1)
    out.append("</roblox>")
    return ("\n".join(out) + "\n").encode("utf-8"), count


def build_place(source: Path) -> Build:
    services, files = read_tree(source)
    data, count = to_rbxlx(services)
    return Build(data, hashlib.sha256(data).hexdigest(), tuple(files), count, "star-builtin")


# --------------------------------------------------------------------------- optional: pinned Rojo

def rojo_platform() -> str:
    return "windows-x86_64" if sys.platform == "win32" else "linux-x86_64"


def rojo_binary(home: Path) -> Path:
    return Path(home) / "tools" / f"rojo-{ROJO_VERSION}" / ("rojo.exe" if sys.platform == "win32" else "rojo")


def rojo_build(home: Path, project: Path, *, timeout: float = 120.0) -> Build:
    """Build with the pinned Rojo when the owner has installed it (scripts/fetch_rojo.py)."""
    binary = rojo_binary(home)
    if not binary.is_file():
        raise BuildError(f"Rojo {ROJO_VERSION} is not installed. Run scripts/fetch_rojo.py, or use the built-in builder.")
    project = Path(project)
    if not (project / "default.project.json").is_file():
        raise BuildError("Rojo needs a default.project.json in the source folder")
    target = Path(home) / "roblox" / "builds" / "rojo-out.rbxlx"
    target.parent.mkdir(parents=True, exist_ok=True)
    done = subprocess.run([str(binary), "build", str(project), "--output", str(target)],
                          capture_output=True, text=True, timeout=timeout, cwd=str(project))
    if done.returncode != 0 or not target.is_file():
        raise BuildError("Rojo could not build the place: " + (done.stderr or done.stdout or "").strip()[-400:])
    data = target.read_bytes()
    return Build(data, hashlib.sha256(data).hexdigest(), ("default.project.json",), 0, f"rojo-{ROJO_VERSION}")
