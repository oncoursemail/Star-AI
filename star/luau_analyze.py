"""Optional, bounded Luau CLI second opinion for STAR's existing static checks.

Runs only an explicitly opted-in local binary, not generated Luau source.
Offline, no automatic installation and no model or Roblox server connection.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import warnings

from .luau_lint import Finding

ENV_VAR = "STAR_LUAU_ANALYZE"
TOOLS_DIR_VAR = "STAR_LUAU_TOOLS_DIR"
PINNED_VERSION = "0.691"
MAX_SOURCE_BYTES = 20_000
MAX_OUTPUT_BYTES = 48_000
MAX_FINDINGS = 20
TIMEOUT_SECONDS = 6
_STAGED_NAME = "star-check.luau"
_DIAGNOSTIC = re.compile(
    r"^(?P<file>.*?)\((?P<line>[0-9]{1,6}),(?P<column>[0-9]{1,6})\): "
    r"(?P<kind>[A-Za-z][A-Za-z0-9]*): (?P<message>[^\r\n]*)$"
)
_UNKNOWN_SYMBOL = re.compile(
    r"""^Unknown (?P<what>global|type) ['"](?P<name>[A-Za-z_][A-Za-z_0-9]*)['"]""",
    re.IGNORECASE,
)
# The standalone CLI has no Roblox-specific engine type definitions.
_ROBLOX_SYMBOLS = frozenset({
    "game", "script", "workspace", "plugin", "shared", "task", "Enum",
    "Instance", "Vector3", "CFrame", "Color3", "UDim", "UDim2", "RaycastParams",
    "OverlapParams", "BasePart", "Player", "Players", "Model", "Humanoid",
    "Animation", "RBXScriptSignal", "RBXScriptConnection", "TweenInfo",
    "NumberSequence", "ColorSequence", "BrickColor", "Region3",
    # Engine data types and Roblox-only globals.
    "Vector2", "Vector2int16", "Vector3int16", "Region3int16", "NumberRange",
    "NumberSequenceKeypoint", "ColorSequenceKeypoint", "Random", "Ray", "RaycastResult",
    "DateTime", "Rect", "PhysicalProperties", "Font", "Faces", "Axes", "PathWaypoint",
    "SharedTable", "Content", "EnumItem", "Enums", "tick", "wait", "spawn", "delay", "time",
    "elapsedTime", "warn", "settings", "UserSettings", "version", "stats",
})
# Classes and services commonly named in --!strict annotations ("Unknown type 'Part'"). Types only:
# as a global (`RunService:Connect`, `Part.new()`) each is a real mistake and stays a finding.
_ROBLOX_CLASS_TYPES = frozenset({
    "Part", "MeshPart", "UnionOperation", "TrussPart", "WedgePart", "SpawnLocation", "Seat",
    "VehicleSeat", "Terrain", "PVInstance", "Folder", "Configuration", "Script", "LocalScript",
    "ModuleScript", "LuaSourceContainer", "RemoteEvent", "RemoteFunction",
    "UnreliableRemoteEvent", "BindableEvent", "BindableFunction", "Tool", "Accessory",
    "Attachment", "Weld", "WeldConstraint", "Motor6D", "Constraint", "AlignPosition",
    "AlignOrientation", "LinearVelocity", "AngularVelocity", "Sound", "SoundGroup",
    "ParticleEmitter", "Beam", "Trail", "Light", "PointLight", "SpotLight", "SurfaceLight",
    "Decal", "Texture", "Highlight", "Camera", "Workspace", "DataModel", "ScreenGui",
    "BillboardGui", "SurfaceGui", "LayerCollector", "GuiBase2d", "GuiObject", "GuiButton",
    "Frame", "TextLabel", "TextButton", "TextBox", "ImageLabel", "ImageButton",
    "ScrollingFrame", "CanvasGroup", "ViewportFrame", "UIListLayout", "UIGridLayout",
    "UICorner", "UIStroke", "UIPadding", "UIScale", "UIGradient", "UIAspectRatioConstraint",
    "ProximityPrompt", "ClickDetector", "Animator", "AnimationTrack", "AnimationController",
    "HumanoidDescription", "Backpack", "PlayerGui", "PlayerScripts", "Team", "Tween",
    "TweenBase", "InputObject", "Mouse", "PlayerMouse", "ObjectValue", "IntValue",
    "NumberValue", "StringValue", "BoolValue", "CFrameValue", "Vector3Value", "Color3Value",
    "Sky", "Atmosphere", "Path", "DataStore", "GlobalDataStore", "OrderedDataStore",
    "DataStoreKeyInfo", "MemoryStoreQueue", "MemoryStoreSortedMap",
    "ReplicatedStorage", "ReplicatedFirst", "ServerStorage", "ServerScriptService",
    "StarterGui", "StarterPack", "StarterPlayer", "Teams", "Lighting", "SoundService",
    "RunService", "UserInputService", "ContextActionService", "TweenService",
    "DataStoreService", "MemoryStoreService", "MessagingService", "HttpService",
    "CollectionService", "PathfindingService", "PhysicsService", "MarketplaceService",
    "TeleportService", "BadgeService", "GroupService", "TextChatService", "TextService",
    "GuiService", "ContentProvider", "InsertService", "Debris", "ProximityPromptService",
    "LocalizationService", "SocialService", "PolicyService", "AssetService",
    "AvatarEditorService", "HapticService", "VRService",
})


