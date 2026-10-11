"""Offline Roblox craft audit and reviewed native-Luau starter recipes.

Inputs are bounded summaries from authorized Studio read tools, not executable
code or a complete DataModel dump. Findings are evidence-linked heuristics;
visual quality and animation playback still require real Studio tests.
"""
from __future__ import annotations

from collections import Counter
import json
import math
import re

MAX_INSTANCES = 160
MAX_SCRIPTS = 12
MAX_SNAPSHOT_BYTES = 120_000
MAX_SCRIPT_CHARS = 20_000
MAX_FINDINGS = 80

DOCS = {
    "luau": "https://create.roblox.com/docs/luau/type-checking",
    "ui": "https://create.roblox.com/docs/ui/size-modifiers",
    "accessibility": "https://create.roblox.com/docs/production/publishing/accessibility",
    "buttons": "https://create.roblox.com/docs/reference/engine/classes/GuiButton",
    "particles": "https://create.roblox.com/docs/reference/engine/classes/ParticleEmitter",
    "beams": "https://create.roblox.com/docs/effects/beams",
    "trails": "https://create.roblox.com/docs/effects/trails",
    "animations": "https://create.roblox.com/docs/reference/engine/classes/Animator",
    "markers": "https://create.roblox.com/docs/animation/events",
    "performance": "https://create.roblox.com/docs/performance-optimization/improve",
}

PARTS = frozenset({"Part", "MeshPart", "UnionOperation", "WedgePart", "CornerWedgePart",
                   "SpawnLocation", "Seat", "VehicleSeat", "TrussPart"})
TEXT_OBJECTS = frozenset({"TextLabel", "TextButton", "TextBox"})
GUI_OBJECTS = frozenset({"Frame", "ScrollingFrame", "CanvasGroup", "TextLabel", "TextButton",
                         "TextBox", "ImageLabel", "ImageButton", "ViewportFrame", "VideoFrame"})
EFFECT_OBJECTS = frozenset({"ParticleEmitter", "Beam", "Trail"})
ANIMATION_OBJECTS = frozenset({"Animator", "Animation", "AnimationController", "Humanoid"})


