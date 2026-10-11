"""Engine API names in a Luau answer, checked against the official API reference.

The Luau compiler and type checker on the STAR Server know nothing about Roblox classes, so a
block that "compiles and passes type analysis" can still call a method that does not exist
(`GuiService.ViewportSize`), use an enum item that was never there, or a member the reference
marks as deprecated. STAR Knowledge answers "does this exact name exist" in a few milliseconds
(`KnowledgeClient.api_lookup`), so this module finds the names a block provably uses and asks.

Only uses with solid evidence are checked, because `thing.Name` is also how a child instance is
read (`ReplicatedStorage.Remotes`, `workspace.Map`):

  * a method call on a receiver whose class is known:          `GuiService:GetGuiInset()`
  * an assignment to a property of such a receiver:            `label.TextScaled = true`
  * an event that is connected or waited on:                   `Players.PlayerAdded:Connect(`
  * a property named in GetPropertyChangedSignal:              `camera:GetPropertyChangedSignal("ViewportSize")`
  * enum items, class names given as strings, library and datatype functions.

A receiver's class is known when the code says so: `game:GetService("X")`, `Instance.new("X")`,
`FindFirstChildOfClass("X")`, a parameter or local annotated with an engine class, and the globals
`game` and `workspace`. Anything else is left alone; nothing here guesses.

`requested_names` is the other direction: engine names the request explicitly asks to be used.
Pure functions plus one injected `lookup(symbols) -> list[dict]`; no network code lives here.
"""
from __future__ import annotations

import re

MAX_SYMBOLS = 64            # per block; a lookup takes a few milliseconds per symbol
LOOKUP_BATCH = 8            # the service accepts at most 8 names per request
MAX_FINDINGS = 6

UNKNOWN = "UnknownAPI"
DEPRECATED = "DeprecatedAPI"
REQUESTED = "RequestedAPI"
ADVISORY_KINDS = frozenset({DEPRECATED, REQUESTED})     # worth one repair, never "did not compile"
API_KINDS = frozenset({UNKNOWN, DEPRECATED, REQUESTED})

_LIBRARIES = ("math", "string", "table", "task", "os", "coroutine", "bit32", "utf8", "buffer", "debug", "vector")
_DATATYPES = ("Vector3", "Vector2", "CFrame", "UDim2", "UDim", "Color3", "TweenInfo", "RaycastParams",
              "OverlapParams", "NumberSequence", "ColorSequence", "NumberRange", "Rect", "Region3", "Random",
              "DateTime", "BrickColor", "NumberSequenceKeypoint", "ColorSequenceKeypoint", "Font",
              "PhysicalProperties", "Instance")
_GLOBAL_CLASSES = {"game": "DataModel", "workspace": "Workspace"}
# Where a misplaced member usually lives. Only asked about when a member was not found on its class.
_COMMON_OWNERS = ("Workspace", "Camera", "Players", "Player", "Humanoid", "Animator", "AnimationTrack", "BasePart",
                  "Model", "Instance", "GuiObject", "GuiBase2d", "TextLabel", "ScreenGui", "UserInputService",
                  "RunService", "GuiService", "TweenService", "Tween", "Tool", "DataModel")
_NAME = r"[A-Za-z_]\w*"
_STRING = r"""["']([A-Za-z]\w*)["']"""

# The call must be the whole value: `game:GetService("ReplicatedStorage"):WaitForChild("Remote")` is the remote.
_WHOLE = r"\s*\)(?!\s*[.:\[])"
_SERVICE = re.compile(rf"\b({_NAME})\s*(?::\s*[\w.?]+\s*)?=\s*game\s*:\s*GetService\(\s*{_STRING}{_WHOLE}")
_NEW = re.compile(rf"\b({_NAME})\s*(?::\s*[\w.?]+\s*)?=\s*Instance\.new\(\s*{_STRING}(?:\s*,[^()\n]*)?{_WHOLE}")
_OF_CLASS = re.compile(rf"\b({_NAME})\s*(?::\s*[\w.?]+\s*)?=\s*[^\n=]*?:\s*(?:FindFirstChildOfClass|"
                       rf"FindFirstChildWhichIsA|FindFirstAncestorOfClass|FindFirstAncestorWhichIsA)\(\s*{_STRING}"
                       rf"(?:\s*,[^()\n]*)?{_WHOLE}")
