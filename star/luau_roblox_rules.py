"""Opt-in Roblox-specific Luau diagnostics: deprecated engine APIs and common client/server bugs.

Token heuristics built on the lexer of ``star.luau_lint`` (comments and string contents are skipped), not a
parser or a data-flow analysis. Every rule is written to stay quiet when it cannot tell; tests pin both the
bugs it reports and the idiomatic code it must leave alone. No file, network, Studio or code execution.

Enable with ``lint(code, roblox_rules=True)``; the default ``lint`` output is unchanged.

Deprecation tables: every service method, class and Instance method listed below is tagged ``Deprecated`` in the
Roblox Studio Full API dump for Studio 0.742 (``version-9b554450a0fc4e65``); the replacement is the dump's
``PreferredDescriptorName`` where it gives one, otherwise the API the official documentation names. The deprecated
globals are the ones tagged Deprecated in the Creator Documentation's Roblox and Lua globals and table library
references (``wait``, ``spawn`` and ``delay`` stay with the older ``deprecated-task-global`` rule).
"""
from __future__ import annotations

import re

from .luau_lint import Finding, _tokens

RULE_IDS = (
    "deprecated-api",
    "pcall-called-result",
    "server-invoke-client",
    "fireserver-player-argument",
    "client-leaderstats-write",
    "playeradded-existing-players",
    "characteradded-existing-character",
    "per-player-connection-leak",
    "remote-every-frame",
)

# (service, method) -> replacement.
DEPRECATED_SERVICE_METHODS: dict[tuple[str, str], str] = {
    ("Workspace", "FindPartOnRay"): "workspace:Raycast(origin, direction, raycastParams)",
    ("Workspace", "FindPartOnRayWithIgnoreList"): "workspace:Raycast with RaycastParams.FilterType Exclude",
    ("Workspace", "FindPartOnRayWithWhitelist"): "workspace:Raycast with RaycastParams.FilterType Include",
    ("Workspace", "findPartOnRay"): "workspace:Raycast(origin, direction, raycastParams)",
    ("Workspace", "FindPartsInRegion3"): "workspace:GetPartBoundsInBox(cframe, size, overlapParams)",
    ("Workspace", "FindPartsInRegion3WithIgnoreList"): "workspace:GetPartBoundsInBox with OverlapParams",
    ("Workspace", "FindPartsInRegion3WithWhiteList"): "workspace:GetPartBoundsInBox with OverlapParams",
    ("Workspace", "findPartsInRegion3"): "workspace:GetPartBoundsInBox(cframe, size, overlapParams)",
    ("Workspace", "IsRegion3Empty"): "#workspace:GetPartBoundsInBox(...) == 0",
    ("Workspace", "IsRegion3EmptyWithIgnoreList"): "#workspace:GetPartBoundsInBox(...) == 0 with OverlapParams",
    ("Workspace", "BreakJoints"): "destroy the joints or WeldConstraints you created",
    ("Workspace", "MakeJoints"): "WeldConstraint instances",
    ("TeleportService", "TeleportToPlaceInstance"): "TeleportService:TeleportAsync with TeleportOptions.ServerInstanceId",
    ("TeleportService", "TeleportToPrivateServer"): "TeleportService:TeleportAsync with TeleportOptions.ReservedServerAccessCode",
    ("TeleportService", "TeleportToSpawnByName"): "TeleportService:TeleportAsync",
    ("TeleportService", "TeleportPartyAsync"): "TeleportService:TeleportAsync(placeId, players, options)",
    ("TeleportService", "ReserveServer"): "TeleportService:ReserveServerAsync or TeleportOptions.ShouldReserveServer",
    ("MarketplaceService", "GetProductInfo"): "MarketplaceService:GetProductInfoAsync",
    ("MarketplaceService", "PlayerOwnsAsset"): "MarketplaceService:PlayerOwnsAssetAsync",
    ("MarketplaceService", "PlayerOwnsBundle"): "MarketplaceService:PlayerOwnsBundleAsync",
    ("GamePassService", "PlayerHasPass"): "MarketplaceService:UserOwnsGamePassAsync(userId, gamePassId)",
    ("BadgeService", "AwardBadge"): "BadgeService:AwardBadgeAsync",
    ("BadgeService", "UserHasBadge"): "BadgeService:UserHasBadgeAsync",
    ("PhysicsService", "CreateCollisionGroup"): "PhysicsService:RegisterCollisionGroup",
    ("PhysicsService", "RemoveCollisionGroup"): "PhysicsService:UnregisterCollisionGroup",
    ("PhysicsService", "SetPartCollisionGroup"): "the BasePart.CollisionGroup property",
    ("PhysicsService", "GetCollisionGroups"): "PhysicsService:GetRegisteredCollisionGroups",
    ("PhysicsService", "GetCollisionGroupId"): "the BasePart.CollisionGroup property",
    ("PhysicsService", "GetCollisionGroupName"): "the BasePart.CollisionGroup property",
    ("PhysicsService", "CollisionGroupContainsPart"): "the BasePart.CollisionGroup property",
    ("Players", "GetHumanoidDescriptionFromUserId"): "Players:GetHumanoidDescriptionFromUserIdAsync",
    ("Players", "GetHumanoidDescriptionFromOutfitId"): "Players:GetHumanoidDescriptionFromOutfitIdAsync",
    ("Players", "CreateHumanoidModelFromUserId"): "Players:CreateHumanoidModelFromUserIdAsync",
    ("Players", "CreateHumanoidModelFromDescription"): "Players:CreateHumanoidModelFromDescriptionAsync",
    ("Players", "getPlayers"): "Players:GetPlayers",
    ("Players", "players"): "Players:GetPlayers",
    ("Players", "playerFromCharacter"): "Players:GetPlayerFromCharacter",
    ("ContentProvider", "Preload"): "ContentProvider:PreloadAsync",
    ("ContextActionService", "BindActionToInputTypes"): "ContextActionService:BindAction",
    ("PathfindingService", "ComputeRawPathAsync"): "PathfindingService:CreatePath() and Path:ComputeAsync",
    ("PathfindingService", "ComputeSmoothPathAsync"): "PathfindingService:CreatePath() and Path:ComputeAsync",
    ("CollectionService", "GetCollection"): "CollectionService:GetTagged",
    ("LocalizationService", "GetTranslatorForPlayer"): "LocalizationService:GetTranslatorForPlayerAsync",
    ("InsertService", "loadAsset"): "InsertService:LoadAsset",
    ("Lighting", "getMinutesAfterMidnight"): "Lighting:GetMinutesAfterMidnight",
    ("Lighting", "setMinutesAfterMidnight"): "Lighting:SetMinutesAfterMidnight",
    ("Debris", "addItem"): "Debris:AddItem",
    ("Chat", "FilterStringForPlayerAsync"): "TextService:FilterStringAsync",
}

