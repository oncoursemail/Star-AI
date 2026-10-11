"""Lessons: what STAR learns from use, kept with provenance and used in later answers.

The model's weights never change. "Learning" here is a loop over local records:

  capture   after each turn, with regular expressions and a few SQLite rows (no model call):
            the owner's stated preferences and corrections, a retry after a failure, a Luau
            check that failed and was repaired, a documentation search that found nothing,
            and thumbs up/down on an answer;
  trust     a durable statement in the OWNER'S OWN WORDS is accepted at once for that project
            (unless the owner chose "review everything"); everything inferred, summarised by a
            model, or taken from tool output, web pages, documentation or files is a CANDIDATE
            and is never given to the model as knowledge until the owner approves it;
  use       accepted lessons are recalled into the next turns of the same project through the
            reviewed-knowledge section of the turn context, ranked, de-duplicated and bounded.

A lesson is an ordinary row of `notes` (star/knowledge.py) whose `status` is set. `reviewed`
remains the single flag every reader checks, and this module is the only writer that sets it
for a lesson. A lesson is text and nothing else: no code path reads one to change a setting
or a permission, and text that asks for either, or that carries a key or password, is refused.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import difflib
import json
from pathlib import Path
import re
import sqlite3

from .knowledge import APPROVED_DECISION_SOURCE, LESSON_KINDS, KnowledgeStore, _project, now

STATUSES = ("candidate", "accepted", "rejected", "superseded", "merged")
OWNER = "user"                 # a durable statement in the owner's own words, typed in a chat
MANUAL = "manual"              # typed by the owner in the review panel
CONTEXT = "chat-correction"    # the owner's words, but they only make sense next to one answer
# Signals STAR worked out for itself. They can only ever start as candidates.
INFERRED = (CONTEXT, "feedback", "retry", "verified-fix", "doc", "summary")
SOURCE_TYPES = (OWNER, MANUAL, *INFERRED)
# Raw captures the optional background step may rewrite into concise candidates.
DIGESTIBLE = (CONTEXT, "feedback", "retry", "verified-fix", "doc")
# Older notes the owner approved by hand are shown and recalled as lessons too.
RECALLED_KINDS = (*LESSON_KINDS, "requirement", "decision", "fix")
STANDING_KINDS = frozenset({"preference", "correction", "requirement", "decision"})

MAX_TEXT = 600
MAX_EVIDENCE = 1200
RECALL_SCAN = 300          # newest accepted lessons considered for one turn
# Heading of the turn section that carries recalled lessons (star.desktop_core.run_task).
LESSONS_HEADING = "OWNER'S LESSONS FOR THIS PROJECT (apply unless this message says otherwise)"
RECALL_CLIP = 240          # characters of one lesson placed in a turn
LINE_OVERHEAD = 20         # "[#123 correction] " and the line break
# Per-turn budget as (lessons, characters). The block is read on every turn and is never in
# the server's prompt cache (it sits in the final user turn), so it is kept small: at most
# about 90 tokens of lessons for a quick answer and 300 for a full one.
RECALL_QUICK = (3, 360)
RECALL_FULL = (8, 1200)
# Rows the review page loads per status, newest first. Every accepted lesson that can be
# recalled (RECALL_SCAN) is on the page, however many newer notes are waiting.
LIST_WINDOW = {"accepted": RECALL_SCAN, "candidate": 200, "rejected": 50, "superseded": 50, "merged": 50}
# Notes STAR makes by itself after a turn. While this many of them (and of the summaries made
# from them) wait unreviewed, no further ones are recorded, so the table cannot grow with
# every turn. The owner's own signals (their words, their thumbs) are never turned away.
MACHINE_MADE = ("retry", "verified-fix", "doc")
MAX_MACHINE_WAITING = 200


class LessonRefused(ValueError):
    """Text that may not become a lesson. `reason` is secret | permission | size."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


# --- content rules ---------------------------------------------------------------------------

_SECRET = re.compile(r"""(?x)
    \b(?:sk|pk|rk)-[A-Za-z0-9_\-]{16,}
  | \bgh[pousr]_[A-Za-z0-9]{20,}
  | \bgithub_pat_[A-Za-z0-9_]{20,}
  | \bgsk_[A-Za-z0-9]{16,}
  | \bAKIA[0-9A-Z]{16}\b
  | \bAIza[0-9A-Za-z_\-]{30,}
  | \bxox[abprs]-[A-Za-z0-9\-]{10,}
  | \beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}
  | -----BEGIN\ [A-Z ]*PRIVATE\ KEY-----
  | (?i:\bbearer\s+[A-Za-z0-9._\-]{16,})
  | (?i:\b(?:pass(?:word|phrase|wd|code)?|pwd|secret|api[\s_-]?key|access[\s_-]?key|
          (?:access|auth|api|bearer|refresh|session)[\s_-]?token|token|credentials?|cookie|
          \.ROBLOSECURITY)\b\s*(?:is|=|:)\s*["']?[^\s"']{4,})
  | _\|WARNING:-DO-NOT-SHARE-THIS
  | \b[A-Fa-f0-9]{32,}\b
  | \b(?=[A-Za-z0-9+_\-]*[0-9])(?=[A-Za-z0-9+_\-]*[A-Z])(?=[A-Za-z0-9+_\-]*[a-z])[A-Za-z0-9+_\-]{40,}
""")

