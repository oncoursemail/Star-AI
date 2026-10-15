"""Structure-aware text search with a size budget ("agent grep"; idea from jcode, MIT, no code copied).

Each text hit in a source file names the function or class around it, so the model can often skip reading the
file; and the result is cut to a budget by keeping hits from every file first, so one noisy file cannot fill the
model's context (CPU prompt reading is the slow part on STAR's brains).
"""
import json

from star import code_navigation
from star.workspace import Workspace


def write(root, filename, text):
    path = root / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


def search(root, query):
    return Workspace(root).call('workspace_search', {'query': query})


def test_python_hits_name_their_enclosing_method_and_module_level_hits_name_nothing(tmp_path):
    write(tmp_path, 'game/store.py', '''TIMEOUT = 5  # coins

class CoinStore:
    def add(self, user: int, coins: int) -> int:
        total = coins + 1
        return total

def spend(coins):
    return coins - 1

print("coins done")
''')
    hits = {hit['line']: hit for hit in search(tmp_path, 'coins')['matches']}
    assert hits[4]['in'].startswith('def add(self, user: int, coins: int)') and hits[4]['in_line'] == 4
    assert hits[5]['in'] == hits[4]['in']                                    # a body line of the same method
    assert hits[8]['in'] == 'def spend(coins)' and hits[9]['in'] == 'def spend(coins)'
    assert 'in' not in hits[1] and 'in' not in hits[11]                       # module level
    assert all({'file', 'line', 'text'} <= set(hit) for hit in hits.values())  # old keys kept


def test_luau_and_typescript_hits_name_the_nearest_declaration_above(tmp_path):
    write(tmp_path, 'src/Round.server.luau', 'local Players = game:GetService("Players")\n\n'
                                              'local function startRound(players)\n\tprint(#players)\nend\n')
    write(tmp_path, 'src/Hud.tsx', 'export function RoundHUD() {\n  const players = 3;\n  return players;\n}\n')
    result = search(tmp_path, 'players')
    by = {(hit['file'], hit['line']): hit for hit in result['matches']}
    assert 'in' not in by[('src/Round.server.luau', 1)]
    assert by[('src/Round.server.luau', 4)]['in'] == 'local function startRound(players)'
    assert by[('src/Hud.tsx', 2)]['in'] == 'export function RoundHUD() {'


def test_plain_text_files_have_no_structure(tmp_path):
    write(tmp_path, 'notes.md', '# Coins\ncoins are saved\n')
    assert all('in' not in hit for hit in search(tmp_path, 'coins')['matches'])


def test_a_large_result_is_cut_to_the_budget_keeping_every_file(tmp_path, monkeypatch):
    monkeypatch.setattr(code_navigation, 'TEXT_RESULT_BUDGET', 2500)
    write(tmp_path, 'noisy.lua', ''.join(f'local coins{i} = {i}\n' for i in range(70)))
    for name in ('a.lua', 'b.lua', 'c.lua'):
        write(tmp_path, name, 'local function pay(coins)\n\treturn coins\nend\n')
    result = search(tmp_path, 'coins')
    assert len(json.dumps(result['matches'], ensure_ascii=False)) <= 2500
    files = {hit['file'] for hit in result['matches']}
    assert {'a.lua', 'b.lua', 'c.lua', 'noisy.lua'} <= files
    shown = sum(hit['file'] == 'noisy.lua' for hit in result['matches'])
    assert result['omitted'] == {'noisy.lua': 70 - shown} and result['incomplete'] is True
    assert result['budget_chars'] == 2500


def test_a_small_result_is_not_cut(tmp_path):
    write(tmp_path, 'a.lua', 'local coins = 1\n')
    result = search(tmp_path, 'coins')
    assert len(result['matches']) == 1 and 'omitted' not in result and result['incomplete'] is False