# Instance methods whose deprecated spelling is unlikely to be a user-defined method name.
DEPRECATED_INSTANCE_METHODS: dict[str, str] = {
    "findFirstChild": "FindFirstChild",
    "getChildren": "GetChildren",
    "children": "GetChildren",
    "isDescendantOf": "IsDescendantOf",
    "Remove": "Destroy",  # only reported for the zero-argument call Instance:Remove()
}

# Instance.new class name -> replacement.
DEPRECATED_CLASSES: dict[str, str] = {
    "BodyVelocity": "LinearVelocity",
    "BodyPosition": "AlignPosition",
    "BodyGyro": "AlignOrientation",
    "BodyForce": "VectorForce",
    "BodyThrust": "VectorForce",
    "BodyAngularVelocity": "AngularVelocity",
    "RocketPropulsion": "LineForce with AlignOrientation",
    "Glue": "WeldConstraint",
    "ManualGlue": "WeldConstraint",
    "ManualWeld": "WeldConstraint",
    "Snap": "WeldConstraint",
    "Rotate": "HingeConstraint",
    "RotateP": "HingeConstraint",
    "RotateV": "HingeConstraint",
    "Message": "a TextLabel in a ScreenGui",
    "Hint": "a TextLabel in a ScreenGui",
    "HopperBin": "Tool",
    "Hat": "Accessory",
}

DEPRECATED_GLOBALS: dict[str, str] = {
    "ypcall": "pcall",
    "elapsedTime": "time() or os.clock()",
    "stats": 'game:GetService("Stats")',
    "version": "no replacement; avoid version checks",
    "printidentity": "no replacement; remove it",
    "getfenv": "explicit module tables (getfenv disables Luau optimisations)",
    "setfenv": "explicit module tables (setfenv disables Luau optimisations)",
}

DEPRECATED_TABLE_FUNCTIONS: dict[str, str] = {
    "getn": "#t",
    "foreach": "a for loop",
    "foreachi": "a for loop",
}

