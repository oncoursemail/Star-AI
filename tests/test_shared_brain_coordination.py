import hashlib
import sqlite3

import pytest

from star.shared_brain.coordination import snapshot
from star.shared_brain.store import SharedBrain, serialize


@pytest.fixture
def collab(tmp_path):
    project = tmp_path / "worktrees/project"
    project.mkdir(parents=True)
    (tmp_path / "COLLAB").mkdir()
    (tmp_path / "COLLAB/BOARD.md").write_text("- [CLAIMED] Graph | claude | star/test | 2026-10-11 05:00Z | notes.md\n")
    log = tmp_path / "COLLAB/MESSAGES.md"
    log.write_text("# Messages\n\n- 2026-10-11 05:00Z claude -> codex: first\n\n- 2026-10-11 05:01Z codex -> claude: second\n")
    brain = SharedBrain(project)
    yield tmp_path, log, brain
    brain.close()


def test_cursor_append_and_receipt_do_not_change_claims(collab):
    root, log, brain = collab
    old_board = (root / "COLLAB/BOARD.md").read_bytes()
    first = snapshot(brain, root, actor="codex", acknowledge=True)
    assert len(first["messages"]) == 2 and first["acknowledged"]
    assert snapshot(brain, root, after=first["cursor"])["messages"] == []
    with log.open("a") as stream:
        stream.write("\n- 2026-10-11 05:02Z claude -> codex: third\n")
    second = snapshot(brain, root, after=first["cursor"])
    assert len(second["messages"]) == 1 and "third" in second["messages"][0]["text"]
    assert (root / "COLLAB/BOARD.md").read_bytes() == old_board
    assert brain.db.execute("SELECT actor,cursor FROM coordination_receipts").fetchone()[0] == "codex"


def test_cursor_rejects_rewritten_history(collab):
    root, log, brain = collab
    prior = snapshot(brain, root)
    log.write_text(log.read_text().replace("first", "wrong"))
    with pytest.raises(ValueError, match="changed before"):
        snapshot(brain, root, after=prior["cursor"])


def test_snapshot_cap_never_skips_undelivered_messages(collab):
    root, log, brain = collab
    log.write_text("# Messages\n" + "".join("\n- 2026-10-11 05:00Z claude -> codex: " + str(i) + " " + "x"*350 + "\n" for i in range(20)))
    result = snapshot(brain, root, budget_chars=1200)
    assert len(serialize(result)) <= 1200 and result["truncated"]
    assert 0 < len(result["messages"]) < 20
    again = snapshot(brain, root, after=result["cursor"], budget_chars=1200)
    assert result["messages"][-1]["id"] != again["messages"][0]["id"]


def test_coordination_root_is_scoped(collab, tmp_path):
    root, _, brain = collab
    outside = root / "another"
    outside.mkdir()
    with pytest.raises(ValueError):
        snapshot(brain, outside)


def test_cursor_cannot_skip_message_from_inside_with_valid_digest(collab):
    root, log, brain = collab
    raw = log.read_bytes()
    offset = raw.index(b"first") + 2
    cursor = str(offset) + ":" + hashlib.sha256(raw[:offset]).hexdigest()
    with pytest.raises(ValueError, match="cursor"):
        snapshot(brain, root, after=cursor)


def test_claims_and_long_message_cannot_stall_pagination(collab):
    root, log, brain = collab
    (root / "COLLAB/BOARD.md").write_text("".join(
        "- [CLAIMED] " + str(i) + " " + "x" * 200 + " | claude | branch | time | notes\n"
        for i in range(40)))
    log.write_text("# Messages\n\n- 2026-10-11 05:00Z claude -> codex: first " + "m" * 5000 + "\n")
    result = snapshot(brain, root, budget_chars=1000)
    assert len(serialize(result)) <= 1000
    assert len(result["messages"]) == 1 and result["messages"][0]["clipped"]
    assert "first" in result["messages"][0]["text"]
    assert result["cursor"].split(":")[0] == str(len(log.read_bytes()))
    assert snapshot(brain, root, after=result["cursor"], budget_chars=1000)["messages"] == []


def test_header_only_cursor_growth_is_in_total_budget(collab):
    root, log, brain = collab
    (root / "COLLAB/BOARD.md").write_text(
        "- [CLAIMED] " + "x" * 210 + " | " + "y" * 240 + " | " + "z" * 200 + "\n")
    log.write_text("# Messages\n" + "x" * 100000)
    result = snapshot(brain, root, budget_chars=1000)
    assert not result["messages"]
    assert len(serialize(result)) <= 1000
    assert result["cursor"].split(":")[0] == str(len(log.read_bytes()))


def test_old_end_cursor_cannot_skip_appended_nonwhitespace(collab):
    root, log, brain = collab
    prior = snapshot(brain, root)
    with log.open("a") as stream:
        stream.write("continued first message\n\n- 2026-10-11 05:02Z claude -> codex: third\n")
    with pytest.raises(ValueError, match="cursor"):
        snapshot(brain, root, after=prior["cursor"])


def test_cursor_from_log_without_final_newline_resumes_after_append(collab):
    root, log, brain = collab
    log.write_text(log.read_text().rstrip("\n"))
    prior = snapshot(brain, root)
    with log.open("a") as stream:
        stream.write("\n\n- 2026-10-11 05:02Z claude -> codex: third\n")
    result = snapshot(brain, root, after=prior["cursor"])
    assert len(result["messages"]) == 1 and "third" in result["messages"][0]["text"]
