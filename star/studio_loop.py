"""The Studio build loop on the official Studio MCP connector, with the sandbox rule enforced in code.

    connect -> which place is this? -> read tree and scripts -> screenshot -> edit scripts and
    instances -> playtest -> read output -> screenshot -> fix -> report what changed, with undo

Nothing here invents a connector method: the tool list is read from the connector at runtime
(star/studio.py) and sorted by star/policy.py. Three things are STAR's own, as fixed text that a
model cannot change: the question "which place is open" (IDENTITY_PROBE), the wrapper around a
sandbox Luau edit (wrap_edit) and the removal of what an edit added (UNDO_SNIPPET).

The sandbox rule. STAR edits a place only when the owner switched Studio edits on AND the place is
  * a blank, unsaved place (never published: PlaceId 0; no scripts, or marked by an earlier STAR edit), or
  * a place owned by STAR's own Roblox account, and the owner also allowed those.
Every other place, and always the places on the deny-list, is read-only whatever the settings say.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
import secrets

from .policy import BLOCKED_TOOLS, READ_TOOLS, WRITE_TOOLS, classify
from .roblox_cloud import DENIED_PLACE_IDS, DENIED_UNIVERSE_IDS

PLACE_MARK, EDIT_MARK = "STAR_PLACE ", "STAR_EDIT "
SANDBOX_ATTRIBUTE = "StarSandbox"
_SERVICES = ('"Workspace", "ReplicatedFirst", "ReplicatedStorage", "ServerScriptService", "ServerStorage", '
             '"StarterGui", "StarterPack", "StarterPlayer", "Lighting"')

# Reads only. API names checked against the official reference (DataModel.PlaceId, GameId,
# CreatorId, CreatorType; Instance:GetAttribute; HttpService:JSONEncode).
IDENTITY_PROBE = f"""-- STAR:identity (reads only)
local HttpService = game:GetService("HttpService")
local scripts = 0
for _, name in ipairs({{ {_SERVICES} }}) do
	local ok, service = pcall(function()
		return game:GetService(name)
	end)
	if ok and service then
		for _, item in ipairs(service:GetDescendants()) do
			if item:IsA("LuaSourceContainer") then
				scripts += 1
			end
		end
	end
end
return "{PLACE_MARK}" .. HttpService:JSONEncode({{
	placeId = game.PlaceId,
	gameId = game.GameId,
	creatorId = game.CreatorId,
	creatorType = game.CreatorType.Name,
	name = game.Name,
	scripts = scripts,
	marker = workspace:GetAttribute("{SANDBOX_ATTRIBUTE}") == true,
}})
"""

# Marks an unsaved place as STAR's sandbox, so a later session may continue in it.
MARK_SNIPPET = f'-- STAR:mark\nworkspace:SetAttribute("{SANDBOX_ATTRIBUTE}", true)\nreturn "marked"\n'

# Removes what one edit added (found by its tag) and nothing else.
UNDO_SNIPPET = """-- STAR:undo %(tag)s
local CollectionService = game:GetService("CollectionService")
local ChangeHistoryService = game:GetService("ChangeHistoryService")
local recording = ChangeHistoryService:TryBeginRecording("STAR undo")
local removed = 0
for _, item in ipairs(CollectionService:GetTagged("%(tag)s")) do
	removed += 1
	item:Destroy()
end
if recording then
	ChangeHistoryService:FinishRecording(recording, Enum.FinishRecordingOperation.Commit)
end
return "STAR_EDIT " .. game:GetService("HttpService"):JSONEncode({ undone = "%(tag)s", removed = removed })
"""

# Removes a script that an edit created. The path is checked by _SCRIPT_PATH before it gets here.
REMOVE_SCRIPT_SNIPPET = """-- STAR:remove-script
local current = game
for name in string.gmatch("%(path)s", "[^.]+") do
	current = current and current:FindFirstChild(name)
end
local removed = 0
if current and current ~= game and current:IsA("LuaSourceContainer") then
	current:Destroy()
	removed = 1
