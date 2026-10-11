"""Offline checks for fast, scoped workspace symbol navigation."""
import pytest
from jsonschema import ValidationError

from star.workspace import Workspace


def write(root, filename, text):
    path = root / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


def test_python_ast_summaries_and_signatures(tmp_path):
    write(tmp_path, 'game/inventory.py', '''class InventoryStore(BaseStore):
    def save(self, user_id: int, items: list[str]) -> bool:
        return True

async def load_inventory(
    user_id: int,
    *,
    fresh: bool = False,
):
    return []
''')
    result = Workspace(tmp_path).call('workspace_search', {'query': 'save inventory', 'mode': 'symbols'})
    matches = result['matches']
    assert result['mode'] == 'symbols'
    assert {item['name'] for item in matches} >= {'InventoryStore.save', 'InventoryStore', 'load_inventory'}
    method = next(item for item in matches if item['name'] == 'InventoryStore.save')
    assert method['line'] == 2
    assert 'user_id: int' in method['text']
    assert method['kind'] == 'method'
    assert result['scanned_files'] == 1


def test_language_signatures_luau_typescript_godot_and_unity(tmp_path):
    write(tmp_path, 'src/Round.server.luau', 'local function startRound(players)\nend\nexport type RoundState = {active: boolean}\n')
    write(tmp_path, 'src/Hud.tsx', 'export function RoundHUD() {\n return null;\n}\nexport const roundTimer = () => 10;\n')
    write(tmp_path, 'src/Player.gd', 'extends CharacterBody3D\nfunc restart_round():\n\tpass\n')
    write(tmp_path, 'src/Round.cs', 'public class RoundController {\npublic void StartRound() {}\n}\n')
    result = Workspace(tmp_path).call('workspace_search', {'query': 'round', 'mode': 'symbols'})
    names = {item['name'] for item in result['matches']}
    assert {'startRound', 'RoundState', 'RoundHUD', 'roundTimer', 'restart_round',
            'RoundController', 'StartRound'} <= names
    assert all(item['line'] > 0 and len(item['text']) <= 200 for item in result['matches'])


def test_text_search_remains_backward_compatible_and_case_insensitive(tmp_path):
    write(tmp_path, 'doc/design.md', 'STAR search\nsecond SEARCH result\nnot a match\n')
    output = Workspace(tmp_path).call('workspace_search', {'query': 'search'})
    assert output['mode'] == 'text'
    assert [(x['file'], x['line']) for x in output['matches']] == [('doc/design.md', 1), ('doc/design.md', 2)]
    assert all('text' in row for row in output['matches'])


def test_ignored_generated_and_sensitive_paths_not_read(tmp_path):
    write(tmp_path, 'src/main.py', 'def safe_function():\n    pass\n')
    write(tmp_path, 'node_modules/vendor.py', 'def leaked_function():\n    pass\n')
    write(tmp_path, '.git/refs/private.py', 'def leaked_function():\n    pass\n')
    write(tmp_path, '.env', 'leaked_function=secret')
    write(tmp_path, 'src/private.key', 'leaked_function')
    write(tmp_path, 'build/bundle.js', 'function leaked_function() {}')
    result = Workspace(tmp_path).call('workspace_search', {'query': 'function', 'mode': 'symbols'})
    assert result['scanned_files'] == 1
    assert {row['name'] for row in result['matches']} == {'safe_function'}
    assert Workspace(tmp_path).call('workspace_search', {'query': 'leaked_function'})['matches'] == []


def test_symlink_cannot_escape_and_invalid_utf8_does_not_break_search(tmp_path):
    outside = tmp_path.parent / 'outside-private.py'
    outside.write_text('def outside_leak(): pass', encoding='utf-8')
    try:
        (tmp_path / 'outside.py').symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip('Symlink creation not supported by current user/platform')
    (tmp_path / 'broken.py').write_bytes(b'\xff\xfe\x00')
    write(tmp_path, 'valid.py', 'def valid(): pass')
    outcome = Workspace(tmp_path).call('workspace_search', {'query': 'valid', 'mode': 'symbols'})
    assert [item['name'] for item in outcome['matches']] == ['valid']
    assert all(item['name'] != 'outside_leak' for item in outcome['matches'])