_GRANT = re.compile(r"""(?ix)
    \b(?:ignore|disregard|override|forget)\b.{0,40}\b(?:rules?|instructions?|polic(?:y|ies)|guardrails?|
        restrictions?|safety|system\s+prompt)\b
  | \bwithout\s+(?:asking|approval|permission|confirmation|confirming|review|checking\s+with)\b
  | \b(?:don'?t|do\s+not|never|stop|no\s+need\s+to)\b.{0,30}\b(?:ask(?:ing)?\s+(?:me\s+)?(?:for\s+)?
        (?:permission|approval|confirmation)|confirm(?:ing|ation)?\s+(?:before|with)|
        (?:need|require|wait\s+for)\s+(?:my\s+)?(?:approval|permission|confirmation))\b
  | \b(?:allow(?:ed)?|enable|grant|permit(?:ted)?|turn\s+on|switch\s+on|unlock|give\s+(?:yourself|star|you))\b
        .{0,50}\b(?:permissions?|workspace[_\s]?(?:edit|writes?)|studio[_\s]?edits?|shell|terminal|
        unrestricted|full\s+(?:control|access)|write\s+access|edit\s+access|admin|root|publishing)\b
  | \b(?:disable|bypass|skip|turn\s+off|switch\s+off|remove)\b.{0,40}\b(?:safety|polic(?:y|ies)|approvals?|
        permissions?|confirmations?|sandbox|guardrails?|the\s+review)\b
  | \bauto[-\s]?(?:approve|accept|merge|publish)
  | \b(?:approve|accept|trust)\b.{0,20}\b(?:everything|all|any|every)\b
  | \b(?:studio_edit|workspace_edit|max_calls|tool_workshop_enabled|learning_auto_accept|learning_digest)
  | \byou\s+(?:may|are\s+allowed\s+to|have\s+permission\s+to|are\s+permitted\s+to|are\s+authori[sz]ed\s+to)\b
  | \b(?:change|set|update|modify|edit)\b.{0,30}\b(?:your|star'?s?|the\s+app'?s?)\s+(?:own\s+)?
        (?:settings?|permissions?|polic(?:y|ies)|config(?:uration)?|api\s+keys?|provider)\b
""")


def has_secret(text: str) -> bool:
    """True when the text carries something that looks like a key, token or password."""
    return bool(_SECRET.search(text or ""))


def grants_permission(text: str) -> bool:
    """True when the text reads as an attempt to widen what STAR may do or to change its settings."""
    return bool(_GRANT.search((text or "").replace("’", "'")))


def redact(text: str, limit: int = MAX_EVIDENCE) -> str:
    """Evidence shown at review: bounded, with anything key-like removed."""
    return _SECRET.sub("[removed]", " ".join(str(text or "").split()))[:limit]


def check_lesson_text(text, *, limit: int = MAX_TEXT) -> str:
    """Return the cleaned text of a lesson, or raise LessonRefused."""
    if not isinstance(text, str):
        raise LessonRefused("size", "A lesson must be text")
    cleaned = " ".join(text.split())
    if not 3 <= len(cleaned) <= limit:
        raise LessonRefused("size", f"A lesson must be 3 to {limit} characters")
    if has_secret(cleaned):
        raise LessonRefused("secret", "Lessons cannot contain keys, tokens or passwords")
    if grants_permission(cleaned):
        raise LessonRefused("permission", "Lessons cannot grant permissions or change settings; "
                                          "use Settings for that")
    return cleaned


# --- subjects --------------------------------------------------------------------------------

_STOP = frozenset("""a an the and or but if then so to of in on at for with from by as is are was were be been
 it its this that these those i you we my your our me us do does did don doesn dont not no yes never always use
 using used instead please should would could can will must want need like prefer rather than when where which
 what who how all any every each just only also too very really more most less now going forward future default
 remember make sure keep avoid stop ever again project here there have has had get got put add added write
 writing wrote code script scripts star actually wrong correct right nope incorrect okay ok mine""".split())


def _normal(text: str) -> str:
    return re.sub(r"[\s.!?,;:]+$", "", " ".join(str(text).lower().replace("’", "'").split()))


def subject_tokens(text: str) -> frozenset[str]:
    """The words a lesson is about: identifiers and nouns, without polarity or filler."""
    found = set()
    for token in re.findall(r"[a-z0-9_]+(?:[.:][a-z0-9_]+)*", str(text).lower()):
        if len(token) < 2 or token in _STOP:
            continue
        if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        found.add(token)
    return frozenset(found)


def subject_key(text: str) -> str:
    return " ".join(sorted(subject_tokens(text)))[:400]


def same_subject(first: frozenset[str], second: frozenset[str]) -> bool:
    """Two lessons are about the same thing when at least three quarters of the shorter one's
    subject words are shared. Deliberately strict: a lesson retired by mistake stops being
    used, while two lessons that overlap are both visible on the review page."""
    if not first or not second:
        return False
    if first == second:
        return True
    shared = len(first & second)
    return shared >= 2 and shared / min(len(first), len(second)) >= 0.75


# --- what the owner said ---------------------------------------------------------------------

