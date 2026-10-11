"""Read-only Studio milestone catalog; loading never executes Luau or opens Studio.

Checks are deliberately limited to a small inspection-only Luau subset. This is
static screening, not a general-purpose Luau sandbox or proof of runtime behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

STUDIO_DIR = Path(__file__).resolve().parents[1] / "evals" / "studio"
GAMES = ("obby", "tycoon", "rounds")
MAX_CHECK_CHARS = 4096
_MAX_DESCRIPTION_CHARS = 300
_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_STRING = re.compile(r'''"[^"\\\r\n]*"|'[^'\\\r\n]*' ''', re.VERBOSE)
_DANGEROUS = re.compile(
    r"\b(?:Destroy|Remove|ClearAllChildren|Clone|SetAttribute|"
    r"HttpService|loadstring|getfenv|setfenv|require|rawset|setmetatable|"
    r"getmetatable|debug|collectgarbage|coroutine|task|spawn|delay|wait|"
    r"Instance|FireServer|FireClient|FireAllClients|InvokeServer|"
    r"InvokeClient|Connect|Once|Disconnect|BindToClose|PivotTo|"
    r"MoveTo|Teleport|Create|SetAsync|UpdateAsync|InsertService|"
    r"HttpGet|HttpPost|RequestAsync|PostAsync|GetAsync)\b",
    re.IGNORECASE,
)
_METHOD = re.compile(rf":\s*({_IDENTIFIER})\s*\(")
_DOT_CALL = re.compile(rf"(?<!\.)\.(?!\.)\s*{_IDENTIFIER}\s*\(")
_FREE_CALL = re.compile(rf"(?<![\w.:])({_IDENTIFIER})\s*\(")
_WRITE = re.compile(r"(?<![<>=~])=(?!=)")
_PROPERTY_WRITE = re.compile(rf"(?:\.\s*{_IDENTIFIER}|\])\s*=(?!=)")
_ALLOWED_METHODS = frozenset({
    "GetService", "FindFirstChild", "GetChildren", "GetDescendants", "IsA",
    "GetAttribute", "find", "match", "sub", "lower",
})
_ALLOWED_FUNCTIONS = frozenset({"ipairs", "pairs", "tostring", "tonumber", "type", "typeof"})
_ALLOWED_SERVICES = frozenset({"ReplicatedStorage", "ServerScriptService", "ServerStorage", "StarterGui"})
_SERVICE_CALL = re.compile(r":\s*GetService\s*\(")
_SERVICE_LITERAL = re.compile(r''':\s*GetService\s*\(\s*(["'])([A-Za-z]+)\1\s*\)''')
_LOCAL = re.compile(rf"\blocal\s+({_IDENTIFIER})\s*=")
_LOOP = re.compile(rf"\bfor\s+({_IDENTIFIER}(?:\s*,\s*{_IDENTIFIER})*)\s+in\b")
_NUMERIC_LOOP = re.compile(rf"\bfor\s+({_IDENTIFIER})\s*=")


@dataclass(frozen=True)
class StudioMilestone:
    id: str
    description: str
    check: str


def validate_check(check: str) -> None:
    """Reject writes, dynamic calls and privileged APIs in the supported Luau subset.

    The deny-list is defense-in-depth: method and free-function calls are also
    allowlisted, property writes and indirect indexing are forbidden, and all
    GetService arguments must be fixed, inspected service names. Do not run
    arbitrary user-supplied Luau based on this static check alone.
    """
    if not isinstance(check, str) or not check.strip() or len(check.encode("utf-8")) > MAX_CHECK_CHARS:
        raise ValueError("Studio check must be a nonempty, bounded Luau snippet")
    if any(char in check for char in ("\\", chr(96), "\x00")) or "--" in check:
        raise ValueError("Studio check contains unsupported quoting or comments")
    # Mask literals at their original offsets so strings cannot spoof a safe
    # service call or an unapproved method invocation.
    code = _STRING.sub(lambda match: ' ' * (match.end() - match.start()), check)
    if any(char in code for char in ('"', "'", "[", "]", ";")):
        raise ValueError("Studio check contains unsupported syntax or indirect indexing")
    if _DANGEROUS.search(code) or re.search(r"\bHttpService\b", check, re.IGNORECASE):
        raise ValueError("Studio check references a forbidden API")
    if re.search(r"\b(?:function|while|repeat|until|goto|continue|break)\b|::|\+=|-=", code):
        raise ValueError("Studio check contains an unsupported control or mutation form")
    if _PROPERTY_WRITE.search(code) or re.search(rf"\.\s*{_IDENTIFIER}\s*,", code):
        raise ValueError("Studio check cannot assign DataModel properties")
    if _DOT_CALL.search(code):
        raise ValueError("Studio check cannot call dotted or dynamically selected functions")
    if set(_METHOD.findall(code)) - _ALLOWED_METHODS:
        raise ValueError("Studio check uses an unapproved method")
    if set(_FREE_CALL.findall(code)) - _ALLOWED_FUNCTIONS:
        raise ValueError("Studio check uses an unapproved function")
    for call in _SERVICE_CALL.finditer(code):
        literal = _SERVICE_LITERAL.match(check, call.start())
        if not literal or literal.group(2) not in _ALLOWED_SERVICES:
            raise ValueError("Studio check requires literal, approved GetService arguments")

    # Assignments may only initialize or update local variables (or numeric loop
    # counters). In particular, assigning to global names is not permitted.
    locals_ = set(_LOCAL.findall(code))
    for bindings in _LOOP.findall(code):
        locals_.update(name.strip() for name in bindings.split(","))
    locals_.update(_NUMERIC_LOOP.findall(code))
    for assignment in _WRITE.finditer(code):
        prefix = code[:assignment.start()]
        target = re.search(rf"({_IDENTIFIER})\s*$", prefix)
        if not target or target.group(1) not in locals_ or "," in prefix.rsplit("\n", 1)[-1]:
            raise ValueError("Studio check may only assign local variables")
    if not re.search(r"\breturn\s+true\s*,", code) or not re.search(r"\breturn\s+false\s*,", code):
        raise ValueError("Studio check needs success and failure detail returns")


def load_milestones(game: str, *, directory: Path | None = None) -> list[StudioMilestone]:
    """Load one game manifest in source order, without evaluating its checks."""
    if game not in GAMES:
        raise ValueError("Unknown Studio milestone game")
    root = STUDIO_DIR if directory is None else Path(directory)
    raw = json.loads((root / f"{game}.json").read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"game", "milestones"} or raw["game"] != game:
        raise ValueError("Invalid Studio milestone manifest")
    rows = raw["milestones"]
    if not isinstance(rows, list) or not rows or len(rows) > 32:
        raise ValueError("Studio milestone list must contain 1 to 32 entries")
    result = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "description", "check"}:
            raise ValueError("Studio milestone needs id, description and check")
        identifier, description, check = row["id"], row["description"], row["check"]
        if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
            raise ValueError("Invalid Studio milestone ID")
        if identifier in seen:
            raise ValueError("Duplicate Studio milestone ID")
        if (not isinstance(description, str) or not description.strip()
                or len(description) > _MAX_DESCRIPTION_CHARS):
            raise ValueError("Invalid Studio milestone description")
        validate_check(check)
        seen.add(identifier)
        result.append(StudioMilestone(identifier, description, check))
    return result


def load_all_milestones(*, directory: Path | None = None) -> list[StudioMilestone]:
    """Load obby, tycoon and rounds in that order, requiring globally unique IDs."""
    result = []
    seen = set()
    for game in GAMES:
        for milestone in load_milestones(game, directory=directory):
            if milestone.id in seen:
                raise ValueError("Duplicate Studio milestone ID across games")
            seen.add(milestone.id)
            result.append(milestone)
    return result