DEPRECATED_PROPERTIES: dict[str, str] = {
    "FilteringEnabled": "nothing: filtering is always on, so remove the read or write",
}

_LONG_LIVED_SERVICES = frozenset((
    "RunService", "UserInputService", "Players", "Workspace", "ReplicatedStorage", "Lighting", "SoundService",
    "CollectionService", "ContextActionService", "TextChatService", "MarketplaceService", "GuiService",
))
_FRAME_EVENTS = frozenset((
    "Heartbeat", "RenderStepped", "Stepped", "PreRender", "PreSimulation", "PostSimulation", "PreAnimation",
))
_REMOTE_SENDS = frozenset(("FireServer", "FireClient", "FireAllClients", "InvokeServer"))
_COMPOUND = frozenset(("+", "-", "*", "/", "%", "^", ".."))
_IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z", re.ASCII)
_LITERAL_ARG = re.compile(r"""\s*(['"])([A-Za-z_][A-Za-z_0-9]*)\1\s*[),]""")
_THROTTLE_HINT = re.compile(r"last|interval|elapsed|accum|throttle|cooldown|rate|prev|changed|dirty|^clock$|^tick$|^time$")


def _is_ident(word: str) -> bool:
    return bool(_IDENT.match(word)) and word not in (
        "and", "or", "not", "local", "function", "end", "if", "then", "else", "elseif", "for", "while", "do",
        "repeat", "until", "return", "break", "continue", "in", "nil", "true", "false")


def _close(words: list[str], start: int, opening: str = "(", closing: str = ")") -> int:
    depth = 0
    for i in range(start, len(words)):
        if words[i] == opening:
            depth += 1
        elif words[i] == closing:
            depth -= 1
            if depth == 0:
                return i
    return len(words)


def _open(words: list[str], close_at: int) -> int:
    depth = 0
    for i in range(close_at, -1, -1):
        if words[i] == ")":
            depth += 1
        elif words[i] == "(":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _function_end(words: list[str], start: int) -> int:
    """Index of the ``end`` closing the block opened at ``start`` (a ``function`` token)."""
    stack: list[str] = []
    pending_do = 0
    for i in range(start, len(words)):
        word = words[i]
        if word in ("function", "if", "repeat"):
            stack.append(word)
        elif word in ("while", "for"):
            stack.append("loop")
            pending_do += 1
        elif word == "do":
            if pending_do:
                pending_do -= 1
            else:
                stack.append("do")
        elif word == "until":
            if stack and stack[-1] == "repeat":
                stack.pop()
                if not stack:
                    return i
        elif word == "end" and stack:
            stack.pop()
            if not stack:
                return i
    return len(words)


def _top_level_args(words: list[str], opening: int) -> list[list[str]]:
    closing = _close(words, opening)
    result: list[list[str]] = [[]]
    depth = 0
    for word in words[opening + 1:closing]:
        if word in ("(", "{", "["):
            depth += 1
        elif word in (")", "}", "]"):
            depth -= 1
        if word == "," and depth == 0:
            result.append([])
        else:
            result[-1].append(word)
    return [] if result == [[]] else result


def _literal_after(code: str, tokens: list, opening: int) -> str | None:
    """The string literal that is the whole first argument of the call whose ``(`` token is ``opening``."""
    match = _LITERAL_ARG.match(code, tokens[opening].offset + 1)
    return match.group(2) if match else None


def _assignment_target(words: list[str], equals: int) -> str | None:
    """NAME for ``NAME = ...`` or ``NAME: Type = ...`` (not a field or an index)."""
    if equals < 1 or words[equals + 1:equals + 2] == ["="] or words[equals - 1] in ("=", "~", "<", ">"):
        return None
    name_at = equals - 1
    if equals >= 3 and words[equals - 2] == ":" and _is_ident(words[equals - 1]):
        name_at = equals - 3
    if name_at < 0 or not _is_ident(words[name_at]):
        return None
    if name_at and words[name_at - 1] in (".", ":"):
        return None
    return words[name_at]


def _service_aliases(code: str, tokens: list, words: list[str]) -> dict[str, str]:
    aliases = {"workspace": "Workspace"}
    for i in range(len(words) - 5):
        if words[i:i + 4] == ["game", ":", "GetService", "("] and (i == 0 or words[i - 1] not in (".", ":")):
            service = _literal_after(code, tokens, i + 3)
            close = _close(words, i + 3)
            if service and i >= 2 and words[i - 1] == "=" and words[close + 1:close + 2] != ["."]:
                target = _assignment_target(words, i - 1)
                if target:
                    aliases[target] = service
    return aliases


