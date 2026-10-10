"""Learning as explicit, source-grounded project knowledge—not silent weight updates.

Only a UI-confirmed human action may call approve_learning(). The model has
no function tool for this operation. Notes are stored under STAR's local
profile, not sent to GitHub, other projects or background model trainers.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .knowledge import KnowledgeStore, _project, now


ALLOWED_DECISIONS = frozenset({"requirement", "decision", "fix"})


@dataclass(frozen=True)
class LearningReceipt:
    project: str
    note_id: int
    kind: str
    superseded_id: int | None
    source: str


def approve_learning(
    home: Path, *,
    project: str,
    text: str,
    kind: str = "decision",
    replaces_note_id: int | None = None,
    human_approved: bool = False,
) -> LearningReceipt:
    """Preserve a user-reviewed fact across conversations, with provenance.

    No agent or tool result may silently call this: the host UI must transmit
    an explicit confirmation. Supersession only changes which note is trusted;
    it never deletes the old auditable record.
    """
    project = _project(project)
    if human_approved is not True:
        raise PermissionError("A human must explicitly approve the learning")
    if kind not in ALLOWED_DECISIONS:
        raise ValueError("Only decisions, requirements and verified fixes may be approved")
    if not isinstance(text, str) or not 3 <= len(text.strip()) <= 1200:
        raise ValueError("Approved note must contain 3–1,200 characters")
    if replaces_note_id is not None and (
        isinstance(replaces_note_id, bool) or not isinstance(replaces_note_id, int)
        or replaces_note_id < 1
    ):
        raise ValueError("Invalid superseded note identifier")

    with_store = KnowledgeStore(Path(home) / "knowledge")
    try:
        if replaces_note_id is not None:
            previous = with_store.db.execute(
                "SELECT id,reviewed FROM notes WHERE id=? AND project=?",
                (replaces_note_id, project),
            ).fetchone()
            if previous is None or not previous["reviewed"]:
                raise ValueError("Superseded note is not a reviewed fact in this project")
        # One SQLite transaction: the replacement is never simultaneously
        # trusted with an old conflicting decision after an interrupted write.
        db = with_store.db
        stamp = now()
        try:
            db.execute("BEGIN IMMEDIATE")
            created = db.execute(
                """INSERT INTO notes(project,kind,text,source,revision,reviewed,created)
                   VALUES(?,?,?,?,?,?,?)""",
                (project, kind, text.strip(),
                 "user:explicit-approved-decision", "user-reviewed", 1, stamp),
            )
            note_id = int(created.lastrowid)
            db.execute(
                """INSERT INTO notes(project,kind,text,source,revision,reviewed,created)
                   VALUES(?,?,?,?,?,?,?)""",
                (project, "observation",
                 f"Reviewed note {note_id}: User explicitly approved the decision in STAR",
                 f"review:{note_id}", "accepted", 0, stamp),
            )
            if replaces_note_id is not None:
                db.execute(
                    "UPDATE notes SET reviewed=0 WHERE id=? AND project=?",
                    (replaces_note_id, project),
                )
            db.commit()
        except BaseException:
            db.rollback()
            raise
        return LearningReceipt(project, note_id, kind, replaces_note_id,
                               "user:explicit-approved-decision")
    finally:
        with_store.close()


def learned_context(home: Path, project: str, query: str, *, max_chars: int = 5000,
                    limit: int = 8) -> str:
    """Select only reviewed, relevant facts into a bounded model-context section."""
    if not 200 <= max_chars <= 12000 or not 1 <= limit <= 20:
        raise ValueError("Context budget outside supported range")
    store = KnowledgeStore(Path(home) / "knowledge")
    try:
        selected = store.find_contextual(project, query, limit=limit)
        entries = []
        size = 0
        for note in selected:
            if note.kind == "observation":
                continue
            prefix = f"[REVIEWED SOURCE note={note.id} kind={note.kind} revision={note.revision} source={note.source}]\n"
            content = prefix + note.text[:1500] + "\n"
            if len(content) > max_chars - size:
                continue
            entries.append(content)
            size += len(content)
        return "\n".join(entries)
    finally:
        store.close()
