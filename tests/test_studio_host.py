"""Settings > Roblox Studio: the state of the STAR Studio server connection (star/studio_host.py).

What is under test: the desktop only reads whether an operator-made connection exists and where it
comes from; it never returns the command, and in v0.9.0 nothing in the interface can store or remove
one (the writer is not part of this release). The addresses below are documentation placeholders
(example.org), not real machines.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from star import studio, studio_host
from star.desktop_core import Settings
from star.react_shell import ALLOWED_ACTIONS, PERMITTED_SETTINGS

OPERATOR_COMMAND = ['ssh', '-o', 'BatchMode=yes', 'star@studio.example.org', '/home/star/bin/studio-mcp.sh']


@pytest.fixture(autouse=True)
def no_operator_environment(monkeypatch):
    monkeypatch.delenv(studio.COMMAND_ENV, raising=False)


def settings_file(tmp_path, **changes) -> Path:
    path = tmp_path / 'settings.json'
    saved = Settings()
    for key, value in changes.items():
        setattr(saved, key, value)
    saved.save(path)
    return path


def operator_file(tmp_path, command) -> Path:
    folder = tmp_path / 'studio'
    folder.mkdir()
    path = folder / 'remote.json'
    path.write_text(json.dumps({'target': 'server', 'command': command}), encoding='utf-8')
    return path


def test_a_new_profile_has_no_connection(tmp_path):
    assert studio_host.handle('studioHostStatus', {}, settings_file(tmp_path)) == {'configured': False, 'source': 'none'}


def test_the_operators_file_is_reported_without_its_text(tmp_path):
    path = settings_file(tmp_path)
    operator_file(tmp_path, OPERATOR_COMMAND)
    report = studio_host.handle('studioHostStatus', {}, path)
    assert report == {'configured': True, 'source': 'settings'}
    assert 'studio.example.org' not in json.dumps(report) and 'studio-mcp' not in json.dumps(report)
    assert studio.configured_command(tmp_path) == tuple(OPERATOR_COMMAND)       # what the transport then reads


def test_the_operator_environment_wins_and_is_reported_without_its_text(tmp_path, monkeypatch):
    path = settings_file(tmp_path)
    monkeypatch.setenv(studio.COMMAND_ENV, json.dumps(['ssh', 'operator@studio.example.org', 'start.sh']))
    report = studio_host.handle('studioHostStatus', {}, path)
    assert report == {'configured': True, 'source': 'environment'}
    assert 'operator' not in json.dumps(report)


def test_a_damaged_file_is_reported_as_invalid(tmp_path):
    path = settings_file(tmp_path)
    operator_file(tmp_path, 'ssh somewhere')
    assert studio_host.handle('studioHostStatus', {}, path) == {'configured': False, 'source': 'invalid'}


def test_reading_the_status_changes_nothing(tmp_path):
    path = settings_file(tmp_path, studio_target='host_launcher', studio_id='studio-7', studio_edit=True)
    studio_host.handle('studioHostStatus', {}, path)
    assert Settings.load(path).studio_id == 'studio-7' and not (tmp_path / 'studio').exists()
    stored = operator_file(tmp_path, OPERATOR_COMMAND)
    before = stored.read_bytes()
    studio_host.handle('studioHostStatus', {}, path)
    assert stored.read_bytes() == before and [item.name for item in stored.parent.iterdir()] == ['remote.json']


@pytest.mark.parametrize('action', ['studioHostSave', 'studioHostClear', 'studioHostRun'])
def test_nothing_in_the_interface_can_store_or_remove_a_connection(tmp_path, action):
    path = settings_file(tmp_path, studio_target='host_launcher', studio_id='studio-7', studio_edit=True)
    stored = operator_file(tmp_path, OPERATOR_COMMAND)
    before = stored.read_bytes()
    assert action not in ALLOWED_ACTIONS                                         # the bridge refuses it by name
    with pytest.raises(PermissionError):
        studio_host.handle(action, {'address': 'star@studio.example.org', 'command': 'run.sh'}, path)
    assert stored.read_bytes() == before
    assert Settings.load(path).studio_id == 'studio-7'


def test_the_bridge_offers_the_status_only_and_no_setting_can_carry_a_command():
    assert studio_host.STUDIO_HOST_ACTIONS == {'studioHostStatus'} and studio_host.STUDIO_HOST_ACTIONS <= ALLOWED_ACTIONS
    assert not {name for name in ALLOWED_ACTIONS if name.startswith('studioHost')} - {'studioHostStatus'}
    assert not {name for name in PERMITTED_SETTINGS if 'command' in name or 'launcher' in name}
    for name in ('compose', 'save', 'clear', '_write'):
        assert not hasattr(studio_host, name), name
    source = (Path(__file__).resolve().parents[1] / 'star' / 'studio_host.py').read_text(encoding='utf-8')
    assert 'write_text' not in source and 'os.replace' not in source and 'open(' not in source
