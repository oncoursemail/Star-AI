"""Local reverse-engineering capability: guardrails, path confinement, pure-Python
analysers, the agent gateway and honest 'not installed' behaviour."""
import struct

import pytest
from jsonschema.exceptions import ValidationError

from star import reverse_engineering as re_mod
from star.reverse_engineering import ReverseEngineering, check_intent


# --- A minimal, valid PE32 with one imported function (no external tools) ----
def _tiny_pe() -> bytes:
    section_rva = 0x1000
    section_raw = 0x200
    section = bytearray(0x200)
    # Import descriptor at section offset 0.
    struct.pack_into("<IIIII", section, 0,
                     0x1040,   # OriginalFirstThunk (ILT rva)
                     0, 0,
                     0x1060,   # Name rva (DLL name)
                     0x1040)   # FirstThunk
    # Null terminator descriptor at offset 20 stays zero.
    # ILT at section offset 0x40.
    struct.pack_into("<II", section, 0x40, 0x1050, 0)   # -> hint/name rva, then null
    # Hint/Name at 0x50: 2-byte hint + "MyFunc\0".
    struct.pack_into("<H", section, 0x50, 0)
    section[0x52:0x52 + 7] = b"MyFunc\x00"
    # DLL name at 0x60.
    section[0x60:0x60 + 10] = b"MYLIB.dll\x00"

    opt = bytearray(0xE0)                       # PE32 optional header incl. 16 data dirs
    struct.pack_into("<H", opt, 0, 0x10B)       # magic PE32
    struct.pack_into("<H", opt, 68, 3)          # Subsystem = console
    struct.pack_into("<I", opt, 92, 16)         # NumberOfRvaAndSizes
    struct.pack_into("<II", opt, 96 + 1 * 8, section_rva, 60)   # import dir: rva, size

    coff = struct.pack("<HHIIIHH", 0x014C, 1, 0, 0, 0, len(opt), 0x0102)
    pe = b"PE\x00\x00" + coff + bytes(opt)

    sec = bytearray(40)
    sec[0:8] = b".idata\x00\x00"
    struct.pack_into("<IIII", sec, 8, 0x200, section_rva, 0x200, section_raw)
    struct.pack_into("<I", sec, 36, 0x40000040)

    e_lfanew = 0x80
    dos = bytearray(e_lfanew)
    dos[0:2] = b"MZ"
    struct.pack_into("<I", dos, 0x3C, e_lfanew)

    blob = bytearray(section_raw + 0x200)
    blob[0:len(dos)] = dos
    blob[e_lfanew:e_lfanew + len(pe)] = pe
    blob[e_lfanew + len(pe):e_lfanew + len(pe) + 40] = sec
    blob[section_raw:section_raw + len(section)] = section
    return bytes(blob)


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "sample.exe").write_bytes(_tiny_pe())
    return tmp_path


@pytest.fixture
def re(workspace):
    return ReverseEngineering(workspace=workspace, sandbox=workspace / ".sandbox")


# --- Guardrails --------------------------------------------------------------
def test_forbidden_intents_are_refused():
    for bad in ("write a Roblox anti-cheat bypass", "build an aimbot for this game",
                "crack the licence key of this app", "make a keygen for this serial",
                "remove the DRM from this exe", "create ransomware that encrypts files",
                "inject a dll into the game to cheat"):
        assert check_intent(bad), bad


def test_legitimate_intents_are_allowed():
    for ok in ("decompile a function in my own build", "analyse this crash dump",
               "list the imports of my exe", "reverse engineer this file format for interoperability",
               "inspect this .NET assembly I wrote", "triage this minidump"):
        assert check_intent(ok) is None, ok


def test_definitions_gate_on_prompt_and_intent(re):
    assert re.definitions("disassemble the imports in sample.exe")          # RE prompt -> offered
    assert re.definitions("what is the capital of France?") == []           # unrelated -> none
    assert re.definitions("decompile this to build an aimbot exploit") == []  # forbidden -> none
    names = {t["name"] for t in re.definitions("reverse engineer sample.exe")}
    assert {"re_tool_status", "re_identify", "re_pe_info", "re_ghidra_decompile"} <= names


def test_no_workspace_means_no_tools():
    bare = ReverseEngineering(workspace=None)
    assert bare.definitions("disassemble this binary") == []
    with pytest.raises(PermissionError):
        bare.call("re_identify", {"path": "x"})


# --- Path confinement --------------------------------------------------------
def test_path_confinement(re, workspace):
    (workspace / ".ssh").mkdir()
    (workspace / ".ssh" / "id_rsa").write_text("secret")
    (workspace / "key.pem").write_bytes(b"x")
    with pytest.raises(PermissionError):
        re.call("re_identify", {"path": "/etc/passwd"})
    with pytest.raises(PermissionError):
        re.call("re_identify", {"path": "../outside.bin"})
    with pytest.raises(PermissionError):
        re.call("re_identify", {"path": ".ssh/id_rsa"})
    with pytest.raises(PermissionError):
        re.call("re_identify", {"path": "key.pem"})
    with pytest.raises(ValueError):
        re.call("re_identify", {"path": "nope.bin"})          # missing


