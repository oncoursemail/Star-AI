"""Exact API lookup: enum items, globals, methods of the Enum data type, inherited members.

Run on the PC:  python -m pytest -q server/knowledge/tests
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from starkb import store  # noqa: E402
from starkb.serve import api_lookup  # noqa: E402

CHUNKS = [
    ("api-overview", "GuiObject", "GuiObject   [class]\n\nInherits: GuiBase2d > GuiBase > Instance"),
    ("api-member", "GuiObject > BackgroundColor3", "GuiObject.BackgroundColor3: Color3   [class GuiObject property]"),
    ("api-overview", "Frame", "Frame   [class]\n\nInherits: GuiObject > GuiBase2d > GuiBase > Instance"),
    ("api-member", "Humanoid > LoadAnimation", "Humanoid:LoadAnimation(animation: Animation): AnimationTrack\n\nDEPRECATED: use Animator"),
    ("enum", "Enum.KeyCode", "Enum.KeyCode   [enum]\n\nItems:\n- Enum.KeyCode.E = 101\n- Enum.KeyCode.Escape = 27"),
    ("enum", "Enum.KeyCode", "Enum.KeyCode   [enum] (continued)\n\nItems:\n- Enum.KeyCode.ButtonX = 1002"),
    ("api-overview", "Enum", "Enum   [datatype]"),
    ("api-member", "Enum > GetEnumItems", "Enum:GetEnumItems(): Array   [datatype Enum method]"),
    ("api-member", "Luau globals > print", "print(...: any)   [global Luau globals function]"),
    ("api-member", "Roblox globals > workspace", "workspace: Workspace   [global Roblox globals property]"),
]


def index(tmp_path):
    db = store.connect(tmp_path / "kb.sqlite3")
    doc = db.execute("INSERT INTO docs(source,path,kind,title,url) VALUES('creator-docs','ref.yaml','api-class','Ref','https://example.invalid/ref')").lastrowid
    for n, (kind, heading, text) in enumerate(CHUNKS):
        db.execute("INSERT INTO chunks(doc_id,ord,kind,heading,anchor,text,idents,text_sha) VALUES(?,?,?,?,?,?,?,?)",
                   (doc, n, kind, heading, "", text, "", f"sha{n}"))
    db.commit()
    return db


def lookup(db, *symbols):
    return {r["symbol"]: r for r in api_lookup(db, list(symbols))}


def test_enum_items_are_checked_not_assumed(tmp_path):
    out = lookup(index(tmp_path), "Enum.KeyCode", "Enum.KeyCode.E", "Enum.KeyCode.ButtonX", "Enum.KeyCode.Nope", "Enum.NoSuchEnum.E")
    assert out["Enum.KeyCode"]["found"] and out["Enum.KeyCode.E"]["found"]
    assert out["Enum.KeyCode.ButtonX"]["found"] and "ButtonX" in out["Enum.KeyCode.ButtonX"]["text"]   # second chunk of the enum
    assert out["Enum.KeyCode.Nope"] == {"symbol": "Enum.KeyCode.Nope", "found": False,
                                        "reason": "Enum.KeyCode exists but has no item Nope"}
    assert out["Enum.NoSuchEnum.E"]["found"] is False


def test_globals_and_enum_datatype_methods_are_found_by_their_code_names(tmp_path):
    out = lookup(index(tmp_path), "print", "workspace", "Enum:GetEnumItems", "printt", "Enum:NoSuchMethod")
    assert out["print"]["heading"] == "Luau globals > print"
    assert out["workspace"]["heading"] == "Roblox globals > workspace"
    assert out["Enum:GetEnumItems"]["heading"] == "Enum > GetEnumItems"
    assert out["printt"]["found"] is False and out["Enum:NoSuchMethod"]["found"] is False


def test_inherited_members_deprecation_and_bad_names(tmp_path):
    out = lookup(index(tmp_path), "Frame.BackgroundColor3", "Humanoid:LoadAnimation", "Frame.Nope", "../../etc/passwd")
    assert out["Frame.BackgroundColor3"]["inherited_from"] == "GuiObject"
    assert out["Humanoid:LoadAnimation"]["deprecated"] is True
    assert out["Frame.Nope"]["found"] is False
    assert out["../../etc/passwd"]["found"] is False and "not a Class" in out["../../etc/passwd"]["reason"]