_LOCAL_TYPED = re.compile(rf"\blocal\s+({_NAME})\s*:\s*([A-Z][A-Za-z0-9]*)\??\s*(?==|\n|$)")
_PARAMS = re.compile(r"\bfunction\b[^\n(]*\(([^)]*)\)")
_PARAM_TYPED = re.compile(rf"^\s*({_NAME})\s*:\s*([A-Z][A-Za-z0-9]*)\??\s*$")
_OWN_TYPE = re.compile(rf"\b(?:export\s+)?type\s+({_NAME})\b")
_CLASS_STRING = re.compile(rf"(?:Instance\.new|:\s*GetService|:\s*IsA|:\s*FindFirstChildOfClass|"
                           rf":\s*FindFirstChildWhichIsA|:\s*FindFirstAncestorOfClass|"
                           rf":\s*FindFirstAncestorWhichIsA)\(\s*{_STRING}")
_ENUM = re.compile(r"(?<![\w.])Enum\.([A-Z]\w*)(?:\.([A-Za-z_]\w*))?")
_STATIC = re.compile(rf"(?<![\w.:])({'|'.join(_LIBRARIES + _DATATYPES)})\.({_NAME})\s*\(")
_ENUM_OWN = frozenset({"GetEnumItems", "FromName", "FromValue", "Name", "Value", "EnumType"})