def _receiver_service(code: str, tokens: list, words: list[str], colon: int, aliases: dict[str, str]) -> str | None:
    """The service a ``receiver:method`` call is made on, when that is plain to see."""
    before = colon - 1
    if before < 0:
        return None
    if words[before] == ")":
        opening = _open(words, before)
        if opening >= 3 and words[opening - 3:opening] == ["game", ":", "GetService"]:
            return _literal_after(code, tokens, opening)
        return None
    if _is_ident(words[before]) and (before == 0 or words[before - 1] not in (".", ":")):
        return aliases.get(words[before])
    if _is_ident(words[before]) and before >= 2 and words[before - 2:before] == ["game", "."]:
        return words[before]  # game.Workspace:Method(...)
    return None


def _locally_bound(words: list[str], name: str) -> bool:
    for i, word in enumerate(words[:-1]):
        if word in ("local", "function") and words[i + 1] == name:
            return True
    # Function parameters named like the global also shadow it.
    for i, word in enumerate(words):
        if word == "function":
            opening = next((j for j in range(i + 1, min(i + 8, len(words))) if words[j] == "("), None)
            if opening is not None and name in words[opening + 1:_close(words, opening)]:
                return True
    return False


def _chain_start(words: list[str], end: int) -> int:
    """Walk back over a ``a.b:c(...)[d].e`` expression that ends at ``end``."""
    i = end
    while i > 0:
        word = words[i]
        if word in (")", "]"):
            i = _open(words, i) if word == ")" else _open_bracket(words, i)
            if i <= 0:
                return max(i, 0)
            i -= 1
            continue
        if _is_ident(word) and words[i - 1] in (".", ":"):
            i -= 2
            continue
        return i
    return i


def _open_bracket(words: list[str], close_at: int) -> int:
    depth = 0
    for i in range(close_at, -1, -1):
        if words[i] == "]":
            depth += 1
        elif words[i] == "[":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _function_named(words: list[str], name: str) -> int | None:
    """Index of the ``function`` token that defines ``name`` (``function name(`` or ``name = function(``)."""
    for i in range(len(words) - 2):
        if words[i] == "function" and words[i + 1] == name and words[i + 2] == "(":
            return i
        if words[i] == name and words[i + 1] == "=" and words[i + 2] == "function" and (
                not i or words[i - 1] not in (".", ":")):
            return i + 2
    return None


def _handlers(words: list[str], event: str) -> list[tuple[int, int, int]]:
    """(event token, function token, end token) for ``X.<event>:Connect(function ... end)`` and for
    ``X.<event>:Connect(name)`` when ``name`` is a function defined in the same script."""
    found = []
    for i in range(len(words) - 4):
        if words[i] != event or words[i + 1:i + 4] not in ([":", "Connect", "("], [":", "connect", "("]):
            continue
        if words[i + 4] == "function":
            found.append((i, i + 4, _function_end(words, i + 4)))
        elif _is_ident(words[i + 4]) and words[i + 5:i + 6] == [")"]:
            fn = _function_named(words, words[i + 4])
            if fn is not None:
                found.append((i, fn, _function_end(words, fn)))
    return found


