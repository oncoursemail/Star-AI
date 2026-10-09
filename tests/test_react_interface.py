"""Offline guards for STAR's real React desktop migration.

These tests don't pretend the browser or GPU has been verified: Windows CI
builds TypeScript and launches the native desktop smoke test separately.
"""
from pathlib import Path
import json
import pytest
from star.react_shell import ALLOWED_ACTIONS, file_allowed, react_index, sanitize_event
from star.version import __version__

ROOT=Path(__file__).resolve().parents[1]

def test_react_version_matches_python():
    package=json.loads((ROOT/'frontend/package.json').read_text())
    assert package['version']==__version__
    installer=(ROOT/'installer/STAR.iss').read_text()
    assert f'"{__version__}"' in installer

def test_react_default_and_native_fallback():
    src=(ROOT/'star_desktop.py').read_text()
    assert 'from star.react_shell import launch' in src
    assert "'--legacy-ui'" in src
    assert react_index(ROOT)==ROOT/'frontend/dist/index.html'

def test_webchannel_no_arbitrary_filesystem_or_shell_commands():
    assert 'sendMessage' in ALLOWED_ACTIONS
    assert 'installBrain' in ALLOWED_ACTIONS
    assert 'discoverStudio' in ALLOWED_ACTIONS
    assert 'openLegacy' in ALLOWED_ACTIONS
    assert 'runShell' not in ALLOWED_ACTIONS
    assert 'deleteAllFiles' not in ALLOWED_ACTIONS
    assert 'getGitHubToken' not in ALLOWED_ACTIONS

def test_attachment_registry_is_required(tmp_path):
    p=tmp_path/'reference.png'
    p.write_bytes(b'img')
    with pytest.raises(PermissionError):file_allowed(p,set())
    assert file_allowed(p,{p})==p

def test_model_tool_event_redacted():
    data=sanitize_event({'event':'tool_output','content':'secret'})
    assert 'secret' not in str(data)

def test_react_assets_and_reduced_motion():
    css=(ROOT/'frontend/src/styles.css').read_text()
    assert 'prefers-reduced-motion' in css
    assert 'font-family' in css
    assert 'OLED' in (ROOT/'docs/STAR_REACT_REDESIGN.md').read_text()

def test_build_workflows_include_frontend():
    windows=(ROOT/'.github/workflows/windows-desktop.yml').read_text()
    pages=(ROOT/'.github/workflows/website-pages.yml').read_text()
    assert 'npm run build' in windows
    assert 'frontend/dist;frontend/dist' in windows
    assert 'npm run build' in pages
    assert 'frontend/dist' in pages

def test_public_site_has_no_native_app_backend():
    entry=(ROOT/'frontend/src/App.tsx').read_text()
    assert 'if(boot)' in entry
    assert 'return <Landing/>' in entry
    assert 'if(wantsPreview)' in entry


def test_packaged_ui_doctor_check_exists():
    boot=(ROOT/'star_desktop.py').read_text()
    windows=(ROOT/'.github/workflows/windows-desktop.yml').read_text()
    assert "'--ui-doctor'" in boot
    assert 'Verify React assets included in packaged STAR.exe' in windows