def blank(code: str, *, strings: bool = True) -> str:
    """The code with comments (and, by default, string contents) replaced by spaces.

    Every character keeps its offset and every line break stays, so a match position in the
    result is the same position, and the same line, in the original.
    """
    out, i, n = [], 0, len(code)

    def spaces(text: str) -> str:
        return "".join("\n" if ch == "\n" else " " for ch in text)

    def long_bracket(at: int) -> int:
        """End index (exclusive) of a `[[ ... ]]` / `[=[ ... ]=]` that starts at `at`, or -1."""
        m = re.match(r"\[(=*)\[", code[at:])
        if not m:
            return -1
        end = code.find("]" + m.group(1) + "]", at + len(m.group(0)))
        return n if end == -1 else end + len(m.group(1)) + 2

    while i < n:
        ch = code[i]
        if code.startswith("--", i):
            end = long_bracket(i + 2)
            if end == -1:
                end = code.find("\n", i)
                end = n if end == -1 else end
            out.append(spaces(code[i:end]))
            i = end
        elif ch in "\"'`":
            j = i + 1
            while j < n and code[j] != ch and code[j] != "\n":
                j += 2 if code[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(ch + spaces(code[i + 1:j - 1]) + (code[j - 1] if j - 1 > i else "") if strings else code[i:j])
            i = j
        elif ch == "[" and long_bracket(i) != -1:
            end = long_bracket(i)
            out.append(spaces(code[i:end]) if strings else code[i:end])
            i = end
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _line(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def receivers(code: str) -> dict[str, set[str]]:
    """Variable name -> the engine classes the code itself says it holds."""
    text = blank(code, strings=False)
    own_types = set(_OWN_TYPE.findall(text))
    found: dict[str, set[str]] = {name: {cls} for name, cls in _GLOBAL_CLASSES.items()}
    for pattern in (_SERVICE, _NEW, _OF_CLASS, _LOCAL_TYPED):
        for name, cls in pattern.findall(text):
            if cls not in own_types:
                found.setdefault(name, set()).add(cls)
    for params in _PARAMS.findall(text):
        for part in params.split(","):
            m = _PARAM_TYPED.match(part)
            if m and m.group(2) not in own_types:
                found.setdefault(m.group(1), set()).add(m.group(2))
    # A name the code also binds to something else (a plain local, a loop variable) is left
    # alone only when that binding has no class at all; two classes are both tried.
    return found


def references(code: str) -> list[dict]:
    """Every checkable API use: {"symbols": [alternatives], "line": n, "shown": text, "owner": class}.

    A use is fine when ANY of its alternative symbols exists (a name bound to two classes).
    """
    bare = blank(code)                      # no comments, no string contents
    quoted = blank(code, strings=False)     # no comments, strings kept (class names live in strings)
    refs: list[dict] = []
    seen: set[tuple] = set()

    def add(symbols: list[str], position: int, shown: str, owner: str = "", kind: str = "member") -> None:
        key = tuple(symbols)
        if key not in seen and len(refs) < MAX_SYMBOLS:
            seen.add(key)
            refs.append({"symbols": symbols, "line": _line(code, position), "shown": shown, "owner": owner,
                         "kind": kind})

    for m in _CLASS_STRING.finditer(quoted):
        add([m.group(1)], m.start(), m.group(1), kind="class")
    for m in _ENUM.finditer(bare):
        if m.group(2) and m.group(2) not in _ENUM_OWN:
            add([f"Enum.{m.group(1)}.{m.group(2)}"], m.start(), f"Enum.{m.group(1)}.{m.group(2)}",
                owner="Enum." + m.group(1), kind="enum")
        else:
            add([f"Enum.{m.group(1)}"], m.start(), f"Enum.{m.group(1)}", kind="enum")
    for m in _STATIC.finditer(bare):
        add([f"{m.group(1)}.{m.group(2)}"], m.start(), f"{m.group(1)}.{m.group(2)}", owner=m.group(1),
            kind="function")
    for name, classes in receivers(code).items():
        ordered = sorted(classes)
        head = rf"(?<![\w.:]){re.escape(name)}"
        for m in re.finditer(rf"{head}\s*:\s*({_NAME})\s*\(", bare):
            add([f"{cls}:{m.group(1)}" for cls in ordered], m.start(), f"{name}:{m.group(1)}", ordered[0])
        for m in re.finditer(rf"{head}\.({_NAME})\s*(?:[-+*/%^]|\.\.)?=(?!=)", bare):
            add([f"{cls}.{m.group(1)}" for cls in ordered], m.start(), f"{name}.{m.group(1)}", ordered[0])
        for m in re.finditer(rf"{head}\.({_NAME})\s*:\s*(?:Connect|Once|Wait|ConnectParallel)\s*\(", bare):
            add([f"{cls}.{m.group(1)}" for cls in ordered], m.start(), f"{name}.{m.group(1)}", ordered[0])
        for m in re.finditer(rf"{head}\s*:\s*GetPropertyChangedSignal\(\s*{_STRING}\s*\)", quoted):
            add([f"{cls}.{m.group(1)}" for cls in ordered], m.start(), f"{name}.{m.group(1)}", ordered[0])
    return refs


def _lookup_all(lookup, symbols: list[str]) -> dict[str, dict]:
    answers: dict[str, dict] = {}
    unique = list(dict.fromkeys(symbols))
    for start in range(0, len(unique), LOOKUP_BATCH):
        for item in lookup(unique[start:start + LOOKUP_BATCH]) or []:
            if isinstance(item, dict) and isinstance(item.get("symbol"), str):
                answers[item["symbol"]] = item
    return answers


def _members(overview: dict | None) -> str:
    """'properties: ...; methods: ...' from a class overview entry, bounded."""
    text = (overview or {}).get("text") or ""
    at = text.find("Members of ")
    if at == -1:
        return ""
    lines = [line.strip() for line in text[at:].splitlines()[1:4] if ":" in line]
    return "; ".join(lines)[:420]


def _deprecation(entry: dict) -> str:
    text = " ".join(str(entry.get("text") or "").split())
    at = text.find("DEPRECATED:")
    if at == -1:
        return ""
    sentence = text[at + len("DEPRECATED:"):].strip()
    return sentence.split(". ")[0].rstrip(".")[:200]


def diagnose(code: str, lookup) -> tuple[list[dict], int]:
    """(findings, number of names checked). `lookup` is KnowledgeClient.api_lookup.

    Raises whatever `lookup` raises (OSError when the service is down): the caller then says
    nothing about API names instead of claiming they were checked.
    """
    refs = references(code)
    if not refs:
        return [], 0
    answers = _lookup_all(lookup, [s for ref in refs for s in ref["symbols"]])
    # A member can only be called "missing" when its owner is a class the reference knows.
    owners = sorted({s.split(":")[0].split(".")[0] for ref in refs if ref["kind"] == "member"
                     for s in ref["symbols"]})
    overviews = _lookup_all(lookup, owners) if owners else {}
    # `math.isFinite`: the same name in another letter case is nearly always what was meant.
    respelled = {s: s.split(".")[0] + "." + s.split(".", 1)[1].lower() for ref in refs if ref["kind"] == "function"
                 for s in ref["symbols"] if not (answers.get(s) or {}).get("found")}
    close = _lookup_all(lookup, [v for k, v in respelled.items() if v != k]) if respelled else {}
    # A member that its class does not have often belongs to another class the code is near
    # (`GuiService.ViewportSize` is `Camera.ViewportSize`): say where the name really lives.
    absent = {ref["symbols"][0].replace(":", ".").split(".", 1)[1] for ref in refs if ref["kind"] == "member"
              and not any((answers.get(s) or {}).get("found") for s in ref["symbols"])}
    nearby = list(dict.fromkeys([*owners, *_COMMON_OWNERS]))
    elsewhere = _lookup_all(lookup, [f"{cls}.{member}" for member in sorted(absent)[:3] for cls in nearby]) if absent else {}
    findings: list[dict] = []
    checked = 0
    for ref in refs:
        entries = [answers.get(s) for s in ref["symbols"]]
        if any(e is None for e in entries):
            continue                                    # the service did not answer for it: no claim
        hits = [e for e in entries if e.get("found")]
        if ref["kind"] == "member":
            known = [s for s in ref["symbols"] if (overviews.get(s.split(":")[0].split(".")[0]) or {}).get("found")]
            if not known:
                continue                                # not an engine class after all (the user's own type)
            if not hits and len(known) < len(ref["symbols"]):
                continue                                # one of its possible classes is unknown: no verdict
        checked += 1
        if not hits:
            hint = ""
            if ref["kind"] == "class":
                message = f"`{ref['shown']}` is not a class in the official Roblox API reference."
            elif ref["kind"] == "enum":
                message = f"`{ref['shown']}` is not in the official Roblox API reference (no such enum or enum item)."
            elif ref["kind"] == "function":
                message = f"`{ref['shown']}` is not in the official reference (no such function in `{ref['owner']}`)."
                other = respelled.get(ref["symbols"][0], "")
                if (close.get(other) or {}).get("found"):
                    hint = f"The reference has `{other}`."
            else:
                listed = _members(overviews.get(ref["owner"]))
                message = (f"`{ref['shown']}` is not in the official Roblox API reference: class {ref['owner']} has no "
                           f"member `{ref['symbols'][0].replace(':', '.').split('.', 1)[1]}`.")
                member = ref["symbols"][0].replace(":", ".").split(".", 1)[1]
                homes = [cls for cls in nearby if (elsewhere.get(f"{cls}.{member}") or {}).get("found")
                         and not elsewhere[f"{cls}.{member}"].get("deprecated")][:3]
                hint = (f"`{member}` is a member of {', '.join(homes)}: use it on an object of that class. " if homes
                        else "") + (f"Members of {ref['owner']}: {listed}" if listed else "")
            findings.append({"line": ref["line"], "column": 0, "kind": UNKNOWN, "message": message,
                             **({"hint": hint} if hint else {})})
        elif all(e.get("deprecated") for e in hits):
            why = _deprecation(hits[0])
            findings.append({"line": ref["line"], "column": 0, "kind": DEPRECATED,
                             "message": f"`{hits[0]['symbol']}` is deprecated in the official Roblox API reference."
                                        + (f" {why}." if why else "")})
    findings.sort(key=lambda f: (f["kind"] != UNKNOWN, f["line"]))
    return findings[:MAX_FINDINGS], checked


# --- names the request asks for ---------------------------------------------------------------

_FENCED = re.compile(r"```.*?(?:```|\Z)", re.S)
_CODE_LINE = re.compile(
    r"^\s*(?:local\s|function\b|end\b|return\b|if\b.*\bthen\s*$|for\b.*\bdo\s*$|while\b.*\bdo\s*$|else\b|elseif\b|--|"
    r"[\w.\[\]\"']+\s*(?:[-+*/]|\.\.)?=\s|[\w.:]+\(.*\)\s*$|[})\]]+\s*$)")
_SYMBOL = re.compile(r"(?<![\w.:])([A-Za-z_]\w*)([.:])([A-Z][A-Za-z0-9]+)\b")
_CAMEL = re.compile(r"(?<![\w.:\"'/])([A-Z][A-Za-z0-9]{2,40})\b(?![\w]*[.:]\w)")
_DIRECTIVE = re.compile(
    r"\b(?:use[sd]?|using|with|via|through|call(?:s|ing)?|give|set(?:s|ting)?|add(?:s|ing)?|connect(?:ed|s)?|"
    r"driven\s+by|wrap(?:ped|s)?|create[sd]?|sav(?:e|es|ed)|flush(?:es)?|must|should)\b"
    r"[^.;!?\n]{0,70}$", re.I)
_NEGATION = re.compile(
    r"\b(?:not|no|never|without|instead\s+of|rather\s+than|avoid(?:s|ing)?|don'?t|deprecated|replace[sd]?|"
    r"remove[sd]?|stop\s+using)\b[^.;!?\n]{0,70}$", re.I)
_INSTANCE_DIRECTIVE = re.compile(
    r"\b(?:use[sd]?|using|add(?:s|ing)?|create[sd]?|insert(?:s|ing)?)\s+(?:an?|the|one)\s+(?:[\w-]+\s+){0,2}$", re.I)
_SERVICE_TAG = re.compile(r"Tags:[^\n]*\bService\b")
# Places and script containers say where code lives, not what it must mention.
_CONTAINERS = frozenset({
    "Script", "LocalScript", "ModuleScript", "ServerScriptService", "ServerStorage", "StarterPlayerScripts",
    "StarterCharacterScripts", "StarterGui", "StarterPack", "StarterPlayer", "ReplicatedFirst", "Workspace",
    "Instance", "Roblox", "Luau", "Studio"})
MAX_REQUESTED = 8


def prose_of_request(prompt: str) -> str:
    """The request without pasted code: fenced blocks and lines that read as Luau statements."""
    text = _FENCED.sub(" ", prompt or "")
    return "\n".join(line for line in text.splitlines() if not _CODE_LINE.match(line))


def requested_names(prompt: str, lookup) -> list[dict]:
    """Engine names the request tells STAR to use: [{"name": text to find, "symbol": reference name}].

    A name counts only when (1) it stands after a directive in its own sentence ("use a UIScale",
    "give it a SmoothTime", "connected to Players.PlayerRemoving") and not after a negation
    ("do not use SetAsync"), and (2) the official reference knows it: a class, or a member of a
    class the request also names. Background such as "StreamingEnabled is on" is not a request.
    """
    prose = prose_of_request(prompt)
    if not prose.strip():
        return []
    candidates: list[tuple[str, str, int]] = []       # (shown name, symbol to verify or '', position)
    for m in _SYMBOL.finditer(prose):
        owner = _GLOBAL_CLASSES.get(m.group(1), m.group(1))
        candidates.append((m.group(3), f"{owner}{m.group(2)}{m.group(3)}", m.start(1)))
    for m in _CAMEL.finditer(prose):
        name = m.group(1)
        if sum(ch.isupper() for ch in name) >= 2 and any(ch.islower() for ch in name):
            candidates.append((name, "", m.start(1)))
    wanted: list[tuple[str, str]] = []
    made_here: set[str] = set()
    for name, symbol, position in sorted(candidates, key=lambda c: c[2]):
        before = prose[max(0, position - 90):position]
        before = re.split(r"[.;!?\n]", before)[-1]
        if name in _CONTAINERS or _NEGATION.search(before) or not _DIRECTIVE.search(before):
            continue
        if _INSTANCE_DIRECTIVE.search(before):
            made_here.add(name)
        if all(name != seen for seen, _ in wanted):
            wanted.append((name, symbol))
    if not wanted:
        return []
    wanted = wanted[:MAX_REQUESTED * 2]
    first = _lookup_all(lookup, [symbol or name for name, symbol in wanted])
    # A class that is not a service is usually an object that already exists in the place and is
    # reached by its path (`ReplicatedStorage.Remotes.Buy`), so its class name need not appear in
    # the code. It counts only when the request says to use or create one ("use a UIScale").
    wanted = [(name, symbol) for name, symbol in wanted
              if symbol or name in made_here or not (first.get(name) or {}).get("found")
              or _SERVICE_TAG.search(str((first.get(name) or {}).get("text") or ""))]
    classes = [name for name, symbol in wanted if not symbol and (first.get(name) or {}).get("found")]
    # Classes the prose names anywhere can own a bare member name ("an IKControl ... a SmoothTime").
    named = [n for n in dict.fromkeys(m.group(1) for m in _CAMEL.finditer(prose)) if n not in _CONTAINERS][:12]
    owners_known = _lookup_all(lookup, named) if named else {}
    owners = [n for n in named if (owners_known.get(n) or {}).get("found")][:6]
    result: list[dict] = []
    pending: list[tuple[str, list[str]]] = []
    for name, symbol in wanted:
        entry = first.get(symbol or name) or {}
        if entry.get("found"):
            if not entry.get("deprecated"):
                result.append({"name": name, "symbol": entry.get("symbol") or symbol or name})
        elif not symbol and name not in classes:
            pending.append((name, [f"{owner}.{name}" for owner in owners if owner != name]))
    if pending:
        second = _lookup_all(lookup, [s for _, symbols in pending for s in symbols])
        for name, symbols in pending:
            hit = next((s for s in symbols if (second.get(s) or {}).get("found")
                        and not second[s].get("deprecated")), "")
            if hit:
                result.append({"name": name, "symbol": hit})
    return result[:MAX_REQUESTED]


def missing_requested(requested: list[dict], blocks: list[str]) -> list[dict]:
    """One finding per requested name that no code block mentions (comments do not count)."""
    code = "\n".join(blank(block, strings=False) for block in blocks)
    findings = []
    for item in requested:
        if not re.search(rf"(?<![\w]){re.escape(item['name'])}(?![\w])", code):
            findings.append({"line": 0, "column": 0, "kind": REQUESTED,
                             "message": f"The request names `{item['symbol']}`, but the code never uses "
                                        f"`{item['name']}`.",
                             "hint": "If the request asks for it, use it the way the request describes; if it is "
                                     "only background, leave the code as it is."})
    return findings