end
return "STAR_EDIT " .. game:GetService("HttpService"):JSONEncode({ undone = "script", removed = removed })
"""
_SCRIPT_PATH = re.compile(r"(?:game\.)?[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_][A-Za-z0-9_ \-]{0,79})+")
_TAG = re.compile(r"StarEdit_[0-9a-f]{8}")


def wrap_edit(code: str, tag: str | None = None) -> tuple[str, str]:
    """A model's sandbox Luau, made one undo step in Studio and tagged so STAR can list and remove
    what it added. The model's first line stays on line 1, so error line numbers still fit."""
    tag = tag or "StarEdit_" + secrets.token_hex(4)
    if not _TAG.fullmatch(tag):
        raise ValueError("Invalid edit tag")
    head = ('local __s = {added = {}, removed = 0, c = game:GetService("ChangeHistoryService")}; '
            '__s.rec = __s.c:TryBeginRecording("STAR edit"); '
            '__s.a = game.DescendantAdded:Connect(function(i) table.insert(__s.added, i) end); '
            '__s.r = game.DescendantRemoving:Connect(function() __s.removed += 1 end); '
            'local __ok, __res = pcall(function() ')
    tail = f"""
end)
task.wait()
__s.a:Disconnect()
__s.r:Disconnect()
local __paths, __count = {{}}, 0
local __tags = game:GetService("CollectionService")
for _, item in ipairs(__s.added) do
	local alive, path = pcall(function()
		return item:GetFullName()
	end)
	if alive and item:IsDescendantOf(game) then
		__count += 1
		local parent = item.Parent
		if not (parent and table.find(__s.added, parent)) then
			pcall(function()
				__tags:AddTag(item, "{tag}")
			end)
			if #__paths < 60 then
				table.insert(__paths, item.ClassName .. " " .. path)
			end
		end
	end
end
pcall(function()
	workspace:SetAttribute("{SANDBOX_ATTRIBUTE}", true)
end)
if __s.rec then
	__s.c:FinishRecording(__s.rec, Enum.FinishRecordingOperation.Commit)
end
return "{EDIT_MARK}" .. game:GetService("HttpService"):JSONEncode({{
	tag = "{tag}", ok = __ok, recorded = __s.rec ~= nil, added = __paths, addedCount = __count,
	removed = __s.removed, result = if __res == nil then nil else string.sub(tostring(__res), 1, 2000),
}})
"""
    return head + code + tail, tag


# --------------------------------------------------------------------------- which place is open

@dataclass(frozen=True)
class PlaceIdentity:
    place_id: int
    game_id: int
    creator_id: int
    creator_type: str
    name: str
    scripts: int
    marker: bool


@dataclass(frozen=True)
class Verdict:
    editable: bool
    kind: str          # blank | own | denied | published | not_blank | unknown
    reason: str
    identity: PlaceIdentity | None = None

    def public(self) -> dict:
        shown = {"editable": self.editable, "kind": self.kind, "reason": self.reason}
        if self.identity:
            shown["place"] = {"place_id": self.identity.place_id, "name": self.identity.name[:80],
                              "scripts": self.identity.scripts}
        return shown


def result_text(result) -> str:
    """All text of an MCP tool result, whether it is an SDK object or a plain dict."""
    data = result.model_dump(by_alias=True, exclude_none=True) if hasattr(result, "model_dump") else result
    parts = data.get("content") if isinstance(data, dict) else None
    return "\n".join(str(part.get("text", "")) for part in parts or () if isinstance(part, dict)
                     and part.get("type") == "text")


def result_failed(result) -> bool:
    data = result.model_dump(by_alias=True, exclude_none=True) if hasattr(result, "model_dump") else result
    return bool(isinstance(data, dict) and data.get("isError"))


