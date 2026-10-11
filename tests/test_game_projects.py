"""Offline multi-engine tests: no engine install, network, GPU or credentials."""
import json

import pytest

from star.workspace import Workspace, TOOL_NAMES
from star import game_projects


def create_godot(root, name='My Game'):
    root.mkdir(parents=True, exist_ok=True)
    (root / 'project.godot').write_text('[application]\nconfig/name="' + name + '"\n', encoding='utf-8')
    (root / 'scenes').mkdir()
    (root / 'scenes' / 'main.tscn').write_text('[gd_scene format=3]\n', encoding='utf-8')
    (root / 'scenes' / 'hero.gd').write_text('extends CharacterBody3D\n', encoding='utf-8')


def create_unity(root):
    (root / 'ProjectSettings').mkdir(parents=True)
    (root / 'ProjectSettings' / 'ProjectVersion.txt').write_text('m_EditorVersion: 6000.1.12f1\n')
    (root / 'Assets').mkdir()
    (root / 'Assets' / 'Player.cs').write_text('class Player {}')
    (root / 'Packages').mkdir()
    (root / 'Packages' / 'manifest.json').write_text(json.dumps({'dependencies': {'com.unity.test-framework': '1.5.1'}}))


def test_tool_registry_exposes_only_preview_and_inspection():
    assert {'workspace_game_discover', 'workspace_game_inspect', 'workspace_game_plan'} <= TOOL_NAMES
    assert not any('execute' in t or 'run' in t for t in TOOL_NAMES if t.startswith('workspace_game_'))


def test_godot_discovery_inspection_and_preview(tmp_path):
    create_godot(tmp_path / 'games' / 'quest')
    work = Workspace(tmp_path)
    listing = work.call('workspace_game_discover', {})
    assert listing['projects'][0]['engine'] == 'godot'
    assert listing['projects'][0]['path'] == 'games/quest'
    detail = work.call('workspace_game_inspect', {'path': 'games/quest'})['project']
    assert detail['languages'] == {'GDScript': 1}
    assert detail['sample_scenes'] == ['scenes/main.tscn']
    assert detail['name'] == 'My Game'
    command = work.call('workspace_game_plan', {'path': 'games/quest', 'action': 'import'})
    assert command['argv'] == ['godot', '--headless', '--path', '.', '--import']
    assert command['executed'] is False and command['requires_owner_run'] is True
    assert command['cwd'] == 'games/quest'


def test_unity_project_version_and_test_plan(tmp_path):
    create_unity(tmp_path / 'unity')
    work = Workspace(tmp_path)
    detail = work.call('workspace_game_inspect', {'path': 'unity'})['project']
    assert detail['engine'] == 'unity' and detail['version'] == '6000.1.12f1'
    assert detail['languages'] == {'C#': 1} and detail['package_count'] == 1
    task = work.call('workspace_game_plan', {'path': 'unity', 'action': 'test'})
    assert task['argv'][0] == '<UNITY_EDITOR_EXECUTABLE>'
    assert '-runTests' in task['argv'] and '-quit' not in task['argv']
    assert task['executes_project_code'] and not task['executed']


def test_unity_import_is_not_falsely_claimed(tmp_path):
    create_unity(tmp_path)
    task = Workspace(tmp_path).call('workspace_game_plan', {'path': '.', 'action': 'import'})
    assert task['available'] is False
    assert 'argv' not in task


def test_unreal_project_detection_is_manifest_only(tmp_path):
    (tmp_path / 'MyShooter.uproject').write_text(json.dumps({'EngineAssociation': '5.5'}))
    result = Workspace(tmp_path).call('workspace_game_inspect', {'path': '.'})['project']
    assert result['engine'] == 'unreal' and result['version'] == '5.5'
    plan = Workspace(tmp_path).call('workspace_game_plan', {'path': '.', 'action': 'test'})
    assert not plan['available'] and 'argv' not in plan