def _engine_symbol(message: str) -> bool:
    """True for an "Unknown global/type" error about a Roblox engine name."""
    symbol = _UNKNOWN_SYMBOL.match(message)
    return bool(symbol) and (symbol["name"] in _ROBLOX_SYMBOLS or (
        symbol["what"].lower() == "type" and symbol["name"] in _ROBLOX_CLASS_TYPES))


_notified: set[str] = set()
_notice_lock = threading.Lock()


def enabled(environ=None) -> bool:
    source = os.environ if environ is None else environ
    return source.get(ENV_VAR, "").strip().lower() == "on"


def locate_analyzer(*, tools_root: Path | None = None) -> str | None:
    """Prefer an existing pinned user-tools binary, then PATH; never download."""
    root = tools_root
    if root is None:
        value = os.environ.get(TOOLS_DIR_VAR, "").strip()
        root = Path(value) if value else None
    if root is not None:
        name = "luau-analyze.exe" if os.name == "nt" else "luau-analyze"
        candidate = Path(root) / ("luau-" + PINNED_VERSION) / name
        if candidate.is_file():
            return str(candidate)
    return shutil.which("luau-analyze")


def _notice_once(key: str, message: str) -> None:
    with _notice_lock:
        if key in _notified:
            return
        _notified.add(key)
    warnings.warn(message, RuntimeWarning, stacklevel=3)


def parse_diagnostics(output: str) -> list[Finding]:
    """Parse only diagnostics for STAR's staged Luau script."""
    findings: list[Finding] = []
    for raw in output.splitlines():
        match = _DIAGNOSTIC.fullmatch(raw)
        if match is None or Path(match["file"]).name != _STAGED_NAME:
            continue
        kind = match["kind"]
        message = match["message"]
        if kind == "TypeError" and _engine_symbol(message):
            continue
        if kind == "SyntaxError":
            fix, severity = "Repair Luau syntax before running the script.", "error"
        elif kind == "TypeError":
            fix, severity = "Review the type mismatch in Studio's Luau checker.", "warning"
        else:
            fix, severity = "Review this Luau lint diagnostic and confirm in Studio.", "review"
        clean = "".join(c if c.isprintable() else " " for c in message)[:220]
        findings.append(Finding(
            "luau-analyze-" + kind.lower(), int(match["line"]),
            kind + ": " + clean, fix, severity))
        if len(findings) >= MAX_FINDINGS:
            break
    return sorted(set(findings), key=lambda f: (f.line, f.rule_id, f.message))


def analyze(source: str, *, tools_root: Path | None = None) -> list[Finding]:
    """Check source staged temporarily, not in the owner workspace; never run Luau."""
    if not isinstance(source, str):
        raise TypeError("source must be str")
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        _notice_once("size", "Luau analyzer skipped oversized code; static checks remain available.")
        return []
    binary = locate_analyzer(tools_root=tools_root)
    if not binary:
        _notice_once("missing", "Luau analyzer is missing; using STAR's static checks only.")
        return []
    try:
        with tempfile.TemporaryDirectory(prefix="star-luau-check-") as temporary:
            # Luau 0.691's stdin '-' path was silent in the pinned CI smoke.
            # Stage source in an isolated directory to force file analysis.
            (Path(temporary) / _STAGED_NAME).write_text(source, encoding="utf-8")
            # Preserve OS runtime only, not provider credentials or custom keys.
            environment = {"PATH": os.environ.get("PATH", ""),
                           "HOME": temporary, "USERPROFILE": temporary,
                           "TEMP": temporary, "TMP": temporary}
            for name in ("SYSTEMROOT", "WINDIR"):
                if name in os.environ:
                    environment[name] = os.environ[name]
            result = subprocess.run(
                [binary, "--mode=strict", _STAGED_NAME],
                cwd=temporary, env=environment,
                capture_output=True, encoding="utf-8", errors="replace",
                text=True, check=False, timeout=TIMEOUT_SECONDS)
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        _notice_once("failure", "Luau analyzer could not run; using STAR's static checks only.")
        return []
    output = result.stderr
    if (result.returncode not in (0, 1) or not isinstance(output, str)
            or not isinstance(result.stdout, str)
            or len(output.encode("utf-8")) > MAX_OUTPUT_BYTES
            or len(result.stdout.encode("utf-8")) > MAX_OUTPUT_BYTES):
        _notice_once("failure", "Luau analyzer returned an invalid result; using static checks only.")
        return []
    findings = parse_diagnostics(output)
    if result.returncode != 0 and not findings:
        # Unknown engine globals are intentionally suppressed; otherwise warn
        # that a failure could not be interpreted rather than alleging success.
        if not output.strip() or not all(
            (m := _DIAGNOSTIC.fullmatch(line)) and m["kind"] == "TypeError"
            and _engine_symbol(m["message"])
            for line in output.splitlines() if line.strip()
        ):
            _notice_once("unparsed", "Luau analyzer diagnostics were not understood; static checks remain available.")
    return findings