def test_malformed_source_skipped_and_new_edit_visible(tmp_path):
    bad = write(tmp_path, 'broken.py', 'def broken(:')
    workspace = Workspace(tmp_path)
    assert workspace.call('workspace_search', {'query': 'broken', 'mode': 'symbols'})['matches'] == []
    bad.write_text('def broken():\n    pass\n', encoding='utf-8')
    assert workspace.call('workspace_search', {'query': 'broken', 'mode': 'symbols'})['matches'][0]['line'] == 1


def test_query_validation_and_schema_enforced(tmp_path):
    workspace = Workspace(tmp_path)
    for params in ({'query': ''}, {'query': 'x', 'mode': 'magic'}, {'query': 's', 'mode': 'symbols'},
                   {'query': 'x', 'allow_write': True}):
        with pytest.raises((ValueError, ValidationError)):
            workspace.call('workspace_search', params)


def test_bounded_matches_scans_and_lines(tmp_path, monkeypatch):
    from star import code_navigation
    monkeypatch.setattr(code_navigation, 'MAX_FILES', 3)
    monkeypatch.setattr(code_navigation, 'MAX_RESULTS', 2)
    for n in range(6):
        write(tmp_path, f'src/file{n}.py', f'def item{n}():\n    return 0\n')
    workspace = Workspace(tmp_path)
    result = workspace.call('workspace_search', {'query': 'item', 'mode': 'symbols'})
    assert result['scanned_files'] == 3
    assert len(result['matches']) == 2
    assert result['incomplete'] is True
    result = workspace.call('workspace_search', {'query': 'return'})
    assert len(result['matches']) == 2


def test_no_mutation_in_read_only_modes(tmp_path):
    file = write(tmp_path, 'mod.py', 'def check():\n    return 1\n')
    original = file.read_bytes()
    workspace = Workspace(tmp_path)
    workspace.call('workspace_search', {'query': 'check', 'mode': 'symbols'}, allow_write=False)
    workspace.call('workspace_search', {'query': 'return'}, allow_write=False)
    assert file.read_bytes() == original


def test_search_only_parses_code_and_never_executes_it(tmp_path):
    write(tmp_path, 'would_run.py', 'raise AssertionError("must not import")\ndef useful_symbol():\n    pass\n')
    matches = Workspace(tmp_path).call('workspace_search', {'query': 'useful_symbol', 'mode': 'symbols'})['matches']
    assert [item['name'] for item in matches] == ['useful_symbol']


def test_workspace_edit_gate_unchanged(tmp_path):
    workspace = Workspace(tmp_path)
    with pytest.raises(PermissionError):
        workspace.call('workspace_write', {'path': 'new.py', 'content': 'pass'}, allow_write=False)
    result = workspace.call('workspace_write', {'path': 'new.py', 'content': 'def approved(): pass'}, allow_write=True)
    assert result['bytes_written'] == len('def approved(): pass')
    assert workspace.call('workspace_search', {'query': 'approved', 'mode': 'symbols'})['matches'][0]['name'] == 'approved'


def test_scan_directory_limit_is_reported(tmp_path, monkeypatch):
    from star import code_navigation
    monkeypatch.setattr(code_navigation, 'MAX_DIRS', 1)
    write(tmp_path, 'a/a.py', 'def first_symbol(): pass')
    write(tmp_path, 'b/b.py', 'def second_symbol(): pass')
    result = Workspace(tmp_path).call('workspace_search', {'query': 'symbol', 'mode': 'symbols'})
    assert result['matches'] == []
    assert result['incomplete'] is True


def test_text_search_reads_any_small_text_file_not_only_known_types(tmp_path):
    names = ['main.c', 'lib.cc', 'app.rb', 'index.php', 'View.swift', 'Main.kt', 'level.tscn', 'water.shader',
             'style.scss', 'App.vue', 'data.csv', 'notes.rst', 'Makefile', 'Dockerfile', 'run.bat', 'main.luau']
    for name in names:
        write(tmp_path, name, 'needle_in_file here')
    (tmp_path / 'image.bin').write_bytes(b'needle_in_file' + bytes([0, 255, 254]))
    write(tmp_path, '.hidden.txt', 'needle_in_file here')
    write(tmp_path, 'node_modules/pkg/index.js', 'needle_in_file here')
    workspace = Workspace(tmp_path)
    found = {hit['file'] for hit in workspace.call('workspace_search', {'query': 'needle_in_file'})['matches']}
    assert found == set(names)
    # Symbol search still needs a language it can read declarations from.
    write(tmp_path, 'tool.rb', 'def needle_symbol; end')
    assert workspace.call('workspace_search', {'query': 'needle_symbol', 'mode': 'symbols'})['matches'] == []