def test_godot_export_requires_manifest_preset_and_safe_filename(tmp_path):
    create_godot(tmp_path)
    (tmp_path / 'export_presets.cfg').write_text('[preset.0]\nname="Windows Desktop"\n[preset.0.options]\nname="ignore"\n')
    workspace = Workspace(tmp_path)
    project = workspace.call('workspace_game_inspect', {'path': '.'})['project']
    assert project['export_presets'] == ['Windows Desktop']
    command = workspace.call('workspace_game_plan', {'path': '.', 'action': 'export',
                                                       'preset': 'Windows Desktop', 'output': 'build/quest.exe'})
    assert command['argv'][-3:] == ['--export-release', 'Windows Desktop', 'build/quest.exe']
    assert not (tmp_path / 'build').exists()  # preview never creates directories
    with pytest.raises(ValueError):
        workspace.call('workspace_game_plan', {'path': '.', 'action': 'export',
                                               'preset': 'not in file', 'output': 'build/game.exe'})
    for path in ['../elsewhere.exe', '/tmp/other.exe', 'C:\\dev\\game.exe', '.env', 'file-no-extension']:
        with pytest.raises((ValueError, PermissionError)):
            workspace.call('workspace_game_plan', {'path': '.', 'action': 'export',
                                                   'preset': 'Windows Desktop', 'output': path})


def test_discovery_skips_symlinks_generated_dirs_and_private_files(tmp_path):
    create_godot(tmp_path / 'real')
    (tmp_path / 'Library').mkdir()
    create_godot(tmp_path / 'Library' / 'ignored')
    (tmp_path / '.git').mkdir()
    create_godot(tmp_path / '.git' / 'private')
    (tmp_path / 'alias').symlink_to(tmp_path / 'real', target_is_directory=True)
    projects = Workspace(tmp_path).call('workspace_game_discover', {})['projects']
    assert [x['path'] for x in projects] == ['real']
    with pytest.raises(PermissionError):
        Workspace(tmp_path).call('workspace_game_discover', {'path': '.git'})


def test_workspace_traversal_is_rejected(tmp_path):
    work = Workspace(tmp_path)
    for tool, args in [('workspace_game_discover', {'path': '..'}),
                       ('workspace_game_inspect', {'path': '..'}),
                       ('workspace_game_plan', {'path': '..', 'action': 'validate'})]:
        with pytest.raises(PermissionError):
            work.call(tool, args)


def test_malformed_and_oversized_manifest_are_bounded(tmp_path):
    create_unity(tmp_path / 'unity')
    manifest = tmp_path / 'unity' / 'Packages' / 'manifest.json'
    manifest.write_text('{broken')
    assert Workspace(tmp_path).call('workspace_game_inspect', {'path': 'unity'})['project']['package_count'] == 0
    manifest.write_text('x' * (game_projects.MAX_MANIFEST_BYTES + 1))
    assert Workspace(tmp_path).call('workspace_game_inspect', {'path': 'unity'})['project']['package_count'] == 0


def test_discover_is_bounded_to_twelve_projects(tmp_path):
    for i in range(20):
        create_godot(tmp_path / f'g{i:02}')
    result = Workspace(tmp_path).call('workspace_game_discover', {})
    assert len(result['projects']) == 12
    assert result['scan_limited'] is True


def test_actions_schema_and_invalid_requests_are_rejected(tmp_path):
    create_godot(tmp_path)
    work = Workspace(tmp_path)
    with pytest.raises(ValueError):
        work.call('workspace_game_plan', {'path': '.', 'action': 'shell'})
    with pytest.raises(ValueError):
        work.call('workspace_game_plan', {'path': '.', 'action': 'import', 'preset': 'Injected'})
    with pytest.raises(Exception):
        work.call('workspace_game_plan', {'path': '.', 'action': 'validate', 'command': 'rm -rf .'})
    assert not work.call('workspace_game_plan', {'path': '.', 'action': 'test'})['available']