_FENCE = re.compile(r"```.*?(?:```|\Z)", re.S)
_FILLER = r"(?:(?:please|ok|okay|so|and|also|star|hey|oh|well)[,:.!]?\s+)*"
_PREFERENCE = re.compile(rf"""(?ix)
    ^{_FILLER}(?:you\s+(?:should|must)\s+)?(?:always|never)\b
        (?!\s*,?\s*(?:mind|wondered|thought|knew|liked|loved|wanted|seen|heard|been|had|did|was|got)\b)
  | \bfrom\s+now\s+on\b
  | \bgoing\s+forward\b
  | ^{_FILLER}in\s+(?:the\s+)?future\b
  | \bi\s+(?:really\s+|much\s+|strongly\s+|would\s+|'d\s+|always\s+|usually\s+)?(?:prefer|rather)\b
  | \bi\s+(?:always|never|only)\s+(?:use|want|write|name|put|like)\b
  | \bi\s+(?:do\s+not|don't|dont)\s+(?:like|use)\b
  | \bmy\s+(?:preference|preferred|convention|style\s+is|standard|rule)\b
  | ^{_FILLER}remember\s*(?:that|to|this|:)
  | ^{_FILLER}keep\s+in\s+mind\b
  | ^{_FILLER}(?:don't|do\s+not|dont|stop)\s+(?:ever\s+)?(?:use|using|add|adding|write|writing|put|putting|
        include|including)\b.{{0,120}}\b(?:ever|anymore|any\s+more|again|unless)\b
  | ^{_FILLER}(?:we\s+(?:use|are\s+using|'re\s+using|always|never|follow|prefer)|use|avoid|stick\s+to|follow)\b
        .{{0,120}}\b(?:for|in|across)\s+(?:this|the\s+whole|my|our)\s+(?:project|game|place|codebase)\b(?!')
""")
_OPENER = re.compile(r"""(?ix)^\s*(?:
    no\b(?!\s+(?:problem|worries|rush|need|idea|thanks|thank|way\b))
  | nope\b | wrong\b | incorrect\b | not\s+quite\b | not\s+like\s+that\b
  | that(?:'s|\s+is|\s+was)\s+(?:wrong|incorrect|not\s+(?:right|correct|what\s+i))
  | that\s+(?:isn't|is\s+not|wasn't)\s+(?:right|correct|what\s+i)
  | actually\b
  | you(?:'re|\s+are)\s+wrong\b
  | you\s+(?:got|made|have)\b.{0,30}\b(?:wrong|mistake|error)
  | (?:this|that|it)\s+(?:doesn't|does\s+not|didn't|did\s+not|won't)\s+work
  | stop\s+(?:using|doing|adding)\b
  | (?:don't|do\s+not)\b.{0,60}\binstead\b
  | use\b.{1,80}\binstead\b
)""")
_DIRECTIVE = re.compile(r"""(?ix)
    \buse\b.{1,80}\binstead\b | \binstead\s+of\b
  | \bshould\s+(?:be|use|have|not|never|always)\b
  | \b(?:is|are|was)\s+(?:deprecated|outdated|removed|obsolete)\b
  | \b(?:does\s+not|doesn't|do\s+not|don't)\s+exist\b
  | \b(?:never|always)\b
  | \b(?:don't|do\s+not|stop)\s+us(?:e|ing)\b
  | \bnot\b.{1,40}\bbut\b
  | \b(?:it's|it\s+is|they're|they\s+are)\s+called\b
  | \bthe\s+(?:correct|right|proper)\s+(?:way|name|method|function|api|service|property|syntax)\b
""")
# Words that point at something only visible in that conversation.
_DEICTIC = re.compile(r"""(?ix)
    \b(?:this|that)\s+one\b | \blike\s+(?:this|that)\b | \bsame\s+as\s+(?:before|above)\b
  | \bthe\s+(?:first|second|third|last|other|former|latter|previous|above)\s+
        (?:one|option|version|approach|way|idea|answer|suggestion)\b
  | \boption\s+[a-d1-4]\b
  | \b(?:prefer|rather|like|want|use)\s+(?:it|that|this|those|these|them)\b(?!\s+\w+\s+(?:to|for|in|as)\b)
""")


@dataclass(frozen=True)
class Statement:
    kind: str       # preference | correction
    text: str       # the owner's words, whitespace-normalised
    durable: bool   # True: stands on its own. False: only makes sense next to the answer it follows


def own_words(message: str) -> str:
    """The part of a message the owner wrote as prose: no code fences, no quoted lines."""
    text = _FENCE.sub(" ", str(message or "").replace("’", "'").replace("‘", "'"))
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith((">", "|")))


# A statement is accepted on sight only when the whole message is short enough to be an
# instruction the owner typed. A longer message is usually material with a question about it
# (a pasted page, a forum post, a document, a transcript): what reads like a preference in
# there was written by someone else, so it waits for review like any other candidate.
TYPED_SENTENCES = 4
TYPED_CHARS = 500


def reads_as_typed(message: str) -> bool:
    """True when a chat message is short enough for its statements to be trusted as typed.
    Code fences and quoted lines do not count: "fix this" above a long script is still short."""
    parts = [" ".join(part.split()) for part in re.split(r"(?<=[.!?])\s+|\n+", own_words(message))]
    parts = [part for part in parts if part]
    return len(parts) <= TYPED_SENTENCES and sum(len(part) for part in parts) <= TYPED_CHARS


def owner_statements(message: str, *, after_answer: bool = False) -> list[Statement]:
    """Stated preferences and corrections in one chat message. Conservative on purpose:
    a missed statement costs nothing, a wrong one would follow the owner into later chats."""
    if not isinstance(message, str) or not message.strip() or len(message) > 4000:
        return []   # a long paste is material, not an instruction
    prose = own_words(message)
    sentences = [" ".join(part.split()) for part in re.split(r"(?<=[.!?])\s+|\n+", prose)]
    sentences = [part for part in sentences if part][:12]
    found: list[Statement] = []
    whole = " ".join(sentences)
    if after_answer and sentences and _OPENER.match(sentences[0]) and not whole.rstrip().endswith("?"):
        text = whole
        if len(text) > 400:
            text = ""
            for part in sentences:
                if len(text) + len(part) + 1 > 400:
                    break
                text = (text + " " + part).strip()
        said = subject_tokens(text)
        if text and len(said) >= 1 and len(text) >= 8:
            durable = bool(_DIRECTIVE.search(text)) and not _DEICTIC.search(text) and len(said) >= 2
            found.append(Statement("correction", text, durable))
    for part in sentences:
        if len(found) >= 4:
            break
        if part.endswith("?") or not 8 <= len(part) <= 300 or not _PREFERENCE.search(part):
            continue
        if any(part in other.text for other in found):
            continue
        if len(subject_tokens(part)) < 1:
            continue
        found.append(Statement("preference", part, not _DEICTIC.search(part)))
    return found


# --- records ---------------------------------------------------------------------------------

@dataclass(frozen=True)
class Lesson:
    id: int
    project: str
    kind: str
    text: str
    status: str
    source: str
    source_type: str
    evidence: str
    created: str
    updated: str
    supersedes_id: int | None
    merged_into: int | None
    uses: int
    last_used: str

    def public(self) -> dict:
        """What the review page may show. Nothing here is a secret: text and evidence were filtered on entry."""
        return {**asdict(self), "origin": describe_source(self.source_type, self.source)}


