"""Offline local builder controls: fake Git and copied PowerShell command flow.

No pip/npm/PyInstaller/EXE/installer commands are executed by these fixtures.
PowerShell retains production branches/finally; only process adapters and the
fixed external Inno path are substituted in a disposable fixture checkout.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from scripts import stamp_build_info as stamping
from star.build_info import read_build_info

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
PROFILE_NAMES = ("APPDATA", "LOCALAPPDATA", "USERPROFILE", "XDG_CONFIG_HOME",
                 "XDG_DATA_HOME", "XDG_CACHE_HOME")
ENV_NAMES = PROFILE_NAMES + ("PYTHON_KEYRING_BACKEND", "PYTHONNOUSERSITE",
                              "QT_QPA_PLATFORM", "STAR_EXPECTED_HEAD_SHA")
STAGES = ["Source verification", "Virtual environment creation", "pip upgrade",
          "Python dependency install", "Python dependency check", "React dependency install",
          "TypeScript check", "React tests", "React build", "Offline tests", "Python compilation",
          "Build provenance stamping", "PyInstaller", "Post-package source verification", "--doctor", "--ui-doctor", "--build-doctor",
          "archive", "Version lookup", "Installer packaging", "checksum", "checksum"]


def fake_git(monkeypatch, root, *, commit=SHA, dirty="", git_root=None, fail=None):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert argv[:3] == ["git", "-C", str(root.resolve())]
        assert kwargs["capture_output"] is True and kwargs["timeout"] == 15
        command = tuple(argv[3:])
        responses = {
            ("rev-parse", "--show-toplevel"): str(git_root or root),
            ("rev-parse", "HEAD"): commit,
            ("status", "--porcelain", "--untracked-files=normal"): dirty,
        }
        assert command in responses
        return subprocess.CompletedProcess(argv, 1 if command == fail else 0, responses[command], "private error")

    monkeypatch.setattr(stamping.subprocess, "run", run)
    return calls


def test_local_stamp_uses_verified_clean_git_without_workflow_claim(monkeypatch, tmp_path):
    (tmp_path / "star").mkdir()
    calls = fake_git(monkeypatch, tmp_path)
    assert stamping.stamp(tmp_path, SHA) == SHA
    raw = json.loads((tmp_path / "star/build-info.json").read_text())
    assert raw == {"schema": 1, "source_commit": SHA, "head_commit": SHA,
                   "build_event": "local_build", "run_id": ""}
    assert read_build_info(tmp_path)["run_url"] == ""
    assert len(calls) == 3
    assert not list((tmp_path / "star").glob("*.part"))


@pytest.mark.parametrize("options,expected", [
    ({"dirty": " M frontend/package-lock.json"}, "dirty"),
    ({"dirty": "?? new-source.py"}, "dirty"),
    ({"commit": "abc"}, "full source SHA"),
    ({"commit": "b" * 40}, "changed between stages"),
    ({"fail": ("rev-parse", "HEAD")}, "verification failed"),
])
def test_source_refusal_preserves_an_existing_stamp(monkeypatch, tmp_path, options, expected):
    (tmp_path / "star").mkdir()
    target = tmp_path / "star/build-info.json"
    target.write_bytes(b"original metadata")
    fake_git(monkeypatch, tmp_path, **options)
    with pytest.raises(stamping.BuildStampError, match=expected):
        stamping.stamp(tmp_path, SHA)
    assert target.read_bytes() == b"original metadata"
    assert not list((tmp_path / "star").glob("*.part"))


def test_stamper_rejects_nested_checkout_root_and_malformed_expected_sha(monkeypatch, tmp_path):
    fake_git(monkeypatch, tmp_path, git_root=tmp_path.parent)
    with pytest.raises(stamping.BuildStampError, match="exact Git checkout root"):
        stamping.verified_commit(tmp_path)
    with pytest.raises(stamping.BuildStampError, match="full lowercase"):
        stamping.verified_commit(tmp_path, "abc")


def test_check_only_never_creates_metadata(monkeypatch, tmp_path, capsys):
    fake_git(monkeypatch, tmp_path)
    assert stamping.main(["--root", str(tmp_path), "--check-only"]) == 0
    assert capsys.readouterr().out.strip() == SHA
    assert not (tmp_path / "star").exists()


def test_stamper_git_error_is_sanitized(monkeypatch, tmp_path, capsys):
    def failed(*args, **kwargs):
        raise OSError("SECRET connection detail")
    monkeypatch.setattr(stamping.subprocess, "run", failed)
    with pytest.raises(SystemExit) as caught:
        stamping.main(["--root", str(tmp_path), "--check-only"])
    assert caught.value.code == 1
    assert "SECRET" not in capsys.readouterr().err


def test_stamper_write_failure_preserves_stamp_and_removes_own_temp(monkeypatch, tmp_path):
    (tmp_path / "star").mkdir()
    target = tmp_path / "star/build-info.json"
    target.write_bytes(b"previous")
    fake_git(monkeypatch, tmp_path)
    def fail_replace(*args):
        raise OSError("denied")
    monkeypatch.setattr(stamping.os, "replace", fail_replace)
    with pytest.raises(stamping.BuildStampError, match="could not be written"):
        stamping.stamp(tmp_path)
    assert target.read_bytes() == b"previous"
    assert not list((tmp_path / "star").glob("*.part"))


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def run_flow(tmp_path, *, failure="", installer=True, doctor_null=False,
             missing_index=False, missing_setup=False, stale_setup=False,
             absent_environment=False):
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        pytest.skip("PowerShell unavailable; Python provenance controls still run")
    repo = tmp_path / "fixture"
    (repo / "scripts").mkdir(parents=True)
    (repo / "frontend/dist").mkdir(parents=True)
    if not missing_index:
        (repo / "frontend/dist/index.html").write_text("fixture")
    (repo / "dist/STAR").mkdir(parents=True)
    (repo / "dist/STAR/STAR.exe").write_text("inert fixture")
    iscc = repo / "fixture-iscc.exe"
    if installer:
        iscc.write_text("inert fixture")
    if stale_setup:
        (repo / "dist/STAR-Setup-v0.8.1.exe").write_text("previous output")
    source = (ROOT / "scripts/build_windows.ps1").read_text(encoding="utf-8")
    seam = "  & $FilePath @CommandArguments"
    external = "$iscc = 'C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe'"
    assert source.count(seam) == source.count(external) == 1
    source = source.replace(seam, "  Invoke-FakeNative $FilePath $CommandArguments $Stage")
    source = source.replace(external, "$iscc = " + ps_quote(iscc))
    (repo / "scripts/build_windows.ps1").write_text(source, encoding="utf-8")
    names = ",".join(ps_quote(name) for name in ENV_NAMES)
    harness = r"""
