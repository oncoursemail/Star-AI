"""Run on the PC:  python -m pytest -q server/knowledge/tests  (pure functions, no Luau tools needed)."""
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starkb import luaucheck  # noqa: E402
from starkb.luaucheck import is_engine_type  # noqa: E402

ENGINE = {"Player", "BasePart", "Vector3", "CFrame", "RBXScriptConnection", "Enum.KeyCode", "Part"}


def error(message, line=1, kind="TypeError"):
    return {"line": line, "column": 1, "kind": kind, "message": message}


def test_engine_type_names_in_annotations_are_not_errors_in_the_code():
    found = [error("Unknown type 'Player'", 2), error("Unknown type 'BasePart'", 3), error("Unknown type 'Player'", 5),
             error("Unknown type 'Enum.KeyCode'", 6), error("Unknown type 'RBXScriptConnection'", 7)]
    errors, warnings, unresolved, engine = luaucheck.classify(found, ENGINE.__contains__)
    assert errors == [] and warnings == [] and unresolved == 0
    assert engine == ["Player", "BasePart", "Enum.KeyCode", "RBXScriptConnection"]      # each name once, in order


def test_a_misspelled_type_and_every_other_error_still_fail():
    found = [error("Unknown type 'strng'"), error("Unknown type 'Player'"),
             error("Expected this to be 'string', but got 'number'", 4),
             error("Unknown global 'notDefined'; consider assigning to it first", 5),
             error("Unknown require: game/ReplicatedStorage/Module", 6),
             error("Expected identifier when parsing expression, got ')'", 7, "SyntaxError"),
             error("Variable 'x' is never used; prefix with '_' to silence", 8, "LocalUnused")]
    errors, warnings, unresolved, engine = luaucheck.classify(found, ENGINE.__contains__)
    assert [e["line"] for e in errors] == [1, 4, 5, 7]
    assert [w["kind"] for w in warnings] == ["LocalUnused"] and unresolved == 1 and engine == ["Player"]


def test_without_a_type_oracle_nothing_is_excused():
    errors, _, _, engine = luaucheck.classify([error("Unknown type 'Player'")], None)
    assert len(errors) == 1 and engine == []


def test_only_classes_data_types_and_enums_of_the_index_are_engine_types():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE chunks (heading TEXT, kind TEXT)")
    db.executemany("INSERT INTO chunks VALUES (?, ?)", [
        ("Player", "api-overview"), ("Enum.KeyCode", "enum"), ("Player > Kick", "api-member"),
        ("Scripting", "guide"), ("strng", "guide")])
    assert is_engine_type(db, "Player") and is_engine_type(db, "Enum.KeyCode")
    for name in ("strng", "Scripting", "Player > Kick", "Kick", "KeyCode", "", "x' OR 1=1 --", "../etc", None, 5):
        assert not is_engine_type(db, name)