def describe_source(source_type: str, source: str) -> str:
    """One plain sentence about where a lesson came from."""
    where = ""
    found = re.search(r"#(\d+)", source or "")
    if found:
        where = f" (message {found.group(1)})"
    return {
        OWNER: "You said this in a chat" + where,
        MANUAL: "You wrote this in the review panel",
        CONTEXT: "You said this about one answer" + where,
        "feedback": "You rated an answer" + where,
        "retry": "A request failed and you sent it again" + where,
        "verified-fix": "A Luau check failed and the code was repaired" + where,
        "doc": "A documentation search found nothing" + where,
        "summary": "Summarised by the fast model from raw captures",
    }.get(source_type or "", "Stored note")


@dataclass(frozen=True)
class Captured:
    lesson_id: int | None
    status: str          # accepted | candidate | duplicate | refused
    reason: str = ""
    replaced: int | None = None   # the older accepted lesson this one retired


_SELECT = ("SELECT n.id,n.project,n.kind,n.text,n.status,n.source,n.source_type,n.evidence,n.created,"
           "n.updated,n.supersedes_id,n.merged_into,COALESCE(u.uses,0) AS uses,"
           "COALESCE(u.last_used,'') AS last_used FROM notes n LEFT JOIN lesson_use u ON u.note_id=n.id ")


def _lesson(row) -> Lesson:
    return Lesson(id=int(row["id"]), project=row["project"], kind=row["kind"], text=row["text"],
                  status=row["status"] or "", source=row["source"], source_type=row["source_type"] or "",
                  evidence=row["evidence"] or "", created=row["created"], updated=row["updated"] or row["created"],
                  supersedes_id=row["supersedes_id"], merged_into=row["merged_into"],
                  uses=int(row["uses"]), last_used=row["last_used"])