$ErrorActionPreference = 'Stop'
# Windows PowerShell 5.1 loads these modules on first use (the script's first Write-Host), and that
# load replaces a same-named stand-in defined below (Get-FileHash, Compress-Archive are module
# functions there). Loading them first keeps every stand-in in force on 5.1 and on PowerShell 7.
Import-Module Microsoft.PowerShell.Utility, Microsoft.PowerShell.Management, Microsoft.PowerShell.Archive -ErrorAction SilentlyContinue
$events = [System.Collections.Generic.List[object]]::new()
$names = @(__NAMES__)
$before = @{}
foreach ($name in $names) { $before[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$beforeLocation = (Get-Location).Path
function Record-Stage([string]$stage, [object]$arguments) {
  $environment = @{}
  foreach ($name in $names) { $environment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
  $events.Add(@{stage=$stage; arguments=@($arguments); environment=$environment; location=(Get-Location).Path})
}
function Get-Command {
  param([string]$Name, [object]$ErrorAction)
  if ($Name -notin @('py','npm')) { throw 'Unexpected executable lookup' }
  return @{Name=$Name}
}
function Invoke-FakeNative([string]$file, [string[]]$arguments, [string]$stage) {
  $allowed = @('Source verification','Virtual environment creation','pip upgrade','Python dependency install','Python dependency check','React dependency install','TypeScript check','React tests','React build','Offline tests','Python compilation','Build provenance stamping','PyInstaller','Post-package source verification','Version lookup','Installer packaging')
  if ($stage -notin $allowed) { throw 'Unexpected native stage' }
  if ($file -notin @('py','npm', (Join-Path __REPO__ '.venv/Scripts/python.exe'), __ISCC__)) { throw 'Unexpected native executable' }
  Record-Stage $stage $arguments
  $global:LASTEXITCODE = 0
  if ($stage -eq __FAILURE__) { $global:LASTEXITCODE = 7; return }
  if ($stage -in @('Source verification','Build provenance stamping','Post-package source verification')) { return ('a' * 40) }
  if ($stage -eq 'Version lookup') { return '0.8.1' }
  if ($stage -eq 'Installer packaging' -and -not __MISSING_SETUP__) { Set-Content -LiteralPath (Join-Path __REPO__ 'dist/STAR-Setup-v0.8.1.exe') -Value 'inert fixture' }
}
function Start-Process {
  param([string]$FilePath, [string]$ArgumentList, [string]$WindowStyle, [switch]$Wait, [switch]$PassThru)
  if ($FilePath -ne (Join-Path __REPO__ 'dist/STAR/STAR.exe') -or $ArgumentList -notin @('--doctor','--ui-doctor','--build-doctor') -or $WindowStyle -ne 'Hidden' -or -not $Wait -or -not $PassThru) { throw 'Unexpected doctor process' }
  Record-Stage $ArgumentList @($ArgumentList)
  if ($ArgumentList -eq __FAILURE__) {
    if (__NULL__) { return @{ExitCode=$null} }
    return @{ExitCode=7}
  }
  return @{ExitCode=0}
}
function Compress-Archive {
  param([string]$Path,[string]$DestinationPath,[switch]$Force)
  if ($DestinationPath -ne (Join-Path __REPO__ 'STAR-Genesis-Windows-x64.zip') -or -not $Force) { throw 'Unexpected archive output' }
  Record-Stage 'archive' @()
  if (__FAILURE__ -eq 'archive') { throw 'Fixture archive failure' }
  Set-Content -LiteralPath $DestinationPath -Value 'inert fixture'
}
function Get-FileHash {
  param([string]$LiteralPath,[string]$Algorithm)
  if ($LiteralPath -notin @((Join-Path __REPO__ 'STAR-Genesis-Windows-x64.zip'), (Join-Path __REPO__ 'dist/STAR-Setup-v0.8.1.exe')) -or $Algorithm -ne 'SHA256') { throw 'Unexpected checksum input' }
  Record-Stage 'checksum' @()
  if (__FAILURE__ -eq 'checksum') { throw 'Fixture checksum failure' }
  return @{Hash=('B' * 64)}
}
$failed = $false
try { . __SCRIPT__ } catch { $failed = $true }
$restored = @{}
foreach ($name in $names) { $restored[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
@{events=@($events.ToArray()); failed=$failed; before=$before; restored=$restored; location_restored=((Get-Location).Path -eq $beforeLocation)} | ConvertTo-Json -Depth 8 -Compress
"""
    replacements = {"__NAMES__": names, "__REPO__": ps_quote(repo), "__ISCC__": ps_quote(iscc),
                    "__FAILURE__": ps_quote(failure), "__NULL__": "$true" if doctor_null else "$false",
                    "__MISSING_SETUP__": "$true" if missing_setup else "$false",
                    "__SCRIPT__": ps_quote(repo / "scripts/build_windows.ps1")}
    for token, value in replacements.items():
        harness = harness.replace(token, value)
    script = tmp_path / "flow.ps1"
    script.write_text(harness, encoding="utf-8")
    environment = {name: os.environ[name] for name in ("SystemRoot", "WINDIR", "COMSPEC") if name in os.environ}
    for name in PROFILE_NAMES:
        environment[name] = str(tmp_path / "before" / name)
    environment.update(PYTHON_KEYRING_BACKEND="fixture.original", QT_QPA_PLATFORM="fixture.original",
                       PYTHONNOUSERSITE="0", STAR_EXPECTED_HEAD_SHA="original")
    if absent_environment:
        for name in ENV_NAMES:
            environment.pop(name, None)
    result = subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                            cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, "Copied offline PowerShell harness failed"
    record = json.loads(result.stdout.strip().splitlines()[-1])
    assert record["before"] == record["restored"]
    assert record["location_restored"]
    profiles = set()
    for event in record["events"]:
        env = event["environment"]
        for name in PROFILE_NAMES:
            path = Path(env[name]).resolve()
            assert path.is_relative_to(repo.resolve() / ".local/windows-build-profiles")
            assert env[name] != record["before"][name]
            profiles.add(path.parent)
        assert env["PYTHON_KEYRING_BACKEND"] == "keyring.backends.null.Keyring"
        assert env["QT_QPA_PLATFORM"] == "offscreen"
        assert env["PYTHONNOUSERSITE"] == "1"
        if event["stage"] in ("PyInstaller", "Post-package source verification", "--doctor", "--ui-doctor", "--build-doctor"):
            assert env["STAR_EXPECTED_HEAD_SHA"] == SHA
    assert len(profiles) == 1
    return record, repo


def test_successful_offline_command_flow_checks_packaged_artifacts_and_profiles(tmp_path):
    record, repo = run_flow(tmp_path)
    assert not record["failed"]
    assert [item["stage"] for item in record["events"]] == STAGES
    package = next(item for item in record["events"] if item["stage"] == "PyInstaller")
    assert "star/build-info.json;star" in package["arguments"]
    # This is the real local builder invoked through the inert PowerShell harness.
    assert "star/data;star/data" in package["arguments"]
    position = package["arguments"].index("keyring")
    assert package["arguments"][position - 1] == "--collect-submodules"
    stamp = next(item for item in record["events"] if item["stage"] == "Build provenance stamping")
    assert stamp["arguments"] == ["scripts/stamp_build_info.py", "--expected-commit", SHA]
    source_check = next(item for item in record["events"] if item["stage"] == "Post-package source verification")
    assert source_check["arguments"] == ["scripts/stamp_build_info.py", "--check-only", "--expected-commit", SHA]
    install = next(item for item in record["events"] if item["stage"] == "React dependency install")
    assert "--package-lock=false" in install["arguments"]
    checksums = (repo / "STAR-PREVIEW-SHA256SUMS.txt").read_text(encoding="utf-8-sig").splitlines()
    assert checksums == ["b" * 64 + "  STAR-Setup-v0.8.1.exe", "b" * 64 + "  STAR-Genesis-Windows-x64.zip"]


@pytest.mark.parametrize("failure", STAGES[:17] + ["Version lookup", "Installer packaging"])
def test_failed_stage_stops_later_commands_and_restores_profile(tmp_path, failure):
    record, repo = run_flow(tmp_path, failure=failure)
    assert record["failed"]
    assert [item["stage"] for item in record["events"]] == STAGES[:STAGES.index(failure) + 1]
    assert not (repo / "STAR-PREVIEW-SHA256SUMS.txt").exists()


def test_unknown_doctor_exit_does_not_accept_package(tmp_path):
    record, repo = run_flow(tmp_path, failure="--build-doctor", doctor_null=True)
    assert record["failed"]
    assert record["events"][-1]["stage"] == "--build-doctor"
    assert not (repo / "STAR-PREVIEW-SHA256SUMS.txt").exists()


def test_portable_only_build_checksums_only_this_runs_zip(tmp_path):
    record, repo = run_flow(tmp_path, installer=False)
    assert not record["failed"]
    assert [event["stage"] for event in record["events"]] == STAGES[:STAGES.index("archive") + 1] + ["checksum"]
    assert (repo / "STAR-PREVIEW-SHA256SUMS.txt").read_text(encoding="utf-8-sig").strip().endswith("  STAR-Genesis-Windows-x64.zip")


def test_originally_absent_environment_is_removed_after_failure(tmp_path):
    record, _ = run_flow(tmp_path, failure="PyInstaller", absent_environment=True)
    assert record["failed"]
    assert all(value in (None, "") for value in record["restored"].values())


@pytest.mark.parametrize("failure", ["archive", "checksum"])
def test_archive_or_checksum_failure_is_visible_and_restores_environment(tmp_path, failure):
    record, repo = run_flow(tmp_path, failure=failure)
    assert record["failed"]
    assert record["events"][-1]["stage"] == failure
    assert not (repo / "STAR-PREVIEW-SHA256SUMS.txt").exists()


def test_missing_frontend_bundle_stops_before_tests_or_packaging(tmp_path):
    record, repo = run_flow(tmp_path, missing_index=True)
    assert record["failed"]
    assert record["events"][-1]["stage"] == "React build"
    assert not (repo / "STAR-PREVIEW-SHA256SUMS.txt").exists()


def test_missing_installer_output_cannot_receive_a_checksum(tmp_path):
    record, repo = run_flow(tmp_path, missing_setup=True)
    assert record["failed"]
    assert record["events"][-1]["stage"] == "Installer packaging"
    assert not (repo / "STAR-PREVIEW-SHA256SUMS.txt").exists()


def test_stale_installer_output_is_refused_before_dispatch(tmp_path):
    record, repo = run_flow(tmp_path, stale_setup=True)
    assert record["failed"]
    assert record["events"][-1]["stage"] == "Version lookup"
    assert (repo / "dist/STAR-Setup-v0.8.1.exe").read_text() == "previous output"
    assert not (repo / "STAR-PREVIEW-SHA256SUMS.txt").exists()


def test_generated_artifacts_are_ignored_without_ignoring_source():
    executable = shutil.which("git")
    if not executable:
        pytest.skip("Git unavailable")
    generated = ["frontend/tsconfig.tsbuildinfo", "build/file.tmp", "dist/STAR/STAR.exe",
                 "STAR.spec", "STAR-Genesis-Windows-x64.zip", "STAR-PREVIEW-SHA256SUMS.txt",
                 "star/build-info.json"]
    source = ["frontend/package-lock.json", "star/new-source.py", "scripts/stamp_build_info.py"]
    result = subprocess.run([executable, "-C", str(ROOT), "check-ignore", "--no-index", "--stdin"],
                            input=("\n".join(generated + source) + "\n").encode("utf-8"),
                            capture_output=True, timeout=10)
    assert result.returncode == 0
    assert result.stdout.decode("utf-8").splitlines() == generated
