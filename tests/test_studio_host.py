"""Settings > Roblox Studio: the STAR Studio server's address and command (star/studio_host.py).

What is under test: the only program the interface can store is `ssh` in key-only mode, nothing typed
can become an option or a second command, the stored command is what star/studio.py then reads, it is
never sent back to the page, and saving a new server drops the chosen place and its edit permissions.
The addresses below are documentation placeholders (RFC 5737 / example.org), not real machines.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from star import studio, studio_host
from star.desktop_core import Settings
from star.react_shell import ALLOWED_ACTIONS, PERMITTED_SETTINGS

ADDRESS = 'star@studio.example.org'
COMMAND = 'lxc exec starai -- sudo -u star -H /home/star/bin/studio-mcp.sh'


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


def test_the_program_is_always_ssh_in_key_only_mode_and_the_command_is_one_argument():
    argv = studio_host.compose(f'  {ADDRESS} ', f'  {COMMAND}  ')
    assert argv == ('ssh', '-o', 'BatchMode=yes', ADDRESS, COMMAND)
    assert studio_host.compose('studio-box', './run.sh')[3:] == ('studio-box', './run.sh')


@pytest.mark.parametrize('address', [
    '', '-oProxyCommand=calc', 'user@-host', 'user name@host', 'user@host;id', 'user@host command',
    'user@@host', '@host', 'user@', 'user@host/', '$(id)@host', 'a' * 300, None, 7,
])
def test_an_address_that_could_be_an_option_or_carry_a_command_is_refused(address):
    with pytest.raises(ValueError):
        studio_host.compose(address, COMMAND)


@pytest.mark.parametrize('command', [
    '', '   ', '-oProxyCommand=calc run.sh', '--version', 'run.sh; rm -rf x', 'run.sh | tee x', 'run.sh && id',
    'run.sh $(id)', 'run.sh `id`', 'run.sh > /tmp/x', "run.sh 'a b'", 'run.sh "a"', 'run.sh a\\b', 'run.sh ~',
    'run.sh *', 'run.sh\x00x', 'x ' * 40, 'run.sh ' + 'a' * 400, None, ['run.sh'],
])
def test_a_command_with_shell_symbols_or_a_leading_option_is_refused(command):
    with pytest.raises(ValueError):
        studio_host.compose(ADDRESS, command)


def test_saving_stores_what_the_studio_transport_reads_and_never_returns_it(tmp_path):
    path = settings_file(tmp_path)
    assert studio_host.handle('studioHostStatus', {}, path) == {'configured': False, 'source': 'none'}
    report = studio_host.handle('studioHostSave', {'address': ADDRESS, 'command': COMMAND}, path)
    assert report == {'configured': True, 'source': 'settings'}
    assert ADDRESS not in json.dumps(report) and 'studio-mcp' not in json.dumps(report)
    assert studio.configured_command(tmp_path) == ('ssh', '-o', 'BatchMode=yes', ADDRESS, COMMAND)
    stored = json.loads((tmp_path / 'studio' / 'remote.json').read_text(encoding='utf-8'))
    assert stored == {'target': 'server', 'command': ['ssh', '-o', 'BatchMode=yes', ADDRESS, COMMAND]}
    assert [item.name for item in (tmp_path / 'studio').iterdir()] == ['remote.json']   # no temporary file left


def test_a_refused_value_leaves_the_stored_connection_as_it_was(tmp_path):
    path = settings_file(tmp_path)
    studio_host.handle('studioHostSave', {'address': ADDRESS, 'command': COMMAND}, path)
    before = (tmp_path / 'studio' / 'remote.json').read_bytes()
    with pytest.raises(ValueError):
        studio_host.handle('studioHostSave', {'address': ADDRESS, 'command': 'run.sh; id'}, path)
    assert (tmp_path / 'studio' / 'remote.json').read_bytes() == before


def test_forgetting_leaves_the_server_choice_unconfigured(tmp_path):
    path = settings_file(tmp_path)
    studio_host.handle('studioHostSave', {'address': ADDRESS, 'command': COMMAND}, path)
    assert studio_host.handle('studioHostClear', {}, path) == {'configured': False, 'source': 'none'}
    assert studio.configured_command(tmp_path) is None
    # The operator scripts keep their own target in the same file; it is not changed by the app.
    assert json.loads((tmp_path / 'studio' / 'remote.json').read_text(encoding='utf-8')) == {'target': 'server', 'command': []}


def test_the_operator_environment_wins_and_is_reported_without_its_text(tmp_path, monkeypatch):
    path = settings_file(tmp_path)
    monkeypatch.setenv(studio.COMMAND_ENV, json.dumps(['ssh', 'operator@studio.example.org', 'start.sh']))
    assert studio_host.handle('studioHostStatus', {}, path) == {'configured': True, 'source': 'environment'}
    assert studio_host.handle('studioHostSave', {'address': ADDRESS, 'command': COMMAND}, path)['source'] == 'environment'


def test_a_damaged_file_is_reported_as_invalid_and_a_new_save_repairs_it(tmp_path):
    path = settings_file(tmp_path)
    (tmp_path / 'studio').mkdir()
    (tmp_path / 'studio' / 'remote.json').write_text('{"command": "ssh somewhere"}', encoding='utf-8')
    assert studio_host.handle('studioHostStatus', {}, path) == {'configured': False, 'source': 'invalid'}
    assert studio_host.handle('studioHostSave', {'address': ADDRESS, 'command': COMMAND}, path)['configured'] is True


def test_a_new_server_drops_the_chosen_place_and_its_permissions(tmp_path):
    path = settings_file(tmp_path, studio_target='host_launcher', studio_id='studio-7', studio_edit=True, studio_luau=True)
    studio_host.handle('studioHostSave', {'address': ADDRESS, 'command': COMMAND}, path)
    saved = Settings.load(path)
    assert (saved.studio_target, saved.studio_id, saved.studio_edit, saved.studio_luau) == ('host_launcher', '', False, False)


def test_this_pc_keeps_its_own_choice_when_the_server_connection_changes(tmp_path):
    path = settings_file(tmp_path, studio_target='local_pc', studio_id='studio-3', studio_edit=True)
    studio_host.handle('studioHostSave', {'address': ADDRESS, 'command': COMMAND}, path)
    saved = Settings.load(path)
    assert (saved.studio_id, saved.studio_edit) == ('studio-3', True)


def test_reading_the_status_changes_nothing(tmp_path):
    path = settings_file(tmp_path, studio_target='host_launcher', studio_id='studio-7', studio_edit=True)
    studio_host.handle('studioHostStatus', {}, path)
    assert Settings.load(path).studio_id == 'studio-7' and not (tmp_path / 'studio').exists()


def test_the_bridge_offers_these_actions_and_no_setting_can_carry_a_command():
    assert studio_host.STUDIO_HOST_ACTIONS <= ALLOWED_ACTIONS
    assert studio_host.CHANGING_ACTIONS == {'studioHostSave', 'studioHostClear'}
    with pytest.raises(PermissionError):
        studio_host.handle('studioHostRun', {}, Path('settings.json').resolve())
    assert not {name for name in PERMITTED_SETTINGS if 'command' in name or 'launcher' in name}
    source = (Path(__file__).resolve().parents[1] / 'star' / 'react_shell.py').read_text(encoding='utf-8')
    block = source[source.index('if action in STUDIO_HOST_ACTIONS:'):source.index("if action=='saveProviderKey':")]
    # A change waits for a running task and drops the earlier test result.
    assert 'self.active_task' in block and 'self.studio_status=None' in block