class LessonStore:
    """Lesson records on top of the project knowledge database.

    `record(project, kind)` is called for `lesson_captured`, `lesson_accepted` and
    `lesson_used`, so the local analytics counts come from real events only.
    """

    def __init__(self, home: Path | None = None, *, knowledge: KnowledgeStore | None = None, record=None):
        if knowledge is None and home is None:
            raise ValueError("A STAR data folder or an open knowledge store is required")
        self._owns = knowledge is None
        self.knowledge = knowledge if knowledge is not None else KnowledgeStore(Path(home) / "knowledge")
        self.db = self.knowledge.db
        self._record = record

    def close(self) -> None:
        if self._owns:
            self.knowledge.close()

    def _begin(self) -> None:
        """Start a write transaction (the connection may already be inside one of its own)."""
        if not self.db.in_transaction:
            self.db.execute("BEGIN IMMEDIATE")

    def _count(self, project: str, kind: str, detail: str = "") -> None:
        if self._record is not None:
            try:
                self._record(project, kind, detail=detail)
            except Exception:
                pass   # a metrics problem never loses a lesson

    # -- reading ---------------------------------------------------------------------------

    def get(self, project: str, lesson_id: int) -> Lesson:
        if isinstance(lesson_id, bool) or not isinstance(lesson_id, int) or lesson_id < 1:
            raise ValueError("Invalid lesson identifier")
        row = self.db.execute(_SELECT + "WHERE n.id=? AND n.project=? AND n.status IS NOT NULL",
                              (lesson_id, _project(project))).fetchone()
        if row is None:
            raise ValueError("Lesson not found in this project")
        return _lesson(row)

    def list(self, project: str, status: str | None = None, *, limit: int = 200) -> list[Lesson]:
        if status is not None and status not in STATUSES:
            raise ValueError("Unknown lesson status")
        if not 1 <= limit <= 500:
            raise ValueError("limit must be 1..500")
        sql, values = _SELECT + "WHERE n.project=? AND n.status IS NOT NULL", [_project(project)]
        if status is not None:
            sql += " AND n.status=?"
            values.append(status)
        rows = self.db.execute(sql + " ORDER BY n.id DESC LIMIT ?", (*values, limit)).fetchall()
        return [_lesson(row) for row in rows]

    def counts(self, project: str) -> dict:
        """Lessons of this project by status, plus how often accepted ones were placed in a turn."""
        found = {name: 0 for name in STATUSES}
        for status, total in self.db.execute(
                "SELECT status,COUNT(*) FROM notes WHERE project=? AND status IS NOT NULL GROUP BY status",
                (_project(project),)):
            if status in found:
                found[status] = int(total)
        uses = self.db.execute(
            "SELECT COALESCE(SUM(u.uses),0) FROM lesson_use u JOIN notes n ON n.id=u.note_id WHERE n.project=?",
            (project,)).fetchone()[0]
        return {**found, "pending": found["candidate"], "uses": int(uses)}

    # -- writing ---------------------------------------------------------------------------

    def _existing(self, project: str, text: str, source_type: str, source: str):
        """A lesson that already says this, or one already made from the same signal."""
        if source_type not in (OWNER, MANUAL, CONTEXT):
            row = self.db.execute(
                "SELECT id,status FROM notes WHERE project=? AND source=? AND source_type=? "
                "AND status IS NOT NULL ORDER BY id DESC LIMIT 1", (project, source, source_type)).fetchone()
            if row is not None:
                return row
        wanted = _normal(text)
        for row in self.db.execute(
                "SELECT id,status,text FROM notes WHERE project=? AND status IN ('accepted','candidate','rejected') "
                "ORDER BY id DESC LIMIT 400", (project,)):
            if _normal(row["text"]) == wanted:
                return row
        return None

    def _insert(self, *, project: str, kind: str, text: str, source: str, source_type: str,
                evidence: str, accept: bool, revision: str) -> Captured:
        project = _project(project)
        if kind not in LESSON_KINDS:
            raise ValueError("A lesson is a preference, correction, pitfall or fact")
        if source_type not in SOURCE_TYPES:
            raise ValueError("Unknown lesson source")
        if not isinstance(source, str) or not source.strip() or len(source) > 300:
            raise ValueError("A lesson needs a source reference")
        try:
            text = check_lesson_text(text)
        except LessonRefused as refused:
            return Captured(None, "refused", refused.reason)
        known = self._existing(project, text, source_type, source)
        if known is not None:
            return Captured(int(known["id"]), "duplicate", known["status"])
        stamp = now()
        try:
            self._begin()
            lesson_id = int(self.db.execute(
                """INSERT INTO notes(project,kind,text,source,revision,reviewed,created,
                                     status,source_type,updated,subject,evidence)
                   VALUES(?,?,?,?,?,0,?,'candidate',?,?,?,?)""",
                (project, kind, text, source.strip(), "candidate", stamp, source_type, stamp,
                 subject_key(text), redact(evidence))).lastrowid)
            replaced = self._accept(project, lesson_id, revision, stamp) if accept else None
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        if source_type != "summary":
            # A summary rewords notes that were counted when they were captured.
            self._count(project, "lesson_captured", source_type)
        if accept:
            self._count(project, "lesson_accepted", "automatic")
        return Captured(lesson_id, "accepted" if accept else "candidate", replaced=replaced)

    def _accept(self, project: str, lesson_id: int, revision: str, stamp: str, *,
                keep_both: bool = False) -> int | None:
        """Mark one lesson trusted and retire older accepted lessons on the same subject.
        Runs inside the caller's transaction, so there is never a moment with both trusted.
        Returns the id of the newest lesson it retired, if any."""
        row = self.db.execute("SELECT text FROM notes WHERE id=? AND project=?", (lesson_id, project)).fetchone()
        subject = subject_tokens(row["text"])
        replaced = None
        if not keep_both:
            for other in self.db.execute(
                    "SELECT id,text FROM notes WHERE project=? AND status='accepted' AND reviewed=1 AND id!=? "
                    "ORDER BY id DESC LIMIT 400", (project, lesson_id)).fetchall():
                if same_subject(subject, subject_tokens(other["text"])):
                    self.db.execute("UPDATE notes SET reviewed=0,status='superseded',updated=? WHERE id=?",
                                    (stamp, other["id"]))
                    replaced = replaced or int(other["id"])
        self.db.execute(
            "UPDATE notes SET reviewed=1,status='accepted',revision=?,updated=?,"
            "supersedes_id=COALESCE(?,supersedes_id) WHERE id=? AND project=?",
            (revision, stamp, replaced, lesson_id, project))
        return replaced

    def capture_owner(self, *, project: str, kind: str, text: str, message: str, source: str,
                      evidence: str = "", auto_accept: bool = True) -> Captured:
        """A durable statement the owner typed. `text` must be the owner's own words: it has to
        appear in `message`, the chat message it was taken from, or nothing is stored as theirs."""
        if _normal(" ".join(str(text).split())) not in _normal(own_words(message)):
            raise PermissionError("Only the owner's own words can be recorded as the owner's statement")
        return self._insert(project=project, kind=kind, text=text, source=source, source_type=OWNER,
                            evidence=evidence, accept=auto_accept is True, revision="owner-stated")

    def capture_inferred(self, *, project: str, kind: str, text: str, source_type: str, source: str,
                         evidence: str = "") -> Captured:
        """Anything STAR worked out, or took from a tool, a page, the documentation or a file.
        Always a candidate: there is no argument that makes this path trusted."""
        if source_type not in INFERRED:
            raise ValueError("Unknown inferred lesson source")
        if source_type in MACHINE_MADE:
            marks = ",".join("?" for _ in (*MACHINE_MADE, "summary"))
            waiting = self.db.execute(
                f"SELECT COUNT(*) FROM notes WHERE project=? AND status='candidate' AND source_type IN ({marks})",
                (_project(project), *MACHINE_MADE, "summary")).fetchone()[0]
            if waiting >= MAX_MACHINE_WAITING:
                return Captured(None, "refused", "full")
        return self._insert(project=project, kind=kind, text=text, source=source, source_type=source_type,
                            evidence=evidence, accept=False, revision="candidate")

    def _reviewable(self, project: str, lesson_id: int, human_approved) -> Lesson:
        if human_approved is not True:
            raise PermissionError("Only the owner can review a lesson")
        return self.get(project, lesson_id)

    def _note_review(self, project: str, lesson_id: int, what: str, stamp: str) -> None:
        # The same append-only audit row review_note() writes for any reviewed note.
        self.db.execute(
            "INSERT INTO notes(project,kind,text,source,revision,reviewed,created) VALUES(?,?,?,?,?,0,?)",
            (project, "observation", f"Reviewed note {lesson_id}: {what}", f"review:{lesson_id}", "accepted", stamp))

    def approve(self, project: str, lesson_id: int, *, human_approved: bool = False, text: str | None = None,
                kind: str | None = None, keep_both: bool = False) -> Lesson:
        """The owner accepts a lesson, optionally with their own wording. Restoring a replaced
        lesson passes keep_both so it does not in turn retire the newer one."""
        lesson = self._reviewable(project, lesson_id, human_approved)
        if lesson.status == "merged":
            raise ValueError("This capture was folded into a summary; review the summary instead")
        new_text = check_lesson_text(text if text is not None else lesson.text,
                                     limit=1200 if lesson.source == APPROVED_DECISION_SOURCE else MAX_TEXT)
        new_kind = kind if kind is not None else lesson.kind
        if new_kind not in RECALLED_KINDS:
            raise ValueError("Unknown lesson kind")
        stamp = now()
        try:
            self._begin()
            self.db.execute("UPDATE notes SET text=?,kind=?,subject=? WHERE id=? AND project=?",
                            (new_text, new_kind, subject_key(new_text), lesson_id, lesson.project))
            was_accepted = lesson.status == "accepted"
            self._accept(lesson.project, lesson_id,
                         "owner-approved" if lesson.source_type not in (OWNER, MANUAL) or text is not None
                         else "owner-stated", stamp, keep_both=keep_both or was_accepted)
            if not was_accepted:
                self._note_review(lesson.project, lesson_id, "The owner approved this lesson in STAR", stamp)
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        if not was_accepted:
            self._count(lesson.project, "lesson_accepted", "reviewed")
        return self.get(project, lesson_id)

    def edit(self, project: str, lesson_id: int, *, human_approved: bool = False, text: str,
             kind: str | None = None) -> Lesson:
        """Change the wording. An accepted lesson stays accepted (the owner wrote the new words);
        a candidate stays a candidate until it is approved."""
        lesson = self._reviewable(project, lesson_id, human_approved)
        if lesson.status == "accepted":
            return self.approve(project, lesson_id, human_approved=True, text=text, kind=kind)
        new_text = check_lesson_text(text)
        new_kind = kind if kind is not None else lesson.kind
        if new_kind not in RECALLED_KINDS:
            raise ValueError("Unknown lesson kind")
        self.db.execute("UPDATE notes SET text=?,kind=?,subject=?,updated=? WHERE id=? AND project=?",
                        (new_text, new_kind, subject_key(new_text), now(), lesson_id, lesson.project))
        self.db.commit()
        return self.get(project, lesson_id)

    def reject(self, project: str, lesson_id: int, *, human_approved: bool = False) -> Lesson:
        """Stop using a lesson and keep the record, so the same capture is not offered again."""
        lesson = self._reviewable(project, lesson_id, human_approved)
        self.db.execute("UPDATE notes SET reviewed=0,status='rejected',updated=? WHERE id=? AND project=?",
                        (now(), lesson_id, lesson.project))
        self.db.commit()
        return self.get(project, lesson_id)

    def delete(self, project: str, lesson_id: int, *, human_approved: bool = False) -> None:
        """Remove a lesson and its use count for good."""
        lesson = self._reviewable(project, lesson_id, human_approved)
        try:
            self._begin()
            self.db.execute("DELETE FROM lesson_use WHERE note_id=?", (lesson_id,))
            # Raw notes folded into a deleted summary have nothing left to be reviewed through:
            # they wait again, marked as already seen so the summary step does not remake it.
            self.db.execute(
                "UPDATE notes SET status='candidate',revision='candidate-digested',merged_into=NULL,updated=? "
                "WHERE merged_into=? AND project=? AND status='merged'", (now(), lesson_id, lesson.project))
            self.db.execute("UPDATE notes SET merged_into=NULL WHERE merged_into=? AND project=?",
                            (lesson_id, lesson.project))
            self.db.execute("DELETE FROM notes WHERE id=? AND project=? AND status IS NOT NULL",
                            (lesson_id, lesson.project))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def withdraw(self, project: str, source_type: str, source: str) -> int:
        """Drop a still-unreviewed capture whose signal was taken back (a removed thumb)."""
        if source_type not in INFERRED:
            raise ValueError("Only inferred captures can be withdrawn")
        done = self.db.execute(
            "DELETE FROM notes WHERE project=? AND source=? AND source_type=? AND status='candidate'",
            (_project(project), source, source_type)).rowcount
        self.db.commit()
        return int(done)

    def export(self, project: str) -> dict:
        """Every lesson of one project, with provenance, as plain data for the owner to keep."""
        rows = self.db.execute(_SELECT + "WHERE n.project=? AND n.status IS NOT NULL ORDER BY n.id DESC",
                               (_project(project),)).fetchall()
        return {"format": "star-lessons-v1", "project": project, "exported": now(),
                "counts": self.counts(project), "lessons": [_lesson(row).public() for row in rows]}

    def page(self, project: str) -> list[Lesson]:
        """What the review page shows: the newest lessons of every status (LIST_WINDOW each),
        newest first. Loading "the newest 200 of anything" would let waiting notes push an
        accepted lesson off the page while it is still used in answers."""
        found: list[Lesson] = []
        for status, limit in LIST_WINDOW.items():
            found += self.list(project, status, limit=limit)
        return sorted(found, key=lambda lesson: -lesson.id)

    # -- using -----------------------------------------------------------------------------

    def recall(self, project: str, prompt: str, *, limit: int = 6, max_chars: int = 1400) -> list[Lesson]:
        """Accepted lessons of this project for one turn: those about the prompt first, then the
        standing preferences and corrections, newest first, without repeats, within a budget."""
        if not 1 <= limit <= 20 or not 100 <= max_chars <= 8000:
            raise ValueError("Recall budget outside the supported range")
        marks = ",".join("?" for _ in RECALLED_KINDS)
        rows = self.db.execute(
            _SELECT + f"WHERE n.project=? AND n.status='accepted' AND n.reviewed=1 AND n.kind IN ({marks}) "
            "ORDER BY n.id DESC LIMIT ?", (_project(project), *RECALLED_KINDS, RECALL_SCAN)).fetchall()
        wanted = subject_tokens(str(prompt)[:4000])
        seen: set[str] = set()
        ranked = []
        for row in rows:
            key = _normal(row["text"])
            if key in seen:
                continue
            seen.add(key)
            overlap = len(subject_tokens(row["text"]) & wanted)
            standing = row["kind"] in STANDING_KINDS
            if overlap or standing:
                ranked.append((-overlap, not standing, -int(row["id"]), row))
        ranked.sort(key=lambda item: item[:3])
        chosen, size = [], 0
        for *_, row in ranked:
            cost = min(len(row["text"]), RECALL_CLIP) + LINE_OVERHEAD
            if size + cost > max_chars:
                continue
            chosen.append(_lesson(row))
            size += cost
            if len(chosen) >= limit:
                break
        return chosen

    def mark_used(self, project: str, lessons: list[Lesson]) -> None:
        """Count one use for each lesson that was placed in the context of an answered turn."""
        if not lessons:
            return
        stamp = now()
        for lesson in lessons:
            self.db.execute(
                "INSERT INTO lesson_use(note_id,uses,last_used) VALUES(?,1,?) "
                "ON CONFLICT(note_id) DO UPDATE SET uses=uses+1,last_used=excluded.last_used", (lesson.id, stamp))
        self.db.commit()
        self._count(project, "lesson_used", str(len(lessons)))


