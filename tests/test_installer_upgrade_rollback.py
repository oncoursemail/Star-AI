"""Issue 120: an upgrade over a running or failing STAR must leave the old STAR working.

No Inno Setup compiler or Setup run is available offline, so these checks read the real
`installer/STAR.iss`: the old runtime is moved aside (never deleted up front), Setup stops with a
message and changes nothing while a runtime file is still open, the kept copy is put back when the
installation does not finish and removed only after it has finished. The Windows workflow compiles
the script; the behaviour itself still needs the packaged acceptance run (docs/STAR_WINDOWS_ACCEPTANCE.md W04c).
"""
from pathlib import Path
import re

INSTALLER = Path(__file__).resolve().parents[1] / "installer" / "STAR.iss"


def _script() -> str:
    return INSTALLER.read_text(encoding="utf-8").replace("\r\n", "\n")


def _section(name: str) -> str:
    source = _script()
    start = re.search(rf"(?im)^\[{re.escape(name)}\][ \t]*$", source)
    assert start is not None, f"[{name}] section missing"
    rest = source[start.end():]
    if name.lower() == "code":                      # [Code] runs to the end of the file
        return rest
    end = re.search(r"(?m)^\[[A-Za-z][A-Za-z0-9_]*\][ \t]*$", rest)
    return rest[:end.start()] if end else rest


def _active(section: str) -> list[str]:
    return [line.strip() for line in section.splitlines() if line.strip() and not line.strip().startswith(";")]


def _routine(code: str, header: str) -> str:
    """The body of one Pascal procedure/function, from its header to the next routine."""
    start = code.index(header)
    following = re.search(r"(?m)^(procedure|function) ", code[start + len(header):])
    return code[start:start + len(header) + following.start()] if following else code[start:]


def _without_comments(code: str) -> str:
    return re.sub(r"\{ [^}]*\}", "", code)     # Pascal { comments }, not '{app}' or '{#STARExe}'


def test_the_old_runtime_is_never_deleted_before_the_new_one_is_copied():
    # [InstallDelete] runs before [Files] and is not undone by Setup's rollback.
    source = _script()
    if re.search(r"(?im)^\[InstallDelete\]", source):
        assert not any("_internal" in line for line in _active(_section("InstallDelete")))
    code = _without_comments(_section("Code"))
    install = _routine(code, "procedure CurStepChanged")
    moving = install.split("ssPostInstall", 1)[0]
    assert "MoveAside(RuntimeDir)" in moving and "MoveAside('{#STARExe}')" in moving
    assert "DelTree(" not in moving  # nothing live is deleted while moving aside
    move = _routine(code, "function MoveAside")
    assert "RenameFile(AppFolder + '\\' + Name, KeptPath(Name))" in move
    assert re.search(r"for Attempt := 1 to \d+ do", move) and "Sleep(" in move   # a closing STAR gets a few seconds


def test_setup_stops_and_changes_nothing_while_a_runtime_file_is_open():
    code = _without_comments(_section("Code"))
    install = _routine(code, "procedure CurStepChanged").split("ssPostInstall", 1)[0]
    # Moving the runtime fails while STAR (even elevated) holds a file: Setup refuses before copying.
    assert re.search(r"if not MoveAside\(RuntimeDir\) then\s+RefuseWhileRunning;", install)
    # The exe could not move: the runtime that did move goes back first, then Setup refuses.
    exe_failure = install.split("if not MoveAside('{#STARExe}') then", 1)[1].split("ExeMoved := True", 1)[0]
    assert "RuntimeMoved := not PutBack(RuntimeDir);" in exe_failure
    assert exe_failure.index("PutBack(RuntimeDir)") < exe_failure.index("RefuseWhileRunning")
    refuse = _routine(code, "procedure RefuseWhileRunning")
    assert "SuppressibleMsgBox(" in refuse and "Setup stopped before copying new files" in refuse
    assert refuse.rstrip().endswith("Abort;\nend;")      # Abort in ssInstall ends Setup before any file is copied
    # Restart Manager still gets the first chance to close STAR (it runs before ssInstall).
    setup = _active(_section("Setup"))
    assert "CloseApplications=yes" in setup and "RestartApplications=no" in setup