def lint_roblox_rules(code: str, *, script_class: str | None = None) -> list[Finding]:
    """Return the Roblox-specific findings for one script. ``script_class`` is trusted caller metadata."""
    if not isinstance(code, str):
        raise TypeError("code must be str")
    tokens = _tokens(code)
    words = [t.value for t in tokens]
    findings: list[Finding] = []

    def add(rule: str, index: int, message: str, fix: str, severity: str = "warning") -> None:
        findings.append(Finding(rule, tokens[index].line, message, fix, severity))

    aliases = _service_aliases(code, tokens, words)
    size = len(words)

    # deprecated-api
    for i, word in enumerate(words):
        prev = words[i - 1] if i else ""
        nxt = words[i + 1] if i + 1 < size else ""
        if prev == ":" and nxt == "(":
            service = _receiver_service(code, tokens, words, i - 1, aliases)
            replacement = DEPRECATED_SERVICE_METHODS.get((service or "", word))
            if replacement:
                add("deprecated-api", i, f"{service}:{word} is deprecated.", f"Use {replacement}.")
            elif word in DEPRECATED_INSTANCE_METHODS and (word != "Remove" or words[i + 2:i + 3] == [")"]):
                add("deprecated-api", i, f"Instance:{word} is deprecated.",
                    f"Use {DEPRECATED_INSTANCE_METHODS[word]}().")
        elif word == "new" and words[i - 2:i] == ["Instance", "."] and nxt == "(":
            class_name = _literal_after(code, tokens, i + 1)
            if class_name in DEPRECATED_CLASSES:
                add("deprecated-api", i, f"The {class_name} class is deprecated.",
                    f"Use {DEPRECATED_CLASSES[class_name]} instead.")
        elif word in DEPRECATED_GLOBALS and nxt == "(" and prev not in (".", ":", "function", "local"):
            if not _locally_bound(words, word):
                add("deprecated-api", i, f"The global {word}() is deprecated.", f"Use {DEPRECATED_GLOBALS[word]}.")
        elif word == "table" and nxt == "." and words[i + 2:i + 3] and words[i + 2] in DEPRECATED_TABLE_FUNCTIONS \
                and words[i + 3:i + 4] == ["("] and prev not in (".", ":"):
            name = words[i + 2]
            add("deprecated-api", i, f"table.{name} is deprecated.", f"Use {DEPRECATED_TABLE_FUNCTIONS[name]}.")
        elif word in DEPRECATED_PROPERTIES and prev == "." and nxt != "(":
            add("deprecated-api", i, f"{word} is deprecated.", f"Use {DEPRECATED_PROPERTIES[word]}.")

    # pcall-called-result
    for i, word in enumerate(words):
        if word in ("pcall", "xpcall") and i + 1 < size and words[i + 1] == "(" and (not i or words[i - 1] not in (".", ":")):
            arguments = _top_level_args(words, i + 1)
            first = arguments[0] if arguments else []
            if first and first[0] not in ("function", "(") and first[-1] == ")" and "(" in first:
                add("pcall-called-result", i,
                    f"{word} receives the result of a call, so the call runs (and can throw) before {word} protects it.",
                    f"Pass the function and its arguments, e.g. {word}(store.GetAsync, store, key), "
                    f"or wrap the call in a function.", "error")

    # server-invoke-client
    for i, word in enumerate(words):
        if word == "InvokeClient" and i and words[i - 1] == ":" and words[i + 1:i + 2] == ["("]:
            add("server-invoke-client", i,
                "RemoteFunction:InvokeClient lets a client stall or break the server thread: a client error is "
                "rethrown, a disconnect throws, and a client that never returns yields forever.",
                "Use RemoteEvent:FireClient and let the client answer with its own RemoteEvent.")

    # fireserver-player-argument
    local_players = set()
    for i, word in enumerate(words):
        if word == "LocalPlayer" and i and words[i - 1] == "." and words[i + 1:i + 2] not in (["."], [":"], ["("], ["["]):
            start = _chain_start(words, i)
            if start >= 1 and words[start - 1] == "=":
                target = _assignment_target(words, start - 1)
                if target:
                    local_players.add(target)
    for i, word in enumerate(words):
        if word in ("FireServer", "InvokeServer") and i and words[i - 1] == ":" and words[i + 1:i + 2] == ["("]:
            arguments = _top_level_args(words, i + 1)
            first = arguments[0] if arguments else []
            if (len(first) == 1 and first[0] in local_players) or (first[-1:] == ["LocalPlayer"] and len(first) >= 3
                                                                    and first[-2] == "."):
                add("fireserver-player-argument", i,
                    f"{word} passes the local player, but the server already receives the sender as the first "
                    "argument, so every argument after it is shifted.",
                    "Remove the player argument and read the sender from the server handler's first parameter.")

    # client-leaderstats-write
    client = script_class == "LocalScript" or (script_class is None and "LocalPlayer" in words)
    if client:
        tainted = set()
        for i, word in enumerate(words):
            if word == "=" and (i + 1 >= size or words[i + 1] != "="):
                target = _assignment_target(words, i)
                if target and i + 1 < size:
                    line_end = code.find("\n", tokens[i].offset)
                    expression = code[tokens[i].offset + 1:line_end if line_end >= 0 else len(code)]
                    if "leaderstats" in expression:
                        tainted.add(target)
        for i, word in enumerate(words):
            if word != "Value" or not i or words[i - 1] != ".":
                continue
            after = words[i + 1:i + 3]
            if not (after[:1] == ["="] and after[1:2] != ["="]) and not (
                    after[:1] and after[0] in _COMPOUND and after[1:2] == ["="]):
                continue
            start = _chain_start(words, i)
            chain_text = code[tokens[start].offset:tokens[i].offset]
            if "leaderstats" in chain_text or words[start] in tainted:
                add("client-leaderstats-write", i,
                    "A LocalScript changing a leaderstats value only changes this client's copy; the server and "
                    "other players never see it.",
                    "Ask the server with a validated RemoteEvent and change the value in a server Script.")

    # playeradded-existing-players
    if "GetPlayers" not in words:
        for i, word in enumerate(words):
            if word == "PlayerAdded" and words[i + 1:i + 3] in ([":", "Connect"], [":", "connect"]):
                add("playeradded-existing-players", i,
                    "Players who joined before this connection runs (for example in a solo Studio playtest, or after "
                    "a yield) never get this handler.",
                    "After connecting, also call the handler for each player in Players:GetPlayers().", "review")
                break

    # characteradded-existing-character
    player_added = _handlers(words, "PlayerAdded")
    reads_character = any(w == "Character" and i and words[i - 1] == "." for i, w in enumerate(words))
    if not reads_character:
        for i, word in enumerate(words):
            if word == "CharacterAdded" and words[i + 1:i + 3] in ([":", "Connect"], [":", "connect"]) \
                    and not any(fn < i < end for _, fn, end in player_added):
                add("characteradded-existing-character", i,
                    "CharacterAdded only fires for future characters; a character that already exists when this "
                    "runs is never handled.",
                    "Also handle player.Character if it is already set, then connect CharacterAdded.", "review")
                break

    # per-player-connection-leak
    seen: set[int] = set()
    for event in ("PlayerAdded", "CharacterAdded"):
        for _, fn, end in _handlers(words, event):
            body = words[fn:end]
            if "Disconnect" in body or "disconnect" in body:
                continue
            for j in range(fn + 1, end):
                if words[j] not in ("Connect", "connect") or words[j - 1] != ":" or words[j + 1:j + 2] != ["("]:
                    continue
                signal_at = j - 2
                start = _chain_start(words, signal_at)
                root = words[start]
                long_lived = aliases.get(root) in _LONG_LIVED_SERVICES or words[signal_at] in (
                    "OnServerEvent", "OnClientEvent") or root == "game"
                assigned = start >= 1 and words[start - 1] == "="
                if long_lived and not assigned and j not in seen:
                    seen.add(j)
                    add("per-player-connection-leak", j,
                        f"This {event} handler connects to a long-lived signal ({words[signal_at]}) on every "
                        f"{'join' if event == 'PlayerAdded' else 'respawn'} and never disconnects, so handlers pile "
                        "up and keep running after the player or character is gone.",
                        "Connect once outside the handler, or keep the connection and Disconnect it on "
                        "PlayerRemoving, CharacterRemoving or Humanoid.Died.")

    # remote-every-frame
    for i, word in enumerate(words):
        frame_callback = None
        if word in _FRAME_EVENTS and i >= 2 and words[i - 1] == "." and aliases.get(words[i - 2]) == "RunService" \
                and words[i + 1:i + 5] in ([":", "Connect", "(", "function"], [":", "connect", "(", "function"]):
            frame_callback = i + 4
        elif word == "BindToRenderStep" and words[i - 1:i] == [":"] and words[i + 1:i + 2] == ["("]:
            frame_callback = next((j for j in range(i + 2, _close(words, i + 1)) if words[j] == "function"), None)
        if frame_callback is None:
            continue
        end = _function_end(words, frame_callback)
        body = words[frame_callback:end]
        sends = [frame_callback + k for k, w in enumerate(body)
                 if w in _REMOTE_SENDS and k and body[k - 1] == ":"]
        if sends and not any(_THROTTLE_HINT.search(w.lower()) for w in body):
            add("remote-every-frame", sends[0],
                "A remote is sent from a per-frame callback, about 60 messages a second per player; client-to-server "
                "remotes share a rate limit and excess traffic adds latency.",
                "Send on change or at a fixed interval tracked with os.clock(), or use UnreliableRemoteEvent "
                "for frequent cosmetic state.")

    return sorted(set(findings), key=lambda f: (f.line, f.rule_id, f.message))