def context_lines(lessons: list[Lesson]) -> str:
    """The lines a turn carries, one lesson per line (a decision typed on several lines is
    joined). The id is the provenance: the review page shows where each came from."""
    return "\n".join(f"[#{lesson.id} {lesson.kind}] {' '.join(lesson.text.split())[:RECALL_CLIP]}"
                     for lesson in lessons)


# The lessons heading in any letter case, apostrophe or spacing, and the start of a lesson line.
_HEADING_COPY = re.compile(r"owner\W{0,3}s\s+lessons", re.I)
_LINE_COPY = re.compile(r"\[#(\d+)\s+([a-z]+)\]", re.I)


def guard_sections(sections) -> list[tuple[str, str]]:
    """Only the section written by this module may look like lessons.

    The heading asks the model to apply what follows, which no other reference text is
    allowed to ask. A stored note, a web result or a documentation passage that repeats the
    heading or a "[#12 preference]" line would borrow that standing, so both are rewritten
    in every other section. The text itself stays, as the reference material it is.
    """
    guarded = []
    for heading, text in sections:
        if heading != LESSONS_HEADING and text:
            text = _HEADING_COPY.sub("(a heading copied from the app was removed here)", str(text))
            text = _LINE_COPY.sub(r"(#\1 \2)", text)
        guarded.append((heading, text))
    return guarded


