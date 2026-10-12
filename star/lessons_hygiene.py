"""Read-only hygiene proposals for Lesson records and star-lessons-v1 exports.

No store is opened by the analysis functions. Embeddings and override observations are
optional caller-supplied inputs, never fetched from a model or inferred from recall counts.
The CLI reads SQLite in mode=ro rather than opening LessonStore (which can migrate it).
Nothing here approves, edits, retires or merges a lesson; use the existing review page.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from itertools import combinations
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
from typing import TYPE_CHECKING, Any
import unicodedata

if TYPE_CHECKING:
    from .lessons import Lesson

Record = Mapping[str, Any]
Embedding = Callable[[str], Sequence[float]]
ACTIVE = frozenset({"accepted", "candidate"})
_STATUSES = ACTIVE | {"rejected", "superseded", "merged"}
# Unlike recall's subject_tokens, directives are parsed separately before polarity is
# discarded. A high token/embedding score must never merge "use X" with "never use X".
_STOP = frozenset("""a an the and or but to of in on at for with from by as is are was were be
been it its this that these those i you we my your our me us do does did not no never always
use using uses instead please should would could can will must want need like prefer rather
than when where which what who how all any every each just also too very really more most
now going forward future default remember make sure keep avoid stop ever again project
here there have has had get got put add write writing code script scripts""".split())
_WORD = re.compile(r"[^\W_]+(?:[_.:][^\W_]+)*", re.UNICODE)
_NEGATION = re.compile(r"\b(?:not|never|no|without|unless|avoid|stop|disable|exclude|disallow|forbid|remove)\b|n't\b")
_VERBS = {
    "use": ("use", 1), "using": ("use", 1), "uses": ("use", 1),
    "avoid": ("use", -1), "stop using": ("use", -1),
    "enable": ("enable", 1), "turn on": ("enable", 1),
    "disable": ("enable", -1), "turn off": ("enable", -1),
    "include": ("include", 1), "exclude": ("include", -1),
    "allow": ("allow", 1), "disallow": ("allow", -1), "forbid": ("allow", -1),
    "keep": ("keep", 1), "remove": ("keep", -1),
    "put": ("put", 1), "prefer": ("use", 1),
    "block": ("allow", -1), "accept": ("accept", 1), "reject": ("accept", -1),
    "save": ("save", 1), "cache": ("cache", 1), "validate": ("validate", 1),
    "send": ("send", 1), "call": ("call", 1),
}
_VERB_PATTERN = "|".join(sorted(_VERBS, key=len, reverse=True))
_DIRECTIVE = re.compile(
    rf"\b(?:(?P<negative>never|do not|don't|dont|must not|should not|cannot|can't|not)\s+)?"
    rf"(?P<verb>{_VERB_PATTERN})\b\s+(?P<target>.+)"
)
_CLAUSE = re.compile(
    rf"[.!?;]\s+|[,;]\s*(?=(?:always|never|do not|don't|{_VERB_PATTERN})\b)"
    rf"|\s+(?:but|and)\s+(?=(?:always|never|do not|don't|{_VERB_PATTERN})\b)"
)
_CONDITION = re.compile(r"\b(?:if|unless|when|except|only)\b")
_NUMBERS = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?(?!\w)")
_PROJECT_NAME = re.compile(
    r"\b[Pp]roject\s+(?:[\"`']([^\"`'\n]+)[\"`']|([A-Z][\w.-]*))"
)


@dataclass(frozen=True)
class Evidence:
    lesson_id: int
    source: str
    evidence: str


@dataclass(frozen=True)
class OverrideObservation:
    """An observed outcome, not a recall count. source identifies a distinct reviewed turn."""
    lesson_id: int
    source: str
    overridden: bool


@dataclass(frozen=True)
class Proposal:
    kind: str                     # merge | contradiction | stale | scope
    lesson_ids: tuple[int, ...]
    project: str
    reason: str
    evidence: tuple[Evidence, ...]
    suggested_text: str | None = None
    keep_id: int | None = None
    suggested_project: str | None = None
    token_overlap: float | None = None
    embedding_similarity: float | None = None


@dataclass(frozen=True)
class HygieneReport:
    as_of: str
    scanned: int
    proposals: tuple[Proposal, ...]
    warnings: tuple[str, ...]
    review_required: bool = True
    format: str = "star-lessons-hygiene-v1"

    def public(self) -> dict:
        return asdict(self)


def _normal(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().replace("’", "'").split())


def _tokens(text: str) -> frozenset[str]:
    words = set()
    for word in _WORD.findall(_normal(text)):
        if word in _STOP:
            continue
        if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        words.add(word)
    return frozenset(words)


def _overlap(first: frozenset[str], second: frozenset[str]) -> tuple[float, float]:
    if not first or not second:
        return 0.0, 0.0
    shared = len(first & second)
    return shared / min(len(first), len(second)), shared / max(len(first), len(second))


def token_overlap(first: str, second: str) -> float:
    """Fraction of the shorter subject covered. Pair matching also checks longer coverage."""
    return _overlap(_tokens(first), _tokens(second))[0]


def _same_topic(first: frozenset[str], second: frozenset[str]) -> bool:
    short, long = _overlap(first, second)
    return bool(first and second) and (first == second or (
        len(first & second) >= 2 and short >= 0.75 and long >= 0.5))


def _directives(text: str) -> tuple[tuple[str, int, frozenset[str]], ...]:
    found = []
    for clause in _CLAUSE.split(_normal(text)):
        match = _DIRECTIVE.search(clause)
        if not match:
            continue
        verb = match["verb"]
        action, sign = _VERBS[verb]
        if match["negative"]:
            sign *= -1
        target = match["target"]
        # Preserve the direction of a replacement, not just its shared bag of words.
        choices = re.split(r"(?:\s+(?:instead of|rather than)|,?\s+not)\s+", target, maxsplit=1)
        if verb == "prefer" and len(choices) == 1:
            choices = re.split(r"\s+over\s+", target, maxsplit=1)
        found.append((action, sign, _tokens(choices[0])))
        if len(choices) == 2:
            found.append((action, -sign, _tokens(choices[1])))
    return tuple(found)


def _opposed(first: str, second: str) -> bool:
    return any(action == other_action and sign != other_sign and _same_topic(topic, other_topic)
               for action, sign, topic in _directives(first)
               for other_action, other_sign, other_topic in _directives(second))


def _merge_safe(first: str, second: str) -> bool:
    """Conservative guards also apply to embedding-only matches."""
    if _opposed(first, second):
        return False
    a, b = _normal(first), _normal(second)
    numbers_a, numbers_b = set(_NUMBERS.findall(a)), set(_NUMBERS.findall(b))
    if numbers_a and numbers_b and numbers_a != numbers_b:
        return False
    # Unmatched exceptions/conditions or negation can reverse an otherwise similar rule.
    if bool(_CONDITION.search(a)) != bool(_CONDITION.search(b)):
        return False
    directives_a, directives_b = _directives(a), _directives(b)
    signs_a, signs_b = {item[1] for item in directives_a}, {item[1] for item in directives_b}
    if signs_a != signs_b:
        return False
    if bool(_NEGATION.search(a)) != bool(_NEGATION.search(b)):
        # Equivalent negative imperatives such as "never use" and "avoid" are safe.
        if signs_a != {-1}:
            return False
    # Mixed instructions need matching signed subjects; cosine alone cannot establish this.
    if len(signs_a) > 1:
        return all(any(action == other_action and sign == other_sign and _same_topic(topic, other_topic)
                       for other_action, other_sign, other_topic in other)
                   for own, other in ((directives_a, directives_b), (directives_b, directives_a))
                   for action, sign, topic in own)
    return True


def _records(lessons: Iterable[Lesson | Record]) -> list[dict]:
    rows, seen = [], set()
    for lesson in lessons:
        if isinstance(lesson, Mapping):
            row = dict(lesson)
        elif is_dataclass(lesson) and not isinstance(lesson, type):
            row = asdict(lesson)
        else:
            raise ValueError("Expected Lesson records or exported lesson objects")
        lesson_id = row.get("id")
        if type(lesson_id) is not int or lesson_id < 1 or lesson_id in seen:
            raise ValueError("Lesson identifiers must be positive and unique")
        for field in ("project", "kind", "text", "status", "source", "evidence", "created", "last_used"):
            if not isinstance(row.get(field), str):
                raise ValueError(f"Lesson {lesson_id}: {field} must be text")
        if not row["text"].strip() or row["status"] not in _STATUSES:
            raise ValueError(f"Lesson {lesson_id}: invalid text or status")
        if type(row.get("uses")) is not int or row["uses"] < 0:
            raise ValueError(f"Lesson {lesson_id}: uses must be a nonnegative integer")
        seen.add(lesson_id)
        rows.append(row)
    return sorted(rows, key=lambda row: row["id"])


def _evidence(*rows: Record) -> tuple[Evidence, ...]:
    return tuple(Evidence(row["id"], row["source"], row["evidence"]) for row in rows)


def _stamp(value: str | datetime) -> datetime:
    stamp = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _positive_integer(value: int, name: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _threshold(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 1:
        raise ValueError(f"{name} must be greater than zero and at most one")


def _vectors(rows: list[dict], embed: Embedding | None, warnings: list[str]) -> dict[int, tuple[float, ...]]:
    if embed is None:
        return {}
    vectors, cache = {}, {}
    for row in rows:
        text = row["text"]
        if text not in cache:
            try:
                raw = embed(text)
                if isinstance(raw, (str, bytes)):
                    raise ValueError("Not a vector")
                vector = tuple(float(value) for value in raw)
                if not vector or not all(math.isfinite(value) for value in vector):
                    raise ValueError("Non-finite or empty vector")
                scale = max(abs(value) for value in vector)
                if not scale:
                    raise ValueError("Zero vector")
                scaled = tuple(value / scale for value in vector)
                norm = math.sqrt(math.fsum(value * value for value in scaled))
                cache[text] = tuple(value / norm for value in scaled)
            except Exception:
                # An optional provider failure must not lose lexical findings or echo its
                # exception (which may contain credentials or transport details).
                cache[text] = None
        if cache[text] is None:
            warnings.append(f"Lesson {row['id']}: embedding unavailable; using token overlap only")
        else:
            vectors[row["id"]] = cache[text]
    return vectors


def _specificity(row: Record) -> tuple[int, int, bool, int]:
    text = _normal(row["text"])
    return (len(_tokens(text)), len(set(_CONDITION.findall(text))) + len(set(_NUMBERS.findall(text))),
            row["status"] == "accepted", -row["id"])


def _named_projects(text: str, names: Iterable[str]) -> tuple[str, ...]:
    normal = _normal(text)
    matches = [(match.start(), match.end(), name) for name in names
               for match in re.finditer(r"(?<!\w)" + re.escape(_normal(name)) + r"(?!\w)", normal)]
    # "Harbor Tools" must not also count as "Harbor" at the same location. A separate
    # mention of Harbor elsewhere still counts as a second project.
    found = {name for start, end, name in matches if not any(
        other_start <= start and end <= other_end and other_end - other_start > end - start
        for other_start, other_end, _ in matches)}
    generic = {"this", "that", "all", "the", "a", "an", "our", "my", "your", "settings",
               "configuration", "folder", "files", "name", "names", "scope", "scoped", "specific",
               "root", "structure", "layout", "templates", "template", "workflow", "guidelines"}
    for match in _PROJECT_NAME.finditer(text):
        name = (match[1] or match[2]).strip().rstrip(".")
        if not name or _normal(name) in generic:
            continue
        # An unquoted single-word guess must not shorten a known multiword project.
        if match[2] and any(_normal(known).startswith(_normal(name) + " ") for known in found):
            continue
        found.add(next((known for known in names if _normal(known) == _normal(name)), name))
    unique = {}
    for name in sorted(found):
        unique.setdefault(_normal(name), name)
    return tuple(unique.values())


def _override_history(observations: Iterable[OverrideObservation]) -> dict[int, dict[str, bool]]:
    history: dict[int, dict[str, bool]] = defaultdict(dict)
    for item in observations:
        _positive_integer(item.lesson_id, "Override lesson identifier")
        if not isinstance(item.source, str) or not item.source.strip() or type(item.overridden) is not bool:
            raise ValueError("Override observations need a source and a boolean outcome")
        source = item.source.strip()
        if source in history[item.lesson_id] and history[item.lesson_id][source] != item.overridden:
            raise ValueError("Conflicting outcomes for the same override observation")
        history[item.lesson_id][source] = item.overridden
    return history


def build_report(lessons: Iterable[Lesson | Record], *, as_of: datetime,
                 stale_days: int = 90, embed: Embedding | None = None,
                 token_threshold: float = 0.8, embedding_threshold: float = 0.93,
                 project_names: Iterable[str] = (), global_projects: Iterable[str] = ("global",),
                 overrides: Iterable[OverrideObservation] = (), minimum_overrides: int = 3) -> HygieneReport:
    """Deterministic proposals, with no mutation of records, stores or review state.

    Only accepted/candidate records participate in pair/scope checks. Only accepted
    records can be stale: unreviewed candidates have deliberately never been recalled.
    as_of is explicit; naive historical timestamps are interpreted as UTC. Pair checks
    stay within an exact project identifier. "global" is a lint convention, NOT a new
    recall scope; callers may explicitly supply other global labels and project names.
    """
    _positive_integer(stale_days, "stale_days")
    _positive_integer(minimum_overrides, "minimum_overrides")
    _threshold(token_threshold, "token_threshold")
    _threshold(embedding_threshold, "embedding_threshold")
    if not isinstance(as_of, datetime):
        raise ValueError("as_of must be a datetime")
    clock = _stamp(as_of)
    rows = _records(lessons)
    active = [row for row in rows if row["status"] in ACTIVE]
    labels, supplied_names = tuple(global_projects), tuple(project_names)
    if any(not isinstance(name, str) for name in labels):
        raise ValueError("Global labels must be strings")
    if any(not isinstance(name, str) or not name.strip() for name in supplied_names):
        raise ValueError("Project names must be nonempty strings")
    global_labels = {_normal(name) for name in labels}
    names = tuple(sorted(set(supplied_names) | {
        row["project"] for row in rows if row["project"] and _normal(row["project"]) not in global_labels
    }))
    warnings: list[str] = []
    proposals: list[Proposal] = []
    history = _override_history(overrides)
    if not history:
        warnings.append("Recall counts do not record overrides; always-overridden checks need supplied observations")
    scopes = {row["id"]: _named_projects(row["text"], names) for row in active}
    for row in active:
        named = scopes[row["id"]]
        if _normal(row["project"]) in global_labels and len(named) == 1:
            proposals.append(Proposal("scope", (row["id"],), row["project"],
                                      "Names one project but is labelled global; review its scope",
                                      _evidence(row), suggested_project=named[0]))

    vectors = _vectors(active, embed, warnings)
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in active:
        groups[row["project"]].append(row)
    for project in sorted(groups):
        for first, second in combinations(groups[project], 2):
            # A global note naming a project is already suspect; do not fold its wording
            # into generic global guidance, or into guidance naming a different project.
            if _normal(project) in global_labels and scopes[first["id"]] != scopes[second["id"]]:
                continue
            a, b = first["text"], second["text"]
            short, long = _overlap(_tokens(a), _tokens(b))
            if _opposed(a, b):
                proposals.append(Proposal("contradiction", (first["id"], second["id"]), project,
                                          "Same subject with opposing instructions; review context and exceptions",
                                          _evidence(first, second), token_overlap=short))
                continue
            if not _merge_safe(a, b):
                continue
            cosine = None
            va, vb = vectors.get(first["id"]), vectors.get(second["id"])
            if va is not None and vb is not None:
                if len(va) != len(vb):
                    warnings.append("Embedding dimensions differ; affected pairs use token overlap only")
                else:
                    cosine = max(-1.0, min(1.0, math.fsum(x * y for x, y in zip(va, vb))))
            exact = _normal(a).rstrip(".!?") == _normal(b).rstrip(".!?")
            lexical = exact or (short >= token_threshold and long >= 0.5 and len(_tokens(a) & _tokens(b)) >= 2)
            semantic = cosine is not None and cosine >= embedding_threshold
            if not lexical and not semantic:
                continue
            keep = max((first, second), key=_specificity)
            proposals.append(Proposal(
                "merge", (first["id"], second["id"]), project,
                "Near duplicate (" + ("token overlap" if lexical else "injected embedding")
                + "); retain the more specific existing wording and both evidence records after review",
                _evidence(first, second), suggested_text=keep["text"], keep_id=keep["id"],
                token_overlap=short, embedding_similarity=cosine))

    for row in active:
        if row["status"] != "accepted":
            continue
        # updated is an edit/review time, not a use: it must not hide an old unused rule.
        stamp = row["last_used"] if row["uses"] else row["created"]
        try:
            created = _stamp(row["created"])
            used = _stamp(stamp)
            if created > clock or used > clock or used < created or (not row["uses"] and row["last_used"]):
                raise ValueError("Inconsistent use history")
            if (clock - used).total_seconds() >= stale_days * 86400:
                reason = "Never recalled since creation" if row["uses"] == 0 else "Not recalled since last use"
                proposals.append(Proposal("stale", (row["id"],), row["project"],
                                          f"{reason} for at least {stale_days} days; review before retiring",
                                          _evidence(row)))
        except (ValueError, OverflowError):
            warnings.append(f"Lesson {row['id']}: invalid or inconsistent timestamps; inactivity not inferred")
        outcomes = history.get(row["id"], {})
        if len(outcomes) >= minimum_overrides and all(outcomes.values()):
            observed = tuple(Evidence(row["id"], source, "Observed override") for source in sorted(outcomes))
            proposals.append(Proposal("stale", (row["id"],), row["project"],
                                      f"Overridden in all {len(outcomes)} supplied observations; unobserved turns are unknown",
                                      _evidence(row) + observed))
    proposals.sort(key=lambda item: (item.kind, item.lesson_ids, item.reason))
    return HygieneReport(clock.isoformat(), len(rows), tuple(proposals), tuple(sorted(set(warnings))))


def read_database(path: Path) -> list[dict]:
    """Read all lesson rows, not the review page's limited window. Never create/migrate a DB.

    mode=ro (not immutable=1) matters: an active app can have recent lessons in its WAL.
    The connection may participate in SQLite WAL coordination, but cannot write records.
    """
    uri = path.expanduser().resolve().as_uri() + "?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        rows = db.execute(
            "SELECT n.id,n.project,n.kind,n.text,n.status,n.source,n.source_type,n.evidence,n.created,"
            "COALESCE(n.updated,n.created) AS updated,n.supersedes_id,n.merged_into,"
            "COALESCE(u.uses,0) AS uses,COALESCE(u.last_used,'') AS last_used "
            "FROM notes n LEFT JOIN lesson_use u ON u.note_id=n.id "
            "WHERE n.status IS NOT NULL ORDER BY n.id"
        ).fetchall()
        return [{**dict(row), "evidence": row["evidence"] or "", "source_type": row["source_type"] or ""}
                for row in rows]
    finally:
        db.close()


def _default_home() -> Path:
    # Same paths as desktop_core.app_data, without importing the desktop/model/keyring
    # stack just to read a file. A parity test pins this intentionally small duplication.
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "STAR"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "star-ai"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    report = commands.add_parser("report", help="Print JSON proposals; never apply them")
    source = report.add_mutually_exclusive_group()
    source.add_argument("--input", type=Path, help="A star-lessons-v1 export or JSON list of lesson records")
    source.add_argument("--home", type=Path, help="STAR data folder (defaults to the app's data folder)")
    report.add_argument("--project", help="Report only this exact project identifier")
    report.add_argument("--project-name", action="append", default=[], help="Known project name, repeatable")
    report.add_argument("--global-project", action="append", help="Global label, repeatable (default: global)")
    report.add_argument("--stale-days", type=int, default=90)
    report.add_argument("--as-of", help="ISO timestamp; defaults to current UTC time")
    report.add_argument("--overrides", type=Path, help="JSON list of explicit override observations")
    args = parser.parse_args(argv)
    try:
        missing = False
        if args.input:
            raw = json.loads(args.input.read_text(encoding="utf-8"))
            rows = raw.get("lessons") if isinstance(raw, dict) else raw
            if not isinstance(rows, list):
                raise ValueError("Input must be a lesson list or an export with a lessons list")
        else:
            path = (args.home if args.home is not None else _default_home()) / "knowledge" / "knowledge.sqlite3"
            missing = not path.exists()
            rows = [] if missing else read_database(path)
        rows = _records(rows)
        labels = args.global_project if args.global_project is not None else ["global"]
        names = set(args.project_name) | {row["project"] for row in rows
                                        if row["project"] and _normal(row["project"]) not in {_normal(x) for x in labels}}
        observations = []
        if args.overrides:
            raw = json.loads(args.overrides.read_text(encoding="utf-8"))
            if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
                raise ValueError("Overrides must be a JSON list of observation objects")
            observations = [OverrideObservation(**item) for item in raw]
        result = build_report(
            (row for row in rows if args.project is None or row["project"] == args.project),
            as_of=_stamp(args.as_of) if args.as_of is not None else datetime.now(timezone.utc),
            stale_days=args.stale_days, project_names=names, global_projects=labels, overrides=observations,
        ).public()
        if missing:
            result["warnings"] = (*result["warnings"], "No lesson database exists; nothing was created")
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    except (OSError, ValueError, TypeError, OverflowError, sqlite3.Error):
        # Keep local paths, raw input and provider details out of diagnostics. A malformed
        # database must not be opened by a writer as a fallback to 'repair' it.
        print("Unable to report: check the input schema, timestamps, options and existing lesson database", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
