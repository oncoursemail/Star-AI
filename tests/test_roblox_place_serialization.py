"""XML round-trip and filesystem boundary tests for the real built-in Roblox place builder."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from star.roblox_place import (
    MAX_FILES, MAX_SOURCE_BYTES, BuildError, build_place, read_tree, to_rbxlx,
)


def _put(root: Path, relative: str, contents: str | bytes = "return true") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents.encode("utf-8") if isinstance(contents, str) else contents)
    return path


def _parsed(build):
    root = ET.fromstring(build.data)
    assert root.tag == "roblox" and root.get("version") == "4"
    entries = []

    def visit(element, parent=""):
        name = element.findtext("./Properties/string[@name='Name']")
        assert name is not None
        item_path = parent + "/" + name if parent else name
        source = element.find("./Properties/ProtectedString[@name='Source']")
        entries.append((item_path, element.get("class"), None if source is None else source.text or ""))
        for child in element.findall("Item"):
            visit(child, item_path)

    for service in root.findall("Item"):
        visit(service)
    referents = [item.get("referent") for item in root.iter("Item")]
    assert len(referents) == len(set(referents)) == build.instances
    assert referents == [f"RBX{index:08d}" for index in range(build.instances)]
    assert hashlib.sha256(build.data).hexdigest() == build.sha256
    return entries


def test_real_builder_preserves_all_three_script_classes_and_parent_relationships(tmp_path):
    _put(tmp_path, "ServerScriptService/Game.server.lua", "print('server')")
    _put(tmp_path, "ReplicatedStorage/Shared/Stats.luau", "return {wins = 1}")
    _put(tmp_path, "ServerScriptService/Shop/init.luau", "return {}")
    _put(tmp_path, "ServerScriptService/Shop/Prices.luau", "return 25")
    _put(tmp_path, "StarterPlayer/StarterPlayerScripts/Hud.client.luau", "print('client')")
    _put(tmp_path, "StarterPlayer/StarterCharacterScripts/Animate.client.lua", "print('animate')")
    entries = _parsed(build_place(tmp_path))
    assert entries == [
        ("ReplicatedStorage", "ReplicatedStorage", None),
        ("ReplicatedStorage/Shared", "Folder", None),
        ("ReplicatedStorage/Shared/Stats", "ModuleScript", "return {wins = 1}"),
        ("ServerScriptService", "ServerScriptService", None),
        ("ServerScriptService/Game", "Script", "print('server')"),
        ("ServerScriptService/Shop", "ModuleScript", "return {}"),
        ("ServerScriptService/Shop/Prices", "ModuleScript", "return 25"),
        ("StarterPlayer", "StarterPlayer", None),
        ("StarterPlayer/StarterCharacterScripts", "StarterCharacterScripts", None),
        ("StarterPlayer/StarterCharacterScripts/Animate", "LocalScript", "print('animate')"),
        ("StarterPlayer/StarterPlayerScripts", "StarterPlayerScripts", None),
        ("StarterPlayer/StarterPlayerScripts/Hud", "LocalScript", "print('client')"),
    ]


@pytest.mark.parametrize(("name", "source"), [
    ("ascii", "return 123"),
    ("unicode", 'local s = "é 日本語 😀"\nreturn s'),
    ("xml-metacharacters", 'local s = "<&> \\" apostrophe \'" \nreturn s'),
    ("cdata-terminator", 'return "a ]]> b ]]>"'),
    ("literal-xml-looking-code", 'return "<script name=\\"x\\"> & text </script>"'),
    ("multiline", "-- first\n\n\tlocal number = 4\nreturn number\n"),
    ("carriage-returns", "local n = 1\r\nreturn n\r\n"),
    ("isolated-carriage-return", "local n = 1\rreturn n"),
    ("mixed-endings-and-cdata", 'local s = "]]>"\r\nreturn s\n'),
    ("tabs", "\treturn\ttrue\n"),
])
def test_each_valid_source_round_trips_exactly_through_xml(tmp_path, name, source):
    _put(tmp_path, f"ServerScriptService/{name}.server.luau", source)
    assert _parsed(build_place(tmp_path)) == [
        ("ServerScriptService", "ServerScriptService", None),
        (f"ServerScriptService/{name}", "Script", source.replace("\r\n", "\n")),
    ]


def test_crlf_and_lf_checkouts_build_identical_place_bytes(tmp_path):
    """git autocrlf on Windows must not change the place file or its hash."""
    lf, crlf = tmp_path / "lf", tmp_path / "crlf"
    _put(lf, "ServerScriptService/Main.server.luau", "local n = 1\nreturn n\n")
    _put(crlf, "ServerScriptService/Main.server.luau", "local n = 1\r\nreturn n\r\n")
    left, right = build_place(lf), build_place(crlf)
    assert left.data == right.data and left.sha256 == right.sha256


def test_file_order_and_bytes_do_not_depend_on_filesystem_creation_order(tmp_path):
    files = [
        ("StarterGui/Ui.client.luau", "return true"),
        ("ServerScriptService/Zeta.server.luau", "return 1"),
        ("ReplicatedStorage/Shared/A.luau", "return 2"),
        ("ServerScriptService/Alpha.server.luau", "return 3"),
    ]
    first, second = tmp_path / "first", tmp_path / "second"
    for relative, source in files:
        _put(first, relative, source)
    for relative, source in reversed(files):
        _put(second, relative, source)
    left, right = build_place(first), build_place(second)
    assert left.data == right.data and left.sha256 == right.sha256
    assert left.files == right.files == tuple(sorted(relative for relative, _ in files))
    assert _parsed(left) == _parsed(right)
    tree, paths = read_tree(first)
    data, count = to_rbxlx(tree)
    assert data == left.data and count == left.instances and tuple(paths) == left.files


def test_ignores_non_source_hidden_entries_and_unsupported_service(tmp_path):
    _put(tmp_path, "ServerScriptService/Valid.luau")
    _put(tmp_path, "ServerScriptService/notes.md", "ignore")
    _put(tmp_path, "ServerScriptService/.hidden.luau", "ignore")
    _put(tmp_path, "Workspace/.private/Hidden.luau", "ignore")
    _put(tmp_path, "OtherService/NotInstalled.server.luau", "ignore")
    result = build_place(tmp_path)
    assert result.files == ("ServerScriptService/Valid.luau",)
    assert _parsed(result) == [
        ("Workspace", "Workspace", None),
        ("ServerScriptService", "ServerScriptService", None),
        ("ServerScriptService/Valid", "ModuleScript", "return true"),
    ]


def test_utf8_bom_decodes_once_and_preserves_multibyte_source(tmp_path):
    _put(tmp_path, "ServerStorage/Bom.luau", b"\xef\xbb\xbfreturn '\xe2\x9c\x93'")
    assert _parsed(build_place(tmp_path))[-1] == (
        "ServerStorage/Bom", "ModuleScript", "return '✓'",
    )


@pytest.mark.parametrize(("files", "message"), [
    (("ServerScriptService/init.luau",), "init script"),
    (("ServerScriptService/A.luau", "ServerScriptService/A.server.luau"), "same name"),
    (("ServerScriptService/A.lua", "ServerScriptService/A.luau"), "same name"),
    (("ServerScriptService/Shop.luau", "ServerScriptService/Shop/init.luau"), "same name"),
    (("ServerScriptService/Shop/init.lua", "ServerScriptService/Shop/init.luau"), "init script"),
    (("ServerScriptService/Invalid+Name.luau",), "Unsupported script name"),
    (("ServerScriptService/Invalid+Folder/Good.luau",), "Unsupported folder name"),
])
def test_bad_names_and_init_collisions_are_controlled_failures(tmp_path, files, message):
    for relative in files:
        _put(tmp_path, relative)
    with pytest.raises(BuildError, match=message):
        build_place(tmp_path)


@pytest.mark.parametrize(("data", "message"), [
    (b"\xff\xfe", "UTF-8"),
    (b"return '\x00'", "Not text"),
    (b"return '\x01'", "XML"),
    (b"return '\x0b'", "XML"),
    ("return '\\ufffe'".replace("\\ufffe", "\ufffe").encode("utf-8"), "XML"),
])
def test_invalid_text_fails_before_emitting_unparseable_xml(tmp_path, data, message):
    _put(tmp_path, "ServerScriptService/Broken.luau", data)
    with pytest.raises(BuildError, match=message):
        build_place(tmp_path)


def test_missing_root_and_no_supported_scripts_fail_with_build_error(tmp_path):
    with pytest.raises(BuildError, match="existing folder"):
        build_place(tmp_path / "missing")
    _put(tmp_path, "UnknownService/Code.server.luau")
    with pytest.raises(BuildError, match="No Luau source"):
        build_place(tmp_path)
    with pytest.raises(BuildError, match="existing folder"):
        build_place(tmp_path / "UnknownService/Code.server.luau")


def test_source_byte_limit_rejects_oversized_single_source(tmp_path):
    # Sparse or dense file, depending on filesystem; the production reader must bound its read.
    path = _put(tmp_path, "ServerScriptService/Oversize.luau", b"")
    with path.open("wb") as stream:
        stream.truncate(MAX_SOURCE_BYTES + 1)
    with pytest.raises(BuildError, match="larger"):
        build_place(tmp_path)


def test_source_budget_counts_multiple_files(tmp_path):
    _put(tmp_path, "ServerScriptService/A.luau", "a" * (MAX_SOURCE_BYTES // 2 + 1))
    _put(tmp_path, "ServerScriptService/B.luau", "b" * (MAX_SOURCE_BYTES // 2 + 1))
    with pytest.raises(BuildError, match="larger"):
        build_place(tmp_path)


def test_maximum_file_count_is_enforced(tmp_path):
    for index in range(MAX_FILES + 1):
        _put(tmp_path, f"ServerScriptService/S{index:04d}.luau", "")
    with pytest.raises(BuildError, match="larger"):
        build_place(tmp_path)


@pytest.mark.parametrize("kind", ["source-file", "source-folder", "service-folder", "root"])
def test_symlink_traversal_is_rejected_without_reading_external_source(tmp_path, kind):
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    _put(outside, "Sensitive.luau", "return 9001")
    _put(project, "ServerScriptService/Good.luau", "return 1")
    try:
        if kind == "source-file":
            os.symlink(outside / "Sensitive.luau", project / "ServerScriptService/Linked.luau")
            root = project
        elif kind == "source-folder":
            os.symlink(outside, project / "ServerScriptService/Linked", target_is_directory=True)
            root = project
        elif kind == "service-folder":
            (project / "ServerScriptService/Good.luau").unlink()
            (project / "ServerScriptService").rmdir()
            os.symlink(outside, project / "ServerScriptService", target_is_directory=True)
            root = project
        else:
            os.symlink(project, tmp_path / "project-link", target_is_directory=True)
            root = tmp_path / "project-link"
    except (OSError, NotImplementedError):
        pytest.skip("Platform cannot create test symlinks")
    with pytest.raises(BuildError, match="Links|existing folder"):
        build_place(root)


def test_unchanged_default_is_a_script_only_xml_builder(tmp_path):
    _put(tmp_path, "ServerScriptService/Main.server.luau", "return true")
    result = build_place(tmp_path)
    assert result.builder == "star-builtin"
    assert not result.data.startswith(b"<?xml")  # Preserve the preexisting output shape.
    assert result.files == ("ServerScriptService/Main.server.luau",)
    assert result.instances == 2
    assert _parsed(result)[-1] == ("ServerScriptService/Main", "Script", "return true")