# --- capture after a turn --------------------------------------------------------------------

def _fix_summary(before: str, after: str, limit: int = 500) -> str:
    """The changed lines of a repair, as short -/+ pairs."""
    lines = [line for line in difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0)
             if line[:1] in "+-" and not line.startswith(("+++", "---")) and line[1:].strip()]
    return "\n".join(lines)[:limit]


def _tool_events(messages) -> list[tuple[str, dict, dict]]:
    """(tool name, arguments, result) for the documentation tools in one run's transcript."""
    calls: dict[str, tuple[str, dict]] = {}
    found = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            if function.get("name") in ("star_docs_search", "star_luau_check"):
                try:
                    arguments = json.loads(function.get("arguments") or "{}")
                except (TypeError, ValueError):
                    arguments = {}
                calls[str(call.get("id"))] = (function["name"], arguments if isinstance(arguments, dict) else {})
        if message.get("role") == "tool" and str(message.get("tool_call_id")) in calls:
            name, arguments = calls[str(message.get("tool_call_id"))]
            try:
                outer = json.loads(message.get("content") or "{}")
                result = json.loads(outer.get("output") or "{}") if not outer.get("isError") else None
            except (TypeError, ValueError):
                result = None
            if isinstance(result, dict):
                found.append((name, arguments, result))
    return found


def capture_turn(store: LessonStore, *, project: str, chat_id: str | None, owner_text: str,
                 turn: dict | None = None, grounding=None, messages=None, auto_accept: bool = True) -> dict:
    """Record what one finished turn taught. Regular expressions and a few rows; never a model call.

    `turn` is Conversations.turn_context(): the message being answered and the turn before it.
    Returns counts for the interface: {'accepted': n, 'candidates': n, 'refused': n, 'replaced': n,
    'ids': [...]}.
    """
    summary = {"accepted": 0, "candidates": 0, "refused": 0, "replaced": 0, "ids": []}
    chat = chat_id or "legacy"
    turn = turn or {}
    message_id = turn.get("message_id")
    previous = turn.get("previous") or {}
    here = f"{chat}#{message_id}" if message_id else chat

    def note(result: Captured) -> None:
        if result.status == "accepted":
            summary["accepted"] += 1
            summary["replaced"] += 1 if result.replaced else 0
        elif result.status == "candidate":
            summary["candidates"] += 1
        elif result.status == "refused":
            summary["refused"] += 1
        if result.lesson_id and result.status in ("accepted", "candidate"):
            summary["ids"].append(result.lesson_id)

    answered = previous.get("outcome") == "answered"
    context = ""
    if answered:
        context = (f"Follows STAR's answer (message {previous.get('answer_id')}): "
                   f"\"{str(previous.get('answer') or '')[:420]}\" Question before it: "
                   f"\"{str(previous.get('text') or '')[:200]}\"")
    # Accepted on sight only in a message short enough to be a typed instruction; statements
    # found in longer material are kept as the owner's words but wait for review.
    typed = reads_as_typed(owner_text)
    for statement in owner_statements(owner_text, after_answer=answered):
        if statement.durable:
            note(store.capture_owner(project=project, kind=statement.kind, text=statement.text,
                                     message=owner_text, source=f"chat:{here}", evidence=context,
                                     auto_accept=auto_accept and typed))
        else:
            note(store.capture_inferred(project=project, kind=statement.kind, text=statement.text,
                                        source_type=CONTEXT, source=f"chat:{here}", evidence=context))

    if (previous.get("outcome") == "failed" and _normal(previous.get("text") or "") == _normal(owner_text)
            and previous.get("message_id")):
        note(store.capture_inferred(
            project=project, kind="pitfall", source_type="retry", source=f"retry:{chat}#{previous['message_id']}",
            text=f"A request failed and was sent again. Request: \"{' '.join(owner_text.split())[:200]}\"",
            evidence=f"Failure shown to the owner: {str(previous.get('detail') or '')[:400]}"))

    if grounding is not None:
        if getattr(grounding, "status", "") == "empty" and getattr(grounding, "query", ""):
            note(store.capture_inferred(
                project=project, kind="fact", source_type="doc", source=f"docs-search:{here}",
                text="The indexed Roblox and Luau documentation had no passage for: "
                     f"\"{' '.join(str(grounding.query).split())[:240]}\"",
                evidence="Automatic documentation search before the answer returned no passages."))
        for record in getattr(grounding, "checks", None) or []:
            if record.get("repaired") and record.get("errors"):
                first = record["errors"][0]
                note(store.capture_inferred(
                    project=project, kind="pitfall", source_type="verified-fix",
                    source=f"luau-check:{here}/block{record.get('block', 1)}",
                    text=f"Luau check failed in generated code: {str(first.get('message', ''))[:220]} "
                         f"(line {first.get('line', '?')}). The corrected code passed the check.",
                    evidence="Fix that passed:\n" + str(record.get("fix") or "(not recorded)")))

    failing = None
    for index, (name, arguments, result) in enumerate(_tool_events(messages)):
        if name == "star_docs_search" and not result.get("passages") and arguments.get("query"):
            note(store.capture_inferred(
                project=project, kind="fact", source_type="doc", source=f"docs-search:{here}/tool{index}",
                text="The indexed Roblox and Luau documentation had no passage for: "
                     f"\"{' '.join(str(arguments['query']).split())[:240]}\"",
                evidence="star_docs_search returned no passages during the turn."))
        elif name == "star_luau_check" and result.get("ran") is True:
            if result.get("ok") is not True and result.get("errors"):
                failing = failing or (arguments.get("code") or "", result["errors"])
            elif result.get("ok") is True and failing is not None:
                code, errors = failing
                failing = None
                note(store.capture_inferred(
                    project=project, kind="pitfall", source_type="verified-fix",
                    source=f"luau-check:{here}/tool{index}",
                    text=f"Luau check failed in generated code: {str(errors[0].get('message', ''))[:220]} "
                         f"(line {errors[0].get('line', '?')}). A later version passed the check.",
                    evidence="Fix that passed:\n" + _fix_summary(str(code), str(arguments.get("code") or ""))))
    return summary


