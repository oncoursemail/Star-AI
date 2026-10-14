"""A stand-in for Roblox Studio's official MCP connector.

TOOLS is the connector's real tool list as it was offered on 2026-10-11 (30 tools): the names, the
argument names, types, enums and required lists are copied from its schemas; descriptions are cut to
one line and the ~250 key names of user_keyboard_input.key_code are not repeated. On that day the
list was compared, tool by tool, with what star/studio.py read from the connector on the owner's PC:
no difference in names, arguments, types, enums or required lists. Every call is validated against
these schemas, so a call STAR builds wrongly fails here as it would in Studio.

The place behind it is a small simulation: scripts, instances, a console and a play switch. Luau is
not executed: STAR's own fixed snippets are recognised by their first line and answered the way
they would answer, and a model's edit is given its effect by `luau_effects`.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from itertools import count
from types import SimpleNamespace

from jsonschema import Draft7Validator

S, N, B, I = {"type": "string"}, {"type": "number"}, {"type": "boolean"}, {"type": "integer"}


def _enum(*values):
    return {"type": "string", "enum": list(values)}


def _list(item):
    return {"type": "array", "items": item}


def _tool(name, description, properties=None, required=()):
    properties = {**(properties or {}), "studio_id": S} if name != "list_roblox_studios" else {}
    required = sorted({*required, "studio_id"}) if name != "list_roblox_studios" else []
    return {"name": name, "description": description, "inputSchema": {
        "$schema": "http://json-schema.org/draft-07/schema#", "type": "object",
        "properties": properties, **({"required": required} if required else {})}}


_ASYNC = {"async": B}
_MATERIALS = ("Plastic SmoothPlastic Wood WoodPlanks Marble Basalt Slate CrackedLava Concrete Limestone Granite "
              "Pavement Brick Pebble Cobblestone Rock Sandstone CorrodedMetal DiamondPlate Foil Metal Grass "
              "LeafyGrass Sand Fabric Snow Mud Ground Asphalt Salt Ice Glacier Cardboard Carpet CeramicTiles "
              "ClayRoofTiles RoofShingles Leather Plaster Rubber").split()
TOOLS = [
    _tool("list_roblox_studios", "Lists the connected Roblox Studio instances so a call can be directed at one."),
    _tool("get_studio_state", "Get the state of the studio, including current play state and available datamodel types."),
    _tool("search_game_tree", "Explore the Roblox game hierarchy tree with flat JSON output.",
          {"datamodel_type": _enum("Edit", "Client", "Server"), "head_limit": N, "instance_type": S,
           "keywords": S, "max_depth": N, "path": S}, ("datamodel_type",)),
    _tool("inspect_instance", "Inspect a specific Roblox instance to get all its properties, attributes, and children summary.",
          {"path": S}, ("path",)),
    _tool("script_read", "Reads a script from the Roblox workspace, with line numbers.",
          {"end_line_one_indexed_inclusive": I, "should_read_entire_file": B, "start_line_one_indexed": I,
           "target_file": S}, ("target_file",)),
    _tool("script_search", "Fast script search based on fuzzy matching against script names.", {"keywords": S}, ("keywords",)),
    _tool("script_grep", "Runs a search for a string pattern over all script contents in the game.", {"query": S}, ("query",)),
    _tool("get_console_output", "Get the console output from the Studio output log."),
    _tool("screen_capture", "Capture current edit-time screen, return the image data.",
          {"camera_position": _list(N), "capture_id": S, "look_at_position": _list(N)}, ("capture_id",)),
    _tool("multi_edit", "Makes multiple edits to a single script in one operation. Can also create new scripts.",
          {"className": S, "datamodel_type": _enum("Edit"), "file_path": S,
           "edits": _list({"type": "object", "additionalProperties": {},
                           "properties": {"new_string": S, "old_string": S, "replace_all": B},
                           "required": ["new_string", "old_string"]})},
          ("datamodel_type", "edits", "file_path")),
    _tool("start_stop_play", "Start play the game or stop the play.", {"is_start": B}, ("is_start",)),
    _tool("execute_luau", "Executes Luau code in Roblox Studio.",
          {"code": S, "datamodel_type": _enum("Edit", "Client", "Server")}, ("code", "datamodel_type")),
    _tool("character_navigation", "Navigate the character to the given position, or instance.",
          {"datamodel_type": _enum("Client"), "instance_path": S, "speed_multiplier": N, "x": N, "y": N, "z": N},
          ("datamodel_type",)),
    _tool("user_keyboard_input", "Send one or more keyboard inputs to the game in order.",
          {"datamodel_type": _enum("Client"),
           "actions": _list({"type": "object", "additionalProperties": {}, "required": ["action"], "properties": {
               "action": _enum("keyDown", "keyUp", "keyPress", "textInput", "wait"), "instance_path": S,
               "key_code": S, "text_inputs": S, "wait_time_ms": N}})}, ("actions", "datamodel_type")),
    _tool("user_mouse_input", "Send one or more mouse actions in order.",
          {"datamodel_type": _enum("Client"),
           "actions": _list({"type": "object", "additionalProperties": {}, "required": ["action"], "properties": {
               "action": _enum("moveTo", "mouseButtonDown", "mouseButtonUp", "mouseButtonClick", "scrollUp",
                               "scrollDown", "wait"),
               "instance_path": S, "mouse_button": _enum("left", "right"), "wait_time_ms": N, "x": N, "y": N}})},
          ("actions", "datamodel_type")),
    _tool("search_asset", "Searches for assets across Creator Store and Creator Inventory.",
          {"assetType": _enum("Model", "Audio", "Mesh", "MeshPart", "Image", "Decal", "Video", "Package"),
           "audioMaxDuration": N, "audioMinDuration": N,
           "excludeSources": _list(_enum("user", "group", "universe", "creator_store")), "facets": _list(S),
           "groupId": S, "groupName": S, "includeSources": _list(_enum("user", "group", "universe", "creator_store")),
           "maxPriceCents": N, "maxResults": N, "minPriceCents": N, "priceFilter": _enum("free", "paid", "all"),
           "query": S, "scope": _enum("auto", "creator_store", "user", "group", "universe"), "tags": _list(S),
           "verifiedCreatorsOnly": B}),
    _tool("insert_asset", "Inserts an asset into the game by its numeric Roblox asset ID.",
          {"assetId": S, "assetName": S, "parentPath": S, "assetType": _enum(
              "Model", "Package", "Mesh", "MeshPart", "Image", "Decal", "Audio", "Video", "Animation")}, ("assetId",)),
    _tool("skill", "Retrieve detailed knowledge, best practices, or reference material for a specific skill.",
          {"skill_name": S}, ("skill_name",)),
    _tool("http_get", "Fetches the content of an allowed Roblox documentation URL via HTTP GET.",
          {"context_lines": N, "query": S, "return_full": B, "url": S}, ("url",)),
    _tool("wait_job_finished", "Wait for a background job to finish.", {"jobId": S, "timeout": N}, ("jobId",)),
    _tool("list_plugin_guis", "List the plugin GUIs (widgets/windows) that exist in Studio."),
    _tool("capture_plugin_gui", "Capture a screenshot of a specific open plugin GUI.", {"plugin_gui_id": S}, ("plugin_gui_id",)),
    _tool("store_image", "Load an image from a local file path and return an image URI.", {"filePath": S}, ("filePath",)),
    _tool("upload_image", "Upload a batch of images to Roblox Asset Server.", {"imagePaths": _list(S)}, ("imagePaths",)),
    _tool("subagent", "Launch a specialized subagent to handle complex, multi-step tasks autonomously.",
          {"description": S, "subagent_type": S, "task": S}, ("description", "subagent_type", "task")),
    _tool("segment_mesh", "Segments an existing mesh into named sub-parts using AI.",
          {"instance_path": S, "parts": _list(S)}, ("parts",)),
    _tool("generate_material", "Generates a MaterialVariant.",
          {**_ASYNC, "baseMaterial": _enum(*_MATERIALS), "materialDescription": S, "materialId": S,
           "materialPattern": _enum("Regular", "Organic")},
          ("baseMaterial", "materialDescription", "materialId", "materialPattern")),
    _tool("generate_mesh", "Generates a textured mesh from a prompt using AI.",
          {**_ASYNC, "maxTriangles": N, "partNames": S, "segmentation": _enum("auto", "none", "explicit"),
           "size": {"type": "object", "additionalProperties": {}, "properties": {"x": N, "y": N, "z": N},
                    "required": ["x", "y", "z"]}, "textPrompt": S}, ("textPrompt",)),
    _tool("generate_procedural_model", "Creates 3D objects built from primitive parts as a ProceduralModel.",
          {**_ASYNC, "attachedImageUri": S, "partNames": S, "prompt": S,
           "segmentation": _enum("auto", "none", "explicit")}, ("prompt",)),
    _tool("generate_texture", "Re-textures an existing mesh using AI.",
          {"hintImage": {"type": "object", "additionalProperties": {}, "properties": {}},
           "instance_path": S, "textPrompt": S}, ("textPrompt",)),
]
PIXEL = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
ARROW = chr(0x2192)
_IDS = count(1)


class Result:
    def __init__(self, content, is_error=False):
        self.content, self.isError = content, is_error

    def model_dump(self, **_):
        return {"content": self.content, "isError": self.isError}


def text(value, is_error=False) -> Result:
    return Result([{"type": "text", "text": value if isinstance(value, str) else json.dumps(value)}], is_error)


class FakeStudio:
    """One open Studio instance. Defaults to a new, unsaved Baseplate."""

    def __init__(self, *, studio_id="studio-1", name="Baseplate", place_id=0, game_id=0, creator_id=0,
                 creator_type="User", tools=None, quote_results=False):
        self.studio_id, self.name = studio_id, name
        self.identity = {"placeId": place_id, "gameId": game_id, "creatorId": creator_id,
                         "creatorType": creator_type, "name": name, "session": f"fake-game-{next(_IDS)}:workspace"}
        self.tools = list(TOOLS if tools is None else tools)
        self.quote_results = quote_results
        self.scripts: dict[str, dict] = {}                 # "ServerScriptService.Main" -> {class, source}
        self.instances: dict[str, dict] = {"Workspace.Baseplate": {"class": "Part", "tags": set()},
                                           "Workspace.SpawnLocation": {"class": "SpawnLocation", "tags": set()}}
        self.marker = False
        self.playing = False
        self.test_args = None
        self.server_unreachable_reads = 0
        self.server_unreachable_text = "Target is not reachable"
        self.console: list[str] = []
        self.calls: list[tuple[str, dict]] = []
        self.luau_effects = lambda code: []                # user code -> [(class, path), ...] it adds
        self.on_play = lambda studio: None                 # prints what the scripts would print
        self.before_native = lambda studio, code: None     # switches AFTER host reads, BEFORE native guard
        self.on_script_callback = lambda studio, path: None
        self.history, self.redo = [], []
        self.undo_fail = self.undo_no_effect = False
        self.connector_recording = False  # native Assistant execute_luau owns an outer recording
        self.recording_available = True
        self.connector_history_count = 0

    # ---- the MCP surface STAR uses
    async def list_tools(self, cursor=None):
        return SimpleNamespace(tools=[SimpleNamespace(model_dump=lambda _tool=tool, **_: dict(_tool))
                                      for tool in self.tools], nextCursor=None)

    async def call_tool(self, name, arguments=None):
        arguments = arguments or {}
        self.calls.append((name, arguments))
        schema = next((tool["inputSchema"] for tool in self.tools if tool["name"] == name), None)
        if schema is None:
            return text(f"Unknown tool: {name}", True)
        problems = sorted(error.message for error in Draft7Validator(schema).iter_errors(arguments))
        assert not problems, f"STAR called {name} with arguments the connector rejects: {problems}"
        if name != "list_roblox_studios" and arguments["studio_id"] != self.studio_id:
            return text("Studio instance not found", True)
        return getattr(self, "_" + name)(arguments)

    def names(self, kind=None):
        return [name for name, _arguments in self.calls if kind is None or name in kind]

    @staticmethod
    def _key(path: str) -> str:
        return path[5:] if path.startswith("game.") else path

    # ---- reads
    def _list_roblox_studios(self, _):
        return text({"studios": [{"id": self.studio_id, "name": self.name}]})

    def _get_studio_state(self, _):
        return text({"playState": "Playing" if self.playing else "Edit",
                     "availableDataModels": ["Client", "Server"] if self.playing else ["Edit"]})

    def _search_game_tree(self, arguments):
        if (arguments["datamodel_type"] == "Edit") == self.playing:
            return text("That datamodel is not available in the current mode", True)
        rows = [{"name": path.split(".")[-1], "className": item["class"], "fullPath": path}
                for path, item in {**self.instances, **self.scripts}.items()]
        return text(sorted(rows, key=lambda row: row["fullPath"]))

    def _inspect_instance(self, arguments):
        found = {**self.instances, **self.scripts}.get(self._key(arguments["path"]))
        return text({"className": found["class"], "path": arguments["path"]}) if found else text("Not found", True)

    def _script_read(self, arguments):
        script = self.scripts.get(self._key(arguments["target_file"]))
        if script is None:
            return text("Script not found: " + arguments["target_file"], True)
        return text("\n".join(f"{number}{ARROW}{line}" for number, line in enumerate(script["source"].split("\n"), 1)))

    def _script_search(self, arguments):
        words = [word.strip().lower() for word in arguments["keywords"].split(",")]
        return text([path for path in self.scripts if any(word in path.lower() for word in words)][:10])

    def _script_grep(self, arguments):
        return text([{"script": path, "line": number, "text": line}
                     for path, script in self.scripts.items()
                     for number, line in enumerate(script["source"].split("\n"), 1) if arguments["query"] in line][:50])

    def _get_console_output(self, _):
        return text("\n".join(self.console))

    def _screen_capture(self, arguments):
        return Result([{"type": "text", "text": arguments["capture_id"]},
                       {"type": "image", "mimeType": "image/png", "data": PIXEL}])

    def _search_asset(self, _):
        return text({"results": [], "context": {"universeId": self.identity["gameId"],
                                                "isPublished": self.identity["placeId"] != 0}})

    def _skill(self, arguments):
        return text("skill text for " + arguments["skill_name"])

    def _http_get(self, arguments):
        return text("documentation text")

    # ---- writes
    def _multi_edit(self, arguments):
        if self.playing:
            return text("Edit datamodel is not available while playing", True)
        key = self._key(arguments["file_path"])
        script = self.scripts.get(key)
        edits = arguments["edits"]
        if script is None:
            if not arguments.get("className") or not edits or edits[0]["old_string"] != "":
                return text("className and an empty first old_string are required to create a script", True)
            source, class_name, edits = edits[0]["new_string"], arguments["className"], edits[1:]
        else:
            source, class_name = script["source"], script["class"]
        for edit in edits:
            if edit["old_string"] == edit["new_string"] or edit["old_string"] not in source or not edit["old_string"]:
                return text("old_string must match the script contents exactly", True)
            source = source.replace(edit["old_string"], edit["new_string"], -1 if edit.get("replace_all") else 1)
        self.scripts[key] = {"class": class_name, "source": source}
        return text("Edited " + arguments["file_path"])

    def _start_stop_play(self, arguments):
        if arguments["is_start"] == self.playing:
            return text("Already in that state", True)
        self.playing = arguments["is_start"]
        if self.playing:
            self.on_play(self)
        return text("Play started" if self.playing else "Play stopped")

    def _reply(self, mark, value):
        encoded = mark + json.dumps(value)
        return text(json.dumps(encoded) if self.quote_results else encoded)

    def _snapshot(self):
        return deepcopy({"scripts": self.scripts, "instances": self.instances, "marker": self.marker})

    def _record(self, tag, before):
        # Roblox DataModel history intentionally excludes Source on an existing
        # LuaSourceContainer. Creation/deletion still belongs to DataModel history.
        compared = deepcopy(before)
        after = self._snapshot()
        for path in before["scripts"].keys() & after["scripts"].keys():
            if before["scripts"][path].get("_id") == after["scripts"][path].get("_id"):
                compared["scripts"][path]["source"] = after["scripts"][path]["source"]
        if compared == after:
            return
        self.history.append({"tag": tag, "before": before, "after": self._snapshot()})
        self.redo.clear()

    def _recording_tag(self, tag):
        if not self.connector_recording:
            return tag
        self.connector_history_count += 1
        return f"Assistant {self.connector_history_count}"

    def owner_edit(self, change):
        before = self._snapshot()
        change(self)
        self._record(f"OwnerEdit_{next(_IDS)}", before)

    def _undo(self, tag):
        if self.undo_fail or not self.history or self.history[-1]["tag"] != tag:
            return False
        record = self.history[-1]
        changes = []
        for category in ("scripts", "instances"):
            before, after, current = record["before"][category], record["after"][category], getattr(self, category)
            for path in before.keys() | after.keys():
                old, new, now = deepcopy(before.get(path)), deepcopy(after.get(path)), deepcopy(current.get(path))
                if category == "scripts" and old and new and old.get("_id") == new.get("_id"):
                    old["source"] = new["source"] = now.get("source") if now else None
                if old != new:
                    if now != new:
                        return False
                    changes.append((current, path, old))
        if record["before"]["marker"] != record["after"]["marker"] and self.marker != record["after"]["marker"]:
            return False
        if self.undo_no_effect:
            return False
        for current, path, value in changes:
            if value is None:
                current.pop(path, None)
            else:
                current[path] = value
        if record["before"]["marker"] != record["after"]["marker"]:
            self.marker = record["before"]["marker"]
        self.redo.append(self.history.pop())
        return True

    @staticmethod
    def _payload(code):
        quoted = re.search(r'JSONDecode\(("(?:\\.|[^"\\])*")\)', code).group(1)
        return json.loads(json.loads(quoted))

    def _script_cas(self, code, pin):
        if not self.connector_recording and not self.recording_available:
            return text("STAR could not begin an undo recording", True)
        request = self._payload(code)
        path = request["path"]
        script = self.scripts.get(path)
        created = script is None
        if created != (request["before"] is None) or (not created and script["source"] != request["before"]):
            return text("STAR script conflict; owner changes preserved", True)
        if not created:
            script.setdefault("_id", f"script-{next(_IDS)}")
        before = self._snapshot()
        if created:
            script = {"class": request["className"], "source": "", "_id": f"script-{next(_IDS)}"}
            self.scripts[path] = script
        self.on_script_callback(self, path)
        ok = self._matches(pin) and self.scripts.get(path) is script \
            and script["source"] == ("" if created else request["before"])
        if ok:
            script["source"] = request["after"]
            self.marker = True
        self._record(self._recording_tag(request["tag"]), before)
        return self._reply("STAR_EDIT ", {"tag": request["tag"], "ok": ok, "created": created,
                                         "recorded": not self.connector_recording, "connectorRecorded": self.connector_recording,
                                         "instanceId": script["_id"],
                                         "undoCan": bool(self.history), "undoName": self.history[-1]["tag"] if self.history else None})

    def _matches(self, pin):
        return all(self.identity.get(key) == value for key, value in pin.items())

    def _execute_luau(self, arguments):
        code = arguments["code"]
        if (arguments["datamodel_type"] == "Edit") == self.playing:
            return text("That datamodel is not available in the current mode", True)
        if code.startswith(("-- STAR:play-stop-probe ", "-- STAR:play-stop-bound ")):
            stop = code.startswith("-- STAR:play-stop-bound ")
            expected = json.loads(code.split("\n", 1)[0].split(" ", 2)[2])
            if arguments["datamodel_type"] != "Server":
                return text("STAR stop requires the Server context", True)
            if not stop and self.server_unreachable_reads:
                self.server_unreachable_reads -= 1
                return text(self.server_unreachable_text, True)
            self.before_native(self, code)
            if any(self.identity.get(key) != expected[key] for key in ("placeId", "gameId", "creatorId", "creatorType")):
                return text("STAR stop target changed; no stop accepted", True)
            if not isinstance(self.test_args, dict) or self.test_args.get("starSession") != expected["session"] or self.test_args.get("starRequest") != expected["request"]:
                return text("STAR stop request changed; no stop accepted", True)
            if stop:
                self.playing = False
                return self._reply("STAR_STOP ", {"request": expected["request"], "session": expected["session"], "requested": True})
            return self._reply("STAR_PLAY_OWNER ", {"request": expected["request"], "session": expected["session"], "matched": True})
        if code.startswith("-- STAR:identity"):
            return self._reply("STAR_PLACE ", {**self.identity, "scripts": len(self.scripts), "marker": self.marker})
        if code.startswith("-- STAR:mark"):
            self.marker = True
            return text("marked")
        pin = None
        if code.startswith("-- STAR:bound "):
            pin = json.loads(code.split("\n", 1)[0].removeprefix("-- STAR:bound "))
            self.before_native(self, code)
            if not self._matches(pin):
                return text("STAR target changed; no mutation accepted", True)
            code = code[code.index("end\n__star_check()\n") + len("end\n__star_check()\n"):]
        if code.startswith("-- STAR:script-cas"):
            return self._script_cas(code, pin)
        if code.startswith("-- STAR:script-undo-cas"):
            request = self._payload(code)
            script = self.scripts.get(request["path"])
            if not script or script.get("_id") != request["instanceId"] or script["source"] != request["after"]:
                return text("STAR undo conflict; owner changes preserved", True)
            if request["created"]:
                if not self._undo(request["tag"]):
                    return text("STAR undo conflict or restoration not confirmed", True)
            else:
                if not request["connectorRecorded"] and (bool(self.history) != request["undoCan"]
                    or (self.history[-1]["tag"] if self.history else None) != request["undoName"]):
                    return text("STAR undo conflict; newer DataModel history must be reviewed first", True)
                self.on_script_callback(self, request["path"])
                if not self._matches(pin) or self.scripts.get(request["path"]) is not script or script["source"] != request["after"]:
                    return text("STAR undo conflict; owner changes preserved", True)
                script["source"] = request["before"]
            restored = self.scripts.get(request["path"])
            confirmed = restored is None if request["created"] else bool(
                restored and restored.get("_id") == request["instanceId"] and restored["source"] == request["before"])
            return self._reply("STAR_EDIT ", {"undone": request["tag"], "ok": confirmed})
        if code.startswith("-- STAR:recording-undo "):
            tag = code.split("\n", 1)[0].split()[-1]
            if not self._undo(tag):
                return text("STAR undo conflict or restoration not confirmed", True)
            if not self.redo or self.redo[-1]["tag"] != tag:
                return text("STAR recording undo not confirmed", True)
            return self._reply("STAR_EDIT ", {"undone": tag, "ok": True})
        if code.startswith("-- STAR:play-bound"):
            tag = re.search(r'starRequest = "(StarEdit_[0-9a-f]{8})"', code).group(1)
            if self.playing:
                return self._reply("STAR_PLAY ", {"request": tag, "requested": False, "status": "failed"})
            self.playing = True
            self.test_args = {"starSession": pin["session"], "starRequest": tag}
            self.on_play(self)
            return self._reply("STAR_PLAY ", {"request": tag, "requested": True, "status": "starting"})
        if code.startswith("-- STAR:undo "):
            tag = code.split("\n", 1)[0].split()[-1]
            doomed = [path for path, item in self.instances.items() if tag in item["tags"]]
            for path in doomed:
                del self.instances[path]
            return self._reply("STAR_EDIT ", {"undone": tag, "removed": len(doomed)})
        if code.startswith("-- STAR:remove-script"):
            path = re.search(r'string\.gmatch\("([^"]+)"', code).group(1)
            return self._reply("STAR_EDIT ", {"undone": "script", "removed": int(self.scripts.pop(path, None) is not None)})
        wrapped = re.search(r'AddTag\(item, "(StarEdit_[0-9a-f]{8})"\)', code)
        if wrapped and code.startswith("local __s = {added"):
            if not self.connector_recording and not self.recording_available:
                return text("STAR could not begin an undo recording", True)
            before = self._snapshot()
            user = code.split("pcall(function() ", 1)[1].rsplit("\nend)\ntask.wait()", 1)[0]
            failed = "error(" in user
            added = [] if failed else list(self.luau_effects(user))
            for class_name, path in added:
                self.instances[path] = {"class": class_name, "tags": {wrapped.group(1)}}
            self.marker = True
            self._record(self._recording_tag(wrapped.group(1)), before)
            return self._reply("STAR_EDIT ", {"tag": wrapped.group(1), "ok": not failed,
                                              "recorded": not self.connector_recording, "connectorRecorded": self.connector_recording,
                                              "added": [f"{c} {p}" for c, p in added], "addedCount": len(added),
                                              "removed": 0})
        return text("nil")

    def _character_navigation(self, _):
        return text("moved") if self.playing else text("Client datamodel is not available", True)

    _user_keyboard_input = _user_mouse_input = _character_navigation

    def __getattr__(self, name):
        # The tools STAR must never call (generation, uploads, asset insert, sub-agents ...).
        if name.startswith("_") and name[1:] in {tool["name"] for tool in TOOLS}:
            raise AssertionError(f"STAR called {name[1:]}, which it must never use")
        raise AttributeError(name)