def _instance_path(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 220 or "\x00" in value \
            or any(ch in value for ch in "\r\n"):
        raise ValueError("Each instance and script needs a bounded, nonempty Studio path")
    return value


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _offset(value: object) -> float | None:
    """Only assert offset evidence from explicit normalized UDim2 data."""
    if not isinstance(value, dict):
        return None
    if not {"xScale", "xOffset", "yScale", "yOffset"} <= set(value):
        return None
    xscale, yscale = _number(value["xScale"]), _number(value["yScale"])
    xoff, yoff = _number(value["xOffset"]), _number(value["yOffset"])
    if None in (xscale, yscale, xoff, yoff) or xscale != 0 or yscale != 0:
        return None
    return max(abs(xoff), abs(yoff))


def _lifetime_max(value: object) -> float | None:
    if isinstance(value, dict):
        return _number(value.get("Max", value.get("max")))
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return _number(value[1])
    return _number(value)


def _missing(value: object) -> bool:
    return value is None or value == "" or value == "nil"


def audit(instances: list[dict], scripts: list[dict] | None = None, *, target: str = "mobile") -> dict:
    """Audit explicit facts. Missing properties never prove an issue unless complete=True."""
    if target not in {"mobile", "desktop"}:
        raise ValueError("Choose mobile or desktop")
    scripts = [] if scripts is None else scripts
    if not isinstance(instances, list) or not isinstance(scripts, list) \
            or len(instances) > MAX_INSTANCES or len(scripts) > MAX_SCRIPTS:
        raise ValueError("Studio snapshot is malformed or larger than the bounded review")
    try:
        encoded = json.dumps({"instances": instances, "scripts": scripts}, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Studio snapshot must contain finite JSON-compatible values") from exc
    if len(encoded.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        raise ValueError("Studio snapshot is too large")
    paths: set[str] = set()
    by_path: dict[str, dict] = {}
    for instance in instances:
        if not isinstance(instance, dict):
            raise ValueError("An instance must be an object")
        path = _instance_path(instance.get("path"))
        kind = instance.get("class")
        properties = instance.get("properties", {})
        if path in paths or not isinstance(kind, str) or not 1 <= len(kind) <= 80 \
                or not isinstance(properties, dict) or len(properties) > 80 \
                or type(instance.get("complete", False)) is not bool:
            raise ValueError("Duplicate path, class, completeness or properties in Studio snapshot")
        if any(not isinstance(key, str) or len(key) > 90 for key in properties):
            raise ValueError("Property names must be short strings")
        paths.add(path)
        by_path[path] = {"class": kind, "properties": properties, "complete": instance.get("complete", False)}
    for entry in scripts:
        if not isinstance(entry, dict):
            raise ValueError("A script must be an object")
        path = _instance_path(entry.get("path"))
        kind, source = entry.get("class"), entry.get("source")
        if kind not in {"Script", "LocalScript", "ModuleScript"} \
                or not isinstance(source, str) or len(source) > MAX_SCRIPT_CHARS:
            raise ValueError("Expected a bounded Luau source and real script class")

    issues: list[dict] = []

    def add(rule: str, category: str, severity: str, path: str, evidence: str,
            action: str, *, doc: str, certainty: str = "observed") -> None:
        if len(issues) >= MAX_FINDINGS:
            return
        issues.append({"rule": rule, "category": category, "severity": severity,
                       "certainty": certainty, "path": path, "evidence": evidence,
                       "recommendation": action, "documentation": DOCS[doc]})

    for path in sorted(by_path):
        node = by_path[path]
        kind, prop, complete = node["class"], node["properties"], node["complete"]
        parent = by_path.get(path.rpartition(".")[0])
        if kind == "ScreenGui" and prop.get("ScreenInsets") is not None \
                and str(prop["ScreenInsets"]) in {"None", "Enum.ScreenInsets.None"}:
            add("ui-unsafe-insets", "ui", "warning", path, "ScreenInsets is explicitly None.",
                "Use safe insets unless the visual and control layout were verified on notched screens.",
                doc="accessibility")
        if kind in GUI_OBJECTS and target == "mobile":
            offset = _offset(prop.get("Size"))
            if offset is not None and offset > 480:
                add("ui-fixed-size", "ui", "review", path,
                    "Size uses only pixel offsets and its largest absolute component exceeds 480.",
                    "Add scale-based sizing, constraints, or a verified small-screen layout.",
                    doc="ui", certainty="heuristic")
        if kind in TEXT_OBJECTS:
            if prop.get("TextScaled") is True and complete \
                    and not any(q["class"] == "UITextSizeConstraint" and p.rpartition(".")[0] == path
                                for p, q in by_path.items()):
                add("ui-text-constraint", "ui", "review", path,
                    "TextScaled is true; no UITextSizeConstraint child appears in the supplied sample.",
                    "Check for an existing child constraint in Studio, then test preferred text size.",
                    doc="accessibility", certainty="heuristic")
            if prop.get("TextWrapped") is False and isinstance(prop.get("Text"), str) \
                    and len(prop["Text"]) > 65:
                add("ui-long-unwrapped-text", "ui", "review", path,
                    "A long visible text string has TextWrapped=false.",
                    "Inspect actual text bounds at mobile and translated text lengths.",
                    doc="ui", certainty="heuristic")
        if kind == "ParticleEmitter":
            if parent and parent["class"] not in PARTS | {"Attachment"}:
                add("vfx-parent", "vfx", "warning", path,
                    "ParticleEmitter is not parented directly to a BasePart or Attachment.",
                    "Parent it to a real BasePart or Attachment before expecting emission.",
                    doc="particles")
            rate = _number(prop.get("Rate"))
            lifetime = _lifetime_max(prop.get("Lifetime"))
            if target == "mobile" and rate is not None and rate > 100:
                add("vfx-rate", "vfx", "review", path, f"Configured Rate is {rate:g} particles/second.",
                    "Profile simultaneous effects on target devices. 100 is a STAR review threshold, not an engine cap.",
                    doc="performance", certainty="heuristic")
            if rate is not None and lifetime is not None and rate * lifetime > 300:
                add("vfx-occupancy", "vfx", "review", path,
                    f"Rate × maximum lifetime is {rate * lifetime:g} potential live particles.",
                    "Review overdraw and simultaneous effect counts with a real device capture.",
                    doc="particles", certainty="heuristic")
        if kind in {"Beam", "Trail"}:
            for attachment in ("Attachment0", "Attachment1"):
                if (attachment in prop and _missing(prop[attachment])) \
                        or (complete and attachment not in prop):
                    add("vfx-missing-attachment", "vfx", "warning", path,
                        f"{attachment} is missing in the supplied Studio properties.",
                        "Bind two distinct Attachment instances and check the effect in Workspace.",
                        doc="beams" if kind == "Beam" else "trails")
            lifetime = _number(prop.get("Lifetime"))
            if kind == "Trail" and lifetime is not None and lifetime > 3:
                add("vfx-long-trail", "vfx", "review", path,
                    f"Trail Lifetime is {lifetime:g} seconds.",
                    "Verify that lingering geometry and transparency are intentional.",
                    doc="trails", certainty="heuristic")
        if kind == "Animation" and "AnimationId" in prop \
                and str(prop["AnimationId"]).strip() in {"", "0", "rbxassetid://0"}:
            add("animation-missing-id", "animation", "warning", path,
                "AnimationId does not identify an authored uploaded animation.",
                "Create or import a rig-compatible clip and set an owner-authorized animation asset ID.",
                doc="animations")
        if kind == "Animator" and parent and parent["class"] not in {"Humanoid", "AnimationController"}:
            add("animation-animator-owner", "animation", "review", path,
                f"Parent class is {parent['class']}, not Humanoid or AnimationController.",
                "Confirm the Animator's owner, replication and rig hierarchy in Studio.",
                doc="animations", certainty="heuristic")

    for script in sorted(scripts, key=lambda entry: entry["path"]):
        path, source = script["path"], script["source"]
        if not re.search(r"(?m)^\s*--!strict\b", source):
            add("luau-strict", "code", "review", path, "No --!strict directive was observed.",
                "Consider strict mode, then run the real Luau analyzer and fix type diagnostics.",
                doc="luau", certainty="heuristic")
        if script["class"] == "LocalScript" and re.search(r'GetService\s*\(\s*["\x27]DataStoreService', source):
            add("luau-datastore-client", "code", "warning", path,
                "A LocalScript requests server-only DataStoreService.",
                "Move DataStore operations to server scripts and validate client requests.",
                doc="luau")
        if re.search(r"\b(?:wait|spawn|delay)\s*\(", source):
            add("luau-legacy-task", "code", "review", path,
                "Source text may contain legacy wait/spawn/delay calls.",
                "Check the match is executable code, then prefer the task library where appropriate.",
                doc="performance", certainty="heuristic")
        if re.search(r"\bhumanoid\s*:\s*LoadAnimation\s*\(", source, flags=re.I):
            add("animation-legacy-load", "animation", "review", path,
                "Source text appears to call Humanoid:LoadAnimation.",
                "Retrieve the Animator and load an authored Animation through Animator:LoadAnimation.",
                doc="animations", certainty="heuristic")
        if "OnServerEvent" in source and not re.search(r"\b(?:typeof|type|validate|Validate|assert)\b", source):
            add("luau-remote-review", "code", "review", path,
                "An OnServerEvent handler appears with no obvious validation token.",
                "Manually review payload validation, rate limits and server-authoritative state.",
                doc="luau", certainty="heuristic")

    counts = Counter(node["class"] for node in by_path.values())
    return {
        "read_only": True, "executed": False, "snapshot_incomplete": True,
        "target": target, "reviewed_instances": len(instances),
        "reviewed_scripts": len(scripts), "complete_property_sets": sum(
            1 for node in by_path.values() if node["complete"]),
        "domains": {"ui": sum(counts[k] for k in GUI_OBJECTS | {"ScreenGui", "SurfaceGui", "BillboardGui"}),
                    "vfx": sum(counts[k] for k in EFFECT_OBJECTS),
                    "animation": sum(counts[k] for k in ANIMATION_OBJECTS),
                    "code": len(scripts)},
        "findings": issues, "findings_truncated": len(issues) >= MAX_FINDINGS,
        "limitations": [
            "A sampled hierarchy is not the whole experience; absent properties are unknown unless marked complete.",
            "Source patterns are heuristic, not a parsed AST or a Luau type-checker result.",
            "No screenshot, animation clip, running gameplay or GPU profiling was inspected.",
            "Native editable UI, live rig alignment and VFX appearance need Studio/device playtests.",
        ],
        "next_steps": [
            "Capture real screen shots at phone, desktop and gamepad viewports.",
            "Run Luau type analysis and a disposable Studio playtest; inspect console output.",
            "Use only STAR's owner-authorized edit and test workflow to apply approved changes.",
        ],
    }


_UI_RECIPE = """--!strict
-- Example native UI. Customize interactions and run device-emulator checks before release.
local Players = game:GetService("Players")
local TweenService = game:GetService("TweenService")
local GuiService = game:GetService("GuiService")
local playerGui = Players.LocalPlayer:WaitForChild("PlayerGui")
local existing = playerGui:FindFirstChild("StarSampleHUD")
if existing then existing:Destroy() end

local gui = Instance.new("ScreenGui")
gui.Name = "StarSampleHUD"
gui.ResetOnSpawn = false
gui.ScreenInsets = Enum.ScreenInsets.CoreUISafeInsets
gui.Parent = playerGui

local panel = Instance.new("Frame")
panel.Name = "Actions"
panel.AnchorPoint = Vector2.new(0.5, 1)
panel.Position = UDim2.fromScale(0.5, 0.96)
panel.Size = UDim2.new(0.64, 0, 0, 92)
panel.BackgroundColor3 = Color3.fromRGB(22, 24, 29)
panel.BorderSizePixel = 0
panel.Parent = gui

local bounds = Instance.new("UISizeConstraint")
bounds.MinSize = Vector2.new(190, 82)
bounds.MaxSize = Vector2.new(340, 100)
bounds.Parent = panel
local outline = Instance.new("UIStroke")
outline.Thickness = 1
outline.Color = Color3.fromRGB(85, 89, 99)
outline.Parent = panel
local padding = Instance.new("UIPadding")
padding.PaddingLeft = UDim.new(0, 12)
padding.PaddingRight = UDim.new(0, 12)
padding.PaddingTop = UDim.new(0, 8)
padding.PaddingBottom = UDim.new(0, 8)
padding.Parent = panel
local stack = Instance.new("UIListLayout")
stack.Padding = UDim.new(0, 7)
stack.SortOrder = Enum.SortOrder.LayoutOrder
stack.Parent = panel

local heading = Instance.new("TextLabel")
heading.Name = "Heading"
heading.LayoutOrder = 1
heading.Size = UDim2.new(1, 0, 0, 24)
heading.BackgroundTransparency = 1
heading.Font = Enum.Font.GothamMedium
heading.Text = "STAR · Sample HUD"
heading.TextColor3 = Color3.fromRGB(245, 245, 246)
heading.TextSize = 16
heading.TextXAlignment = Enum.TextXAlignment.Left
heading.Parent = panel

local button = Instance.new("TextButton")
button.Name = "Action"
button.LayoutOrder = 2
button.Size = UDim2.new(1, 0, 0, 40)
button.BackgroundColor3 = Color3.fromRGB(53, 57, 66)
button.BorderSizePixel = 0
button.Font = Enum.Font.GothamMedium
button.Text = "Try action"
button.TextColor3 = Color3.fromRGB(245, 245, 246)
button.TextSize = 15
button.Selectable = true
button.Parent = panel

local activeTween: Tween? = nil
local function shade(color: Color3)
    if activeTween then activeTween:Cancel() end
    if GuiService.ReducedMotionEnabled then
        button.BackgroundColor3 = color
    else
        activeTween = TweenService:Create(button, TweenInfo.new(0.13), {BackgroundColor3 = color})
        activeTween:Play()
    end
end
button.MouseEnter:Connect(function() shade(Color3.fromRGB(66, 71, 82)) end)
button.MouseLeave:Connect(function() shade(Color3.fromRGB(53, 57, 66)) end)
button.Activated:Connect(function()
    heading.Text = "Action requested"
    -- Wire this to the actual game feature with a validated server request.
end)
"""

_VFX_RECIPE = """--!strict
-- Require on the client for cosmetic effects. Server gameplay must remain authoritative.
local Debris = game:GetService("Debris")
local VFX = {}

function VFX.burst(position: Vector3)
    local holder = Instance.new("Part")
    holder.Name = "StarImpactBurst"
    holder.Size = Vector3.new(0.2, 0.2, 0.2)
    holder.Position = position
    holder.Anchored = true
    holder.CanCollide = false
    holder.CanTouch = false
    holder.Transparency = 1
    holder.Parent = workspace

    local attachment = Instance.new("Attachment")
    attachment.Parent = holder

    local sparks = Instance.new("ParticleEmitter")
    sparks.Name = "Sparks"
    sparks.Enabled = false
    sparks.Rate = 0
    sparks.Lifetime = NumberRange.new(0.18, 0.35)
    sparks.Speed = NumberRange.new(10, 22)
    sparks.SpreadAngle = Vector2.new(180, 180)
    sparks.Drag = 4
    sparks.LightEmission = 0.25
    sparks.Color = ColorSequence.new(Color3.fromRGB(250, 214, 153), Color3.fromRGB(132, 135, 147))
    sparks.Size = NumberSequence.new({
        NumberSequenceKeypoint.new(0, 0.32),
        NumberSequenceKeypoint.new(1, 0),
    })
    sparks.Transparency = NumberSequence.new({
        NumberSequenceKeypoint.new(0, 0),
        NumberSequenceKeypoint.new(1, 1),
    })
    sparks.Parent = attachment
    sparks:Emit(18)

    local dust = Instance.new("ParticleEmitter")
    dust.Name = "SoftDust"
    dust.Enabled = false
    dust.Rate = 0
    dust.Lifetime = NumberRange.new(0.4, 0.65)
    dust.Speed = NumberRange.new(2, 5)
    dust.SpreadAngle = Vector2.new(70, 70)
    dust.Drag = 6
    dust.Color = ColorSequence.new(Color3.fromRGB(136, 139, 144))
    dust.Size = NumberSequence.new(0.45)
    dust.Transparency = NumberSequence.new({
        NumberSequenceKeypoint.new(0, 0.25),
        NumberSequenceKeypoint.new(1, 1),
    })
    dust.Parent = attachment
    dust:Emit(8)

    Debris:AddItem(holder, 1.5)
end

return VFX
"""

_ANIMATION_RECIPE = """--!strict
-- Provide a published Animation owned by the permitted creator and matching the real rig.
-- Place an "Impact" marker on the authored animation timeline in Studio.
-- The marker callback here is cosmetic: never authorize combat damage from this alone.
local AnimationCraft = {}

function AnimationCraft.prepare(animator: Animator, animation: Animation, onImpact: () -> ())
    local track = animator:LoadAnimation(animation)
    track.Priority = Enum.AnimationPriority.Action
    local markerConnection = track:GetMarkerReachedSignal("Impact"):Connect(function(_parameter)
        onImpact()
    end)
    local disposed = false
    return {
        play = function()
            if not disposed then track:Play(0.12, 1, 1) end
        end,
        stop = function()
            if not disposed then track:Stop(0.15) end
        end,
        destroy = function()
            if disposed then return end
            disposed = true
            markerConnection:Disconnect()
            track:Stop(0)
            track:Destroy()
        end,
    }
end

return AnimationCraft
"""

_RECIPES = {
    "responsive-hud": {
        "path": "StarterPlayer/StarterPlayerScripts/StarSampleHUD.client.luau",
        "class": "LocalScript", "source": _UI_RECIPE,
        "requires": ["Native Roblox UI in PlayerGui", "Real game action wiring", "Phone, desktop and gamepad review"],
        "docs": [DOCS["ui"], DOCS["accessibility"], DOCS["buttons"]],
    },
    "impact-vfx": {
        "path": "ReplicatedStorage/Shared/StarImpactVFX.luau",
        "class": "ModuleScript", "source": _VFX_RECIPE,
        "requires": ["Require and invoke on the client for a validated visual event", "Profile concurrent effects on mobile"],
        "docs": [DOCS["particles"], DOCS["performance"]],
    },
    "animation-marker": {
        "path": "ReplicatedStorage/Shared/StarAnimationCraft.luau",
        "class": "ModuleScript", "source": _ANIMATION_RECIPE,
        "requires": ["Real compatible R6/R15/custom Animator", "Owned uploaded Animation with Impact event marker",
                     "Server-authoritative gameplay logic and playback review"],
        "docs": [DOCS["animations"], DOCS["markers"]],
    },
}


def recipe(kind: str) -> dict:
    """Return deterministic source for review; never write or execute it."""
    if kind not in _RECIPES:
        raise ValueError("Unknown Roblox craft recipe")
    chosen = _RECIPES[kind]
    return {"recipe": kind, "source_path": chosen["path"], "script_class": chosen["class"],
            "luau": chosen["source"], "requirements": list(chosen["requires"]),
            "documentation": list(chosen["docs"]), "preview_only": True,
            "installed": False, "executed": False,
            "next_step": "Review code and install only through an authorized workspace or Studio edit, then test."}