# --- feedback on one answer ------------------------------------------------------------------

def record_feedback(store: LessonStore, *, project: str, chat_id: str, message_id: int, value: str,
                    question: str, answer: str) -> Captured | None:
    """A thumb on an answer becomes a candidate (the lesson would be drawn from the model's
    own answer, so it is inferred). Changing or removing the thumb withdraws an unreviewed one."""
    if value not in ("up", "down", ""):
        raise ValueError("Feedback must be up, down or empty")
    source = f"feedback:{chat_id}#{message_id}"
    store.withdraw(project, "feedback", source)
    if not value:
        return None
    asked = " ".join(str(question or "").split())[:200]
    text = (f"An answer was marked helpful. Question: \"{asked}\"" if value == "up"
            else f"An answer was marked not helpful. Question: \"{asked}\"")
    return store.capture_inferred(project=project, kind="fact" if value == "up" else "pitfall",
                                  source_type="feedback", source=source, text=text,
                                  evidence=f"STAR's answer began: \"{str(answer or '')[:500]}\"")


# --- bridge ----------------------------------------------------------------------------------

LESSON_ACTIONS = frozenset({"listLessons", "reviewLesson", "exportLessons", "messageFeedback"})
REVIEW_OPERATIONS = frozenset({"approve", "edit", "reject", "delete", "restore"})


def _metrics(home: Path):
    from .analytics import AnalyticsStore
    return AnalyticsStore(Path(home) / "analytics.sqlite3")


def learning_status(home: Path, project: str) -> dict:
    """Counts for the interface (pending badge, review page). Zeroes when nothing was ever stored."""
    try:
        store = LessonStore(home)
    except (sqlite3.Error, OSError, ValueError):
        return {name: 0 for name in (*STATUSES, "pending", "uses")}
    try:
        return store.counts(project)
    except ValueError:
        return {name: 0 for name in (*STATUSES, "pending", "uses")}
    finally:
        store.close()


def write_export(destination: Path, data: dict) -> dict:
    """Save an export where the owner chose. Returns a nonsecret receipt for the interface."""
    destination = Path(destination).expanduser()
    if not destination.suffix:
        destination = destination.with_suffix(".json")
    temporary = destination.with_name(destination.name + ".part")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)
    return {"filename": destination.name, "count": len(data.get("lessons") or []),
            "saved_to_user_selected_location": True}


def handle_action(home: Path, project: str, action: str, body: dict) -> dict:
    """The lesson actions of the desktop bridge. Every change is an explicit owner action from
    the interface; none of them can touch settings, permissions or another project."""
    if action not in LESSON_ACTIONS:
        raise PermissionError("Action not permitted")
    if not isinstance(body, dict):
        raise ValueError("Invalid request")
    metrics = _metrics(home)
    store = LessonStore(home, record=metrics.record)
    try:
        if action == "listLessons":
            status = body.get("status")
            status = None if status in (None, "", "all") else str(status)
            lessons = store.page(project) if status is None else store.list(project, status, limit=200)
            return {"project": project, "counts": store.counts(project),
                    "lessons": [lesson.public() for lesson in lessons]}
        if action == "exportLessons":
            return store.export(project)
        if action == "reviewLesson":
            operation = body.get("op")
            if operation not in REVIEW_OPERATIONS:
                raise ValueError("Unknown review operation")
            lesson_id = body.get("id")
            approved = body.get("approved") is True
            text = body.get("text")
            kind = body.get("kind")
            if text is not None and not isinstance(text, str):
                raise ValueError("Lesson text must be text")
            if kind is not None and not isinstance(kind, str):
                raise ValueError("Unknown lesson kind")
            if operation == "delete":
                store.delete(project, lesson_id, human_approved=approved)
                lesson = None
            elif operation == "reject":
                lesson = store.reject(project, lesson_id, human_approved=approved)
            elif operation == "edit":
                if text is None:
                    raise ValueError("Write the new wording first")
                lesson = store.edit(project, lesson_id, human_approved=approved, text=text, kind=kind)
            else:
                lesson = store.approve(project, lesson_id, human_approved=approved, text=text, kind=kind,
                                       keep_both=operation == "restore")
            return {"lesson": lesson.public() if lesson else None, "counts": store.counts(project)}
        # messageFeedback
        from .desktop_core import Conversations
        message_id = body.get("messageId")
        value = body.get("value")
        if isinstance(message_id, bool) or not isinstance(message_id, int) or value not in ("up", "down", ""):
            raise ValueError("Invalid feedback")
        chats = Conversations(Path(home) / "conversations.sqlite3")
        try:
            rated = chats.set_feedback(project, message_id, value)
        finally:
            chats.close()
        captured = record_feedback(store, project=project, chat_id=rated["chat_id"], message_id=message_id,
                                   value=value, question=rated["question"], answer=rated["answer"])
        return {"messageId": message_id, "value": value, "counts": store.counts(project),
                "lesson_id": captured.lesson_id if captured else None}
    finally:
        store.close()
        metrics.close()