def _marked_json(text: str, mark: str) -> dict | None:
    """The JSON object STAR's own snippet printed after `mark`, however the connector quoted it."""
    position = text.find(mark)
    if position < 0:
        return None
    rest = text[position + len(mark):]
    for candidate in (rest, rest.replace(chr(92) + '"', '"').replace(chr(92) * 2, chr(92))):
        try:
            value, _end = json.JSONDecoder().raw_decode(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def studios(result) -> list[dict]:
    """[{id, name}] from list_roblox_studios."""
    try:
        data = json.loads(result_text(result))
    except ValueError:
        return []
    items = data.get("studios") if isinstance(data, dict) else None
    return [{"id": str(item.get("id", "")), "name": str(item.get("name", ""))[:200]}
            for item in items or () if isinstance(item, dict) and item.get("id")]


def name_is_denied(name: str) -> bool:
    """A deny-listed place or experience id in the instance's display name: no question is asked of that place."""
    denied = DENIED_PLACE_IDS | DENIED_UNIVERSE_IDS
    return any(int(number) in denied for number in re.findall(r"\d{6,19}", str(name)))


async def identify(session, studio_id: str, *, tools: set[str], studio_name: str = "") -> PlaceIdentity | None:
    """Ask the open place what it is. None when that cannot be found out (then nothing is edited)."""
    if name_is_denied(studio_name) or "execute_luau" not in tools:
        return None
    result = await session.call_tool("execute_luau", arguments={
        "studio_id": studio_id, "datamodel_type": "Edit", "code": IDENTITY_PROBE})
    found = None if result_failed(result) else _marked_json(result_text(result), PLACE_MARK)
    if not found:
        return None
    try:
        return PlaceIdentity(int(found["placeId"]), int(found["gameId"]), int(found["creatorId"]),
                             str(found.get("creatorType", "")), str(found.get("name", ""))[:120],
                             int(found["scripts"]), found.get("marker") is True)
    except (KeyError, TypeError, ValueError):
        return None


def judge(identity: PlaceIdentity | None, *, opted_in: bool, own_places: bool = False,
          own_account_id: int | None = None, studio_name: str = "") -> Verdict:
    """The sandbox rule. Pure: the same facts always give the same answer."""
    if name_is_denied(studio_name) or (identity and (identity.place_id in DENIED_PLACE_IDS
                                                     or identity.game_id in DENIED_UNIVERSE_IDS)):
        return Verdict(False, "denied", "This place is on STAR's deny-list. STAR never edits it. Open a new "
                                         "Baseplate for STAR to build in.", identity)
    if identity is None:
        return Verdict(False, "unknown", "STAR could not find out which place is open, so it only reads.")
    if identity.place_id == 0 and identity.game_id == 0:
        if identity.scripts and not identity.marker:
            return Verdict(False, "not_blank", "This unsaved place already has scripts that STAR did not "
                           "make. Open a new Baseplate for STAR to build in.", identity)
        if not opted_in:
            return Verdict(False, "blank", "A blank place is open. Switch on Studio edits to let STAR build in it.",
                           identity)
        return Verdict(True, "blank", "A blank, unpublished place: STAR may build here.", identity)
    if (identity.creator_type == "User" and own_account_id and identity.creator_id == own_account_id):
        if opted_in and own_places:
            return Verdict(True, "own", "A place of STAR's own Roblox account: STAR may build here.", identity)
        return Verdict(False, "own", "This place belongs to STAR's own Roblox account. Allow 'places of "
                       "STAR's own account' in Settings to let STAR edit it.", identity)
    return Verdict(False, "published", "This is a published place that does not belong to STAR's own "
                   "account. STAR only reads it. Open a new Baseplate for STAR to build in.", identity)


# --------------------------------------------------------------------------- journal and undo

@dataclass
class ChangeJournal:
    """What STAR changed in this session, in order, with what is needed to take it back."""
    entries: list[dict] = field(default_factory=list)

    def report(self) -> dict:
        changes = []
        for entry in self.entries:
            if entry["kind"] == "script":
                changes.append({"what": ("created script " if entry["created"] else "edited script ") + entry["path"],
                                "undo": "STAR restores it" if entry["restorable"] else "Ctrl+Z in Studio"})
            elif entry["kind"] == "luau":
                added = entry.get("added_count", 0)
                changes.append({"what": f"ran an edit: {added} instance(s) added, {entry.get('removed', 0)} removed"
                                        + ("" if entry.get("ok", True) else " (the edit stopped with an error)"),
                                "added": entry.get("added", [])[:20],
                                "undo": "STAR removes what was added; Ctrl+Z in Studio also takes back "
                                        "property changes and deletions" if entry.get("known") else "Ctrl+Z in Studio"})
            elif entry["kind"] == "playtest":
                changes.append({"what": "started a playtest" if entry["start"] else "stopped the playtest", "undo": "nothing to undo"})
        steps = sum(1 for entry in self.entries if entry["kind"] in ("script", "luau"))
        return {"changes": changes, "edits": steps,
                "undo": {"available": steps > 0,
                         # Only what exists: the journal lives for this session, so a later turn
                         # cannot take these edits back by itself; Studio's own undo can.
                         "how": "Press Ctrl+Z in Studio to step back through these edits (a Luau edit is "
                                "one undo step)." if steps else ""}}

    def text(self) -> str:
        report = self.report()
        if not report["edits"]:
            return ""
        lines = [f"Studio changes in this turn ({report['edits']}):"]
        for change in report["changes"]:
            if change["undo"] != "nothing to undo":
                lines.append(f"- {change['what']}" + ("".join(f"\n    {item}" for item in change.get("added", [])[:8])))
        lines.append("Undo: " + report["undo"]["how"])
        return "\n".join(lines)


def _plain_source(text: str) -> str:
    """script_read numbers its lines (number, U+2192 arrow, code); give back the code."""
    return "\n".join(re.sub(r"^\s*\d+\u2192", "", line) for line in text.split("\n"))


class _Refused:
    def __init__(self, text: str):
        self._data = {"isError": True, "content": [{"type": "text", "text": text}]}

    def model_dump(self, **_):
        return self._data


class GuardedStudio:
    """What the agent loop talks to instead of the raw connector session.

    Reads STAR knows pass through. An edit is refused unless the verdict allows it and it targets
    the instance that was judged; allowed edits are written to the journal, and a sandbox Luau edit
    is wrapped so it is one undo step and its additions are known. A tool this class has no rule
    for (one a later connector adds, whatever it is called) is refused, never passed on.
    """

    def __init__(self, session, *, studio_id: str, verdict: Verdict, tools: set[str],
                 journal: ChangeJournal | None = None):
        self.session, self.studio_id, self.verdict, self.tools = session, studio_id, verdict, set(tools)
        self.journal = journal if journal is not None else ChangeJournal()
        self._marked = bool(verdict.identity and verdict.identity.marker)

    async def call_tool(self, name: str, arguments: dict | None = None):
        arguments = dict(arguments or {})
        if name in BLOCKED_TOOLS:
            return _Refused("STAR does not use this Studio tool")
        if name in READ_TOOLS:
            return await self.session.call_tool(name, arguments=arguments)
        if name not in WRITE_TOOLS:
            return _Refused("STAR does not know this Studio tool, so it does not use it")
        if not self.verdict.editable:
            return _Refused("Edit refused: " + self.verdict.reason)
        if arguments.get("studio_id") != self.studio_id:
            return _Refused("Edit refused: that is not the Studio instance STAR checked")
        if name == "multi_edit":
            return await self._edit_script(arguments)
        if name == "execute_luau":
            if arguments.get("datamodel_type") != "Edit":
                return _Refused("Edit refused: Luau runs in the Edit DataModel only")
            wrapped, tag = wrap_edit(str(arguments.get("code", "")))
            result = await self.session.call_tool(name, arguments={**arguments, "code": wrapped})
            seen = _marked_json(result_text(result), EDIT_MARK)
            self._marked = self._marked or bool(seen)
            self.journal.entries.append({
                "kind": "luau", "tag": tag, "known": bool(seen), "ok": bool(seen.get("ok")) if seen else not result_failed(result),
                "added": [str(item)[:160] for item in (seen or {}).get("added", [])][:60],
                "added_count": int((seen or {}).get("addedCount", 0) or 0), "removed": int((seen or {}).get("removed", 0) or 0)})
            return result
        result = await self.session.call_tool(name, arguments=arguments)
        if name == "start_stop_play" and not result_failed(result):
            self.journal.entries.append({"kind": "playtest", "start": arguments.get("is_start") is True})
        return result

    async def _read(self, path: str) -> str | None:
        if "script_read" not in self.tools:
            return None
        result = await self.session.call_tool("script_read", arguments={"studio_id": self.studio_id, "target_file": path})
        return None if result_failed(result) else _plain_source(result_text(result))

    async def _edit_script(self, arguments: dict):
        path = str(arguments.get("file_path", ""))
        edits = arguments.get("edits") or []
        before = await self._read(path)
        result = await self.session.call_tool("multi_edit", arguments=arguments)
        if result_failed(result):
            return result
        created = (before is None and bool(arguments.get("className")) and bool(edits)
                   and isinstance(edits[0], dict) and edits[0].get("old_string") == "")
        self.journal.entries.append({"kind": "script", "path": path, "created": created, "before": before,
                                     "restorable": created or before is not None})
        if not self._marked and "execute_luau" in self.tools:
            # STAR's own fixed line: remember that this unsaved place is its sandbox.
            await self.session.call_tool("execute_luau", arguments={
                "studio_id": self.studio_id, "datamodel_type": "Edit", "code": MARK_SNIPPET})
            self._marked = True
        return result

    async def undo(self) -> dict:
        """Take back this session's edits, newest first, as far as STAR can do it exactly."""
        done, left = [], []
        if not self.verdict.editable:
            return {"undone": done, "left": ["Undo refused: " + self.verdict.reason]}
        for entry in reversed(self.journal.entries):
            if entry["kind"] == "luau" and entry.get("known") and "execute_luau" in self.tools:
                result = await self.session.call_tool("execute_luau", arguments={
                    "studio_id": self.studio_id, "datamodel_type": "Edit", "code": UNDO_SNIPPET % {"tag": entry["tag"]}})
                seen = _marked_json(result_text(result), EDIT_MARK) or {}
                done.append(f"removed {seen.get('removed', 0)} added instance(s)")
            elif entry["kind"] == "script" and entry["created"] and "execute_luau" in self.tools \
                    and _SCRIPT_PATH.fullmatch(entry["path"]):
                path = entry["path"][5:] if entry["path"].startswith("game.") else entry["path"]
                await self.session.call_tool("execute_luau", arguments={
                    "studio_id": self.studio_id, "datamodel_type": "Edit",
                    "code": REMOVE_SCRIPT_SNIPPET % {"path": path}})
                done.append("removed script " + entry["path"])
            elif entry["kind"] == "script" and entry["before"] is not None:
                current = await self._read(entry["path"])
                if current is None:
                    left.append("could not read " + entry["path"])
                elif current != entry["before"]:
                    result = await self.session.call_tool("multi_edit", arguments={
                        "studio_id": self.studio_id, "datamodel_type": "Edit", "file_path": entry["path"],
                        "edits": [{"old_string": current, "new_string": entry["before"]}]})
                    (left if result_failed(result) else done).append("restored script " + entry["path"])
            elif entry["kind"] in ("luau", "script"):
                left.append("use Ctrl+Z in Studio for: " + (entry.get("path") or "a Luau edit"))
        self.journal.entries = [entry for entry in self.journal.entries if entry["kind"] == "playtest"]
        return {"undone": done, "left": left}


async def open_guarded(session, discovered: list[dict], *, studio_id: str, opted_in: bool,
                       own_places: bool = False, own_account_id: int | None = None) -> GuardedStudio:
    """Connect step of the loop: find the instance, ask what it is, apply the sandbox rule."""
    tools = {tool.get("name", "") for tool in discovered}
    name = ""
    if "list_roblox_studios" in tools:
        listed = studios(await session.call_tool("list_roblox_studios", arguments={}))
        name = next((item["name"] for item in listed if item["id"] == studio_id), "")
        if listed and not any(item["id"] == studio_id for item in listed):
            return GuardedStudio(session, studio_id=studio_id, tools=tools, verdict=Verdict(
                False, "unknown", "The chosen Studio instance is not open any more."))
    identity = await identify(session, studio_id, tools=tools, studio_name=name)
    verdict = judge(identity, opted_in=opted_in, own_places=own_places, own_account_id=own_account_id,
                    studio_name=name)
    return GuardedStudio(session, studio_id=studio_id, verdict=verdict, tools=tools)


def own_account_id(home) -> int | None:
    """STAR's own Roblox account: the account of the connected API key, as its last test showed it."""
    from .roblox_cloud import RobloxCloud
    try:
        last = RobloxCloud(home=home).status().get("last_check") or {}
    except Exception:
        return None
    account = (last.get("account") or {}).get("user_id") if last.get("state") in ("valid", "missing_permission") else None
    return account if type(account) is int and account > 0 else None


def with_report(outcome, studio: GuardedStudio):
    """Append what was changed in Studio, and how to undo it, to the answer of a turn. Written by
    code from the journal, so it is there whether or not the model mentions its edits."""
    text = studio.journal.text()
    if not text or not isinstance(outcome, tuple) or not outcome or not isinstance(outcome[0], str):
        return outcome
    return (outcome[0].rstrip() + "\n\n" + text, *outcome[1:])


# --------------------------------------------------------------------------- the loop, step by step

ERROR_LINE = re.compile(r"(?i)\b(error|exception|attempt to|is not a valid member|stack begin|infinite yield)\b")


def console_errors(text: str) -> list[str]:
    return [line.strip()[:400] for line in text.splitlines() if ERROR_LINE.search(line)][:40]


async def run_build_loop(studio: GuardedStudio, *, scripts: list[dict], luau_edits: list[str] = (),
                         fix=None, settle=None, undo_at_end: bool = False) -> dict:
    """One full pass of the loop without a model, for the fake connector and for the live check.

    `scripts`: [{path, class_name, source}] to create or replace. `luau_edits`: sandbox Luau that
    builds instances. `fix(errors)` returns the same kind of script list to repair what the
    playtest printed. `settle()` is awaited while the playtest runs.
    """
    session, sid, tools = studio.session, studio.studio_id, studio.tools
    steps: list[dict] = []
    report = {"verdict": studio.verdict.public(), "tools": classify([{"name": name} for name in tools]),
              "steps": steps, "ok": False}

    async def read(name, **arguments):
        result = await session.call_tool(name, arguments={"studio_id": sid, **arguments})
        return result, result_text(result)

    async def shot(label):
        if "screen_capture" not in tools:
            return steps.append({"step": "screenshot " + label, "ok": False, "detail": "the connector has no screen_capture"})
        result = await session.call_tool("screen_capture", arguments={"studio_id": sid, "capture_id": label})
        data = result.model_dump(by_alias=True, exclude_none=True) if hasattr(result, "model_dump") else result
        images = [part for part in data.get("content", []) if isinstance(part, dict) and part.get("type") == "image"]
        steps.append({"step": "screenshot " + label, "ok": bool(images) and not result_failed(result),
                      "bytes": sum(len(str(part.get("data", ""))) for part in images)})

    async def write(items):
        for item in items:
            existing = await studio._read(item["path"])
            edit = ({"old_string": existing, "new_string": item["source"]} if existing is not None
                    else {"old_string": "", "new_string": item["source"]})
            if existing == item["source"]:
                continue
            result = await studio.call_tool("multi_edit", {
                "studio_id": sid, "datamodel_type": "Edit", "file_path": item["path"], "edits": [edit],
                **({} if existing is not None else {"className": item.get("class_name", "Script")})})
            steps.append({"step": "write " + item["path"], "ok": not result_failed(result),
                          "detail": result_text(result)[:200] if result_failed(result) else ""})

    async def playtest(label):
        started = await studio.call_tool("start_stop_play", {"studio_id": sid, "is_start": True})
        if result_failed(started):
            steps.append({"step": "playtest " + label, "ok": False, "detail": result_text(started)[:200]})
            return None
        if settle is not None:
            await settle()
        _result, output = await read("get_console_output")
        await studio.call_tool("start_stop_play", {"studio_id": sid, "is_start": False})
        errors = console_errors(output)
        steps.append({"step": "playtest " + label, "ok": True, "errors": errors, "output_chars": len(output)})
        return errors

    _result, state = await read("get_studio_state")
    steps.append({"step": "connect", "ok": True, "state": state[:300]})
    _result, tree = await read("search_game_tree", datamodel_type="Edit", max_depth=2)
    steps.append({"step": "read tree", "ok": bool(tree), "chars": len(tree)})
    _result, found = await read("script_grep", query="function")
    steps.append({"step": "read scripts", "ok": True, "chars": len(found)})
    await shot("before")
    if not studio.verdict.editable:
        report["stopped"] = "read only: " + studio.verdict.reason
        return report
    await write(scripts)
    for code in luau_edits:
        result = await studio.call_tool("execute_luau", {"studio_id": sid, "datamodel_type": "Edit", "code": code})
        steps.append({"step": "build instances", "ok": not result_failed(result)
                      and bool(studio.journal.entries and studio.journal.entries[-1].get("ok"))})
    errors = await playtest("first")
    await shot("after first playtest")
    if errors and fix is not None:
        await write(fix(errors))
        errors = await playtest("after the fix")
        await shot("after the fix")
    report["changes"] = studio.journal.report()
    report["ok"] = errors == [] and all(step["ok"] for step in steps if step["step"].startswith(("write", "build")))
    if undo_at_end:
        report["undo"] = await studio.undo()
    return report
