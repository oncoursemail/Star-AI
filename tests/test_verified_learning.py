"""Project memory quality, provenance and migration regressions."""
import sqlite3

import pytest

from star.knowledge import KnowledgeStore
from star.learning import approve_learning, learned_context


def test_explicit_review_is_required_and_project_scoped(tmp_path):
    with pytest.raises(PermissionError):
        approve_learning(tmp_path, project="VALEN", text="Use restrained OLED UI", kind="decision")
    receipt = approve_learning(tmp_path, project="VALEN",
        text="Use restrained OLED UI with warm gold accents.", kind="decision",
        human_approved=True)
    assert receipt.note_id > 0
    assert "OLED" in learned_context(tmp_path, "VALEN", "OLED interface")
    assert not learned_context(tmp_path, "DifferentGame", "OLED interface")


def test_ranked_search_favors_relevance_not_creation_order(tmp_path):
    store = KnowledgeStore(tmp_path)
    try:
        older = store.add_note(project="P", kind="decision",
            text="Inventory hotbar layout inventory hotbar layout centered slots",
            source="reviewed:user")
        store.review_note(project="P", note_id=older, evidence="Human screenshot review")
        newer = store.add_note(project="P", kind="reference",
            text="Inventory is mentioned once alongside unrelated unrelated unrelated unrelated text.",
            source="reviewed:design")
        store.review_note(project="P", note_id=newer, evidence="Human source review")
        if store._fts:
            ids = [row.id for row in store.find("P", "inventory hotbar", limit=5)]
            assert ids[0] == older
        unreviewed = store.add_note(project="P", kind="fix",
            text="hotbar hotbar hotbar hotbar hidden unverified claim",
            source="model:generated")
        assert unreviewed not in [x.id for x in store.find("P", "hotbar", reviewed_only=True)]
        assert unreviewed in [x.id for x in store.find("P", "hotbar", reviewed_only=False)]
    finally:
        store.close()


def test_existing_knowledge_database_is_indexed_without_losing_notes(tmp_path):
    path=tmp_path / "knowledge.sqlite3"
    c=sqlite3.connect(path)
    c.execute("""CREATE TABLE notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL, kind TEXT NOT NULL,
        text TEXT NOT NULL, source TEXT NOT NULL, revision TEXT NOT NULL,
        reviewed INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL)""")
    c.execute("INSERT INTO notes(project,kind,text,source,revision,reviewed,created) VALUES(?,?,?,?,?,?,?)",
              ("A","decision","Purple forest should have floating spores","user","initial",1,"2025-01-01"))
    c.commit();c.close()
    store=KnowledgeStore(tmp_path)
    try:
        notes=store.find("A","purple spores")
        assert len(notes)==1 and "Purple forest" in notes[0].text
        if store._fts:
            assert store.db.execute("SELECT 1 FROM index_meta WHERE name='fts5_initialized'").fetchone()
    finally:store.close()


def test_new_note_fts_trigger_and_safe_user_query(tmp_path):
    store=KnowledgeStore(tmp_path)
    try:
        id1=store.add_note(project="A",kind="decision",text="Vulkan performance budgets",
                           source="human:approved")
        store.review_note(project="A",note_id=id1,evidence="Benchmark screenshot")
        assert any(n.id==id1 for n in store.find("A","Vulkan performance"))
        assert store.find("A",'" ) OR ( * : NEAR weird') == []
        assert not store.find("B","Vulkan performance")
        with pytest.raises(ValueError):
            store.find("A","x"*4001)
    finally:store.close()


def test_superseded_decisions_stop_retrieval_but_remain_auditable(tmp_path):
    first=approve_learning(tmp_path,project="One",kind="decision",
        text="Use blue for selected navigation.",human_approved=True)
    second=approve_learning(tmp_path,project="One",kind="decision",
        text="Use antique gold for selected navigation.",replaces_note_id=first.note_id,
        human_approved=True)
    assert second.superseded_id==first.note_id
    assert "gold" in learned_context(tmp_path,"One","selected navigation")
    assert "blue" not in learned_context(tmp_path,"One","selected navigation")
    store=KnowledgeStore(tmp_path/"knowledge")
    try:
        old=store.db.execute("SELECT reviewed FROM notes WHERE id=?",(first.note_id,)).fetchone()
        assert old["reviewed"]==0
    finally:store.close()
    with pytest.raises(ValueError):
        approve_learning(tmp_path,project="Other",text="invalid cross-project change",
                         replaces_note_id=second.note_id,human_approved=True)


def test_explicit_learning_validates_content_and_source(tmp_path):
    with pytest.raises(ValueError):
        approve_learning(tmp_path,project="../bad",text="Valid content",human_approved=True)
    with pytest.raises(ValueError):
        approve_learning(tmp_path,project="P",text="ok",human_approved=True)
    with pytest.raises(ValueError):
        approve_learning(tmp_path,project="P",text="a"*1201,human_approved=True)
    with pytest.raises(ValueError):
        approve_learning(tmp_path,project="P",text="Valid content",
                         kind="unreviewed",human_approved=True)


def test_implicit_recall_of_reviewed_decisions_without_matching_keywords(tmp_path):
    store=KnowledgeStore(tmp_path)
    try:
        i=store.add_note(project="P",kind="decision",
                         text="Select antique gold accents for navigation",
                         source="user:approved")
        store.review_note(project="P",note_id=i,evidence="UI sign-off")
        store.add_note(project="P",kind="fix",
                       text="Never use red backgrounds - unverified model claim",
                       source="model:guess")
        recall=store.find_contextual("P","What did we decide last time?")
        assert [x.id for x in recall] == [i]
        assert all(x.reviewed for x in recall)
        assert store.find_contextual("P","What is the weather on Neptune?") == []
        assert store.find_contextual("OtherProject","What did we decide last time?") == []
    finally:
        store.close()


def test_workspace_names_with_spaces_retrieve_their_own_memory(tmp_path):
    receipt=approve_learning(tmp_path,project="My Roblox Game",
         text="Use polished low-noise dark interface",human_approved=True)
    assert receipt.project=="My Roblox Game"
    assert "dark interface" in learned_context(tmp_path,"My Roblox Game","dark interface")
    assert not learned_context(tmp_path,"Another Roblox Game","dark interface")
    with pytest.raises(ValueError):
        approve_learning(tmp_path,project="Bad / Path",text="Invalid path",
                         human_approved=True)