def test_a_failed_installation_puts_the_old_runtime_back_and_a_finished_one_removes_it():
    code = _without_comments(_section("Code"))
    finish = _routine(code, "procedure CurStepChanged").split("ssPostInstall", 1)[1]
    assert finish.index("InstallFinished := True") < finish.index("DelTree(KeptPath(RuntimeDir)")
    assert "DeleteFile(KeptPath('{#STARExe}'))" in finish
    restore = _routine(code, "procedure DeinitializeSetup")
    assert re.search(r"if InstallFinished then\s+Exit;", restore)
    assert re.search(r"if RuntimeMoved then\s+RuntimeMoved := not PutBack\(RuntimeDir\);", restore)
    assert re.search(r"if ExeMoved then\s+ExeMoved := not PutBack\('\{#STARExe\}'\);", restore)
    assert "if RuntimeMoved or ExeMoved then" in restore
    assert "Setup could not restore" in restore
    put_back = _routine(code, "function PutBack")
    assert put_back.index("DelTree(Live") < put_back.index("RenameFile(KeptPath(Name), Live)")


def test_leftovers_of_a_killed_setup_are_preserved_before_any_moves():
    code = _without_comments(_section("Code"))
    install = _routine(code, "procedure CurStepChanged").split("ssPostInstall", 1)[0]
    assert install.index("CheckLeftover(RuntimeDir)") < install.index("MoveAside(RuntimeDir)")
    assert install.index("CheckLeftover('{#STARExe}')") < install.index("MoveAside(RuntimeDir)")
    check = _routine(code, "procedure CheckLeftover")
    assert "DirExists(Path) or FileExists(Path)" in check and "Abort;" in check
    assert "DelTree" not in check and "DeleteFile" not in check
    uninstall = _active(_section("UninstallDelete"))
    assert 'Type: filesandordirs; Name: "{app}\\_internal.star-previous"' in uninstall
    assert 'Type: files; Name: "{app}\\{#STARExe}.star-previous"' in uninstall
    assert "KeptSuffix = '.star-previous';" in code and "RuntimeDir = '_internal';" in code


def test_the_code_only_ever_deletes_the_runtime_or_its_kept_copy():
    """Chats, models and memory live in {userappdata}\\STAR: no [Code] path may reach them or {app} itself."""
    code = _without_comments(_section("Code"))
    assert "userappdata" not in code.lower() and "{localappdata}" not in code.lower()
    deleted = re.findall(r"(?:DelTree|DeleteFile)\(((?:KeptPath\([^)]*\))|[^,)]+)", code)
    assert deleted and set(deleted) <= {"Path", "Live", "KeptPath(RuntimeDir)", "KeptPath('{#STARExe}')"}
    assert set(re.findall(r"(?:CheckLeftover|PutBack|MoveAside)\(([^)]*)\)", code)) <= {
        "RuntimeDir", "'{#STARExe}'", "const Name: String"}
    assert "AppFolder := ExpandConstant('{app}');" in code


def test_loaded_executable_and_runtime_are_checked_before_either_is_moved():
    code = _without_comments(_section("Code"))
    install = _routine(code, "procedure CurStepChanged").split("ssPostInstall", 1)[0]
    for target in ("AppFolder + '\\{#STARExe}'", "AppFolder + '\\' + RuntimeDir"):
        assert f"if not RuntimeAvailable({target}) then\n      RefuseWhileRunning;" in install
        assert install.index(f"RuntimeAvailable({target})") < install.index("MoveAside(RuntimeDir)")
    check = _routine(code, "function RuntimeAvailable")
    assert "TFileStream.Create(Path, $0012)" in check  # existing file, exclusive read/write, never create/truncate
    assert "Stream.Free;" in check and "except" in check
    assert "RuntimeAvailable(Path + '\\' + Found.Name)" in check
    assert "Found.Attributes and $400" in check  # refuse reparse points instead of following them