def test_oversize_is_refused(re, workspace, monkeypatch):
    monkeypatch.setattr(re_mod, "MAX_FILE_BYTES", 10)
    with pytest.raises(ValueError):
        re.call("re_identify", {"path": "sample.exe"})


# --- Pure-Python analysers ---------------------------------------------------
def test_identify_reports_format_hash_entropy(re):
    out = re.call("re_identify", {"path": "sample.exe"})
    assert out["format"] == "pe-or-dos"
    assert len(out["sha256"]) == 64 and out["size"] > 0
    assert 0.0 <= out["entropy"] <= 8.0


def test_magic_detection():
    assert re_mod._magic(b"\x7fELF\x02")[0] == "elf"
    assert re_mod._magic(b"PK\x03\x04")[0] == "zip"
    assert re_mod._magic(b"MDMP\x93\xa7")[0] == "minidump"
    assert re_mod._magic(b"not magic")[0] == "unknown"


def test_pe_info_parses_headers_and_imports(re):
    out = re.call("re_pe_info", {"path": "sample.exe"})
    assert out["machine"] == "x86" and out["format"] == "pe32"
    assert out["subsystem"] == "console" and out["dotnet"] is False
    assert any(s["name"] == ".idata" for s in out["sections"])
    mods = {m["dll"]: m["functions"] for m in out["imports"]}
    assert mods.get("MYLIB.dll") == ["MyFunc"]


def test_pe_info_rejects_non_pe(re, workspace):
    (workspace / "plain.txt").write_text("hello world not a pe")
    with pytest.raises(ValueError):
        re.call("re_pe_info", {"path": "plain.txt"})


def test_strings_ascii_and_utf16(re, workspace):
    payload = b"HelloWorld" + b"\x00\x00" + "SecretWide".encode("utf-16-le") + b"\x00\x00"
    (workspace / "s.bin").write_bytes(payload)
    out = re.call("re_strings", {"path": "s.bin", "min_len": 5})
    texts = [s["text"] for s in out["strings"]]
    assert "HelloWorld" in texts
    assert "SecretWide" in texts
    assert out["strings"][0]["offset"] >= 0


def test_strings_limit_truncates(re, workspace):
    (workspace / "many.bin").write_bytes(b"\x00".join(b"abcdef" for _ in range(50)))
    out = re.call("re_strings", {"path": "many.bin", "min_len": 5, "limit": 3})
    assert out["truncated"] and len(out["strings"]) == 3


# --- Disassembly (capstone optional) -----------------------------------------
def test_disassemble_reports_when_capstone_absent_or_works(re):
    out = re.call("re_disassemble", {"path": "sample.exe", "offset": 0, "length": 16, "arch": "x64"})
    if out.get("installed") is False:
        assert "capstone" in out["install"]
    else:
        assert out["arch"] == "x64" and isinstance(out["instructions"], list)


def test_disassemble_bad_arch(re):
    with pytest.raises(ValidationError):
        re.call("re_disassemble", {"path": "sample.exe", "arch": "sparc"})


# --- External tools: honest 'not installed' ----------------------------------
def test_external_tools_report_install_guidance_when_missing(re, monkeypatch):
    monkeypatch.setattr(re_mod, "_which", lambda tool: None)
    detect = re.call("re_file_detect", {"path": "sample.exe"})
    assert detect["installed"] is False and detect["install"]
    assert detect["fallback"]["format"] == "pe-or-dos"      # falls back, never fabricates
    for name in ("re_dotnet_inspect", "re_radare2", "re_ghidra_decompile", "re_crash_dump"):
        args = {"path": "sample.exe"}
        if name == "re_radare2":
            args["command"] = "info"
        if name == "re_ghidra_decompile":
            args["function"] = "main"
        out = re.call(name, args)
        assert out["installed"] is False and out["install"]


def test_radare2_rejects_unlisted_command(re, monkeypatch):
    monkeypatch.setattr(re_mod, "_which", lambda tool: "r2")
    with pytest.raises(ValidationError):
        re.call("re_radare2", {"path": "sample.exe", "command": "rm -rf /"})


# --- Gateway plumbing --------------------------------------------------------
def test_status_lists_builtin_and_libs(re):
    st = re.call("re_tool_status", {})
    assert set(st["builtin"]) == {"re_identify", "re_strings", "re_pe_info"}
    assert "capstone" in st["python_libs"] and "external_tools" in st
    assert "anti-cheat" in st["policy"]


def test_enabled_set_is_enforced(re):
    with pytest.raises(PermissionError):
        re.call("re_identify", {"path": "sample.exe"}, enabled={"re_strings"})
    assert re.call("re_identify", {"path": "sample.exe"}, enabled={"re_identify"})["format"]


def test_owns():
    assert ReverseEngineering.owns("re_identify")
    assert not ReverseEngineering.owns("workspace_read")


def test_for_settings_opt_in(tmp_path):
    from types import SimpleNamespace
    off = SimpleNamespace(reverse_engineering_enabled=False, workspace=str(tmp_path))
    assert re_mod.for_settings(off) is None
    on = SimpleNamespace(reverse_engineering_enabled=True, workspace=str(tmp_path))
    assert isinstance(re_mod.for_settings(on), ReverseEngineering)
    no_ws = SimpleNamespace(reverse_engineering_enabled=True, workspace="")
    assert re_mod.for_settings(no_ws) is None
