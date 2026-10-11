"""Roblox skill packs: short guidance distilled from the official documentation.

A pack is an ordinary Agent Skill (a folder with SKILL.md and references/, the format read by
`star.agent_skills`), shipped inside the application. Unlike a skill the model has to ask for, a pack
is chosen here, in code, from the user's words: it is added to the turn only when the prompt is a
Roblox question AND names the pack's topic, so unrelated prompts are byte-for-byte unchanged.

Where it goes: `desktop_core.run_task` appends the rendered block to `turn_sections`, which
`star.agent.volatile_context` puts after the user's own words. It never enters the system message,
which stays byte-stable for the model server's prompt cache.

Cost: the text is read by the model on every turn it is added. Each pack is about 240 tokens (measured
with the server's tokenizer) and only the best-matching pack is added (MAX_PACKS_PER_TURN = 1), so the
first token is delayed by about 4 seconds at the server's prompt-reading speed of roughly 65 tokens per
second, and only for matching prompts.

Whether a pack is on is decided by evidence, not by hope: a pack is enabled by default (DEFAULT_ENABLED)
only after the evaluation gate (docs/evals.md) showed that it does not lower the golden-task score.
`STAR_SKILL_PACKS` overrides it: `off`, `all`, or a comma list of pack names.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
import re

from ..agent_skills import _frontmatter

PACKS_DIR = Path(__file__).resolve().parent
ENV_VAR = "STAR_SKILL_PACKS"
MAX_BODY_CHARS = 6400
MAX_PACKS_PER_TURN = 1
MAX_BLOCK_CHARS = 6500
BLOCK_HEADING = "ROBLOX SKILL PACKS (guidance from STAR, distilled from the official documentation; not part of the request)"

# Enabled by default: only packs the gate allowed with at least one measured improvement (docs/evals.md,
# "Measured results"). The others stay shipped and can be switched on with STAR_SKILL_PACKS, but were either
# blocked (a confirmed regression), inconclusive (the no-pack arm flips on the same task) or showed no gain.
DEFAULT_ENABLED: tuple[str, ...] = (
    "roblox-secure-remotes",
    "roblox-animation-craft",
    "roblox-vfx",
    "roblox-building-layout",
    "eng-verify-before-done",
)

# The prompt must read as a Roblox question at all ...
_ROBLOX_CONTEXT = re.compile(
    r"\b(?:roblox|luau|studio|workspace|LocalScript|ModuleScript|ServerScriptService|ServerStorage|ReplicatedStorage|"
    r"StarterGui|StarterPlayer\w*|StarterCharacterScripts|PlayerGui|ScreenGui|Instance\.new|game:GetService|"
    r"Humanoid|RemoteEvent|RemoteFunction|DataStore\w*|OnServerEvent|BindToClose|R6|R15)\b", re.IGNORECASE)

# ... and name the pack's topic.
TRIGGERS: dict[str, re.Pattern] = {
    "roblox-ui-layout": re.compile(
        r"\b(?:ScreenGui|SurfaceGui|BillboardGui|UDim2|UIListLayout|UIGridLayout|UIScale|UIPadding|UICorner|UIStroke|"
        r"UIAspectRatioConstraint|UISizeConstraint|UITextSizeConstraint|ScrollingFrame|TextButton|TextLabel|TextBox|"
        r"ImageLabel|ImageButton|PlayerGui|StarterGui|HUD|GUI|UI|menu|nameplate|safe area|notch|TweenService|"
        r"AutomaticCanvasSize|ViewportSize)\b", re.IGNORECASE),
    "roblox-secure-remotes": re.compile(
        r"\b(?:RemoteEvent|RemoteFunction|UnreliableRemoteEvent|OnServerEvent|OnClientEvent|FireServer|FireClient|"
        r"FireAllClients|InvokeServer|InvokeClient|exploit\w*|anti-?cheat|cheat\w*|ProcessReceipt|developer product|"
        r"validate|server-authoritative|never trust)\b", re.IGNORECASE),
    "roblox-datastore-safety": re.compile(
        r"\b(?:DataStore\w*|data ?stores?|UpdateAsync|GetAsync|SetAsync|BindToClose|ProcessReceipt|developer product|"
        r"save (?:the )?(?:player|data)|player data|autosave|session lock\w*)\b", re.IGNORECASE),
    "roblox-animation-tools": re.compile(
        r"\b(?:Animator|AnimationTrack|LoadAnimation|animations?|animate|R6|R15|RigType|Motor6D|Tool|Grip\w*|Equipped|"
        r"Unequipped|Handle|attachments?|rigs?|AnimationId|KeyframeMarker|marker)\b", re.IGNORECASE),
    "roblox-performance-streaming": re.compile(
        r"\b(?:performance|optimi[sz]\w*|lag\w*|frame ?rate|FPS|MicroProfiler|StreamingEnabled|streaming|RenderStepped|"
        r"Heartbeat|polling|every frame|object pool\w*|pooling|Debris|garbage|ModelStreamingMode)\b", re.IGNORECASE),
    # Creation packs (animation craft, effects, building, UI looks).
    "roblox-animation-craft": re.compile(
        r"\b(?:anticipation|follow-?through|easing|eased?|wind-?up|frame data|startup|recovery|cancel ?window|combo|move-?set|"
        r"IKControl|inverse kinematics|damped|damping|spring|secondary motion|procedural|AdjustWeight|AdjustSpeed|cross-?fade|"
        r"blend\w*|GetMarkerReachedSignal|animation events?|markers?|hit window|AnimationPriority|keyframes?|overshoot\w*|"
        r"interpolat\w*)\b", re.IGNORECASE),
    "roblox-vfx": re.compile(
        r"\b(?:ParticleEmitter|particles?|Beam|Trail|Attachment[01]|Emit|LightEmission|NumberSequence|ColorSequence|VFX|"
        r"visual effects?|particle effects?|emitters?|sparks?|burst|shockwave|embers?|smoke|muzzle flash|explosion|laser)\b",
        re.IGNORECASE),
    "roblox-building-layout": re.compile(
        r"\b(?:grid|snap\w*|studs?|modular|level design|level layout|doorway|Atmosphere|ClockTime|Lighting|OutdoorAmbient|"
        r"BloomEffect|ColorCorrectionEffect|SunRaysEffect|PivotTo|Terrain|walls?|floors?|rooms?|ceilings?|corridors?|obby|"
        r"lobby)\b", re.IGNORECASE),
    "roblox-ui-styles": re.compile(
        r"\b(?:theme[sd]?|style[sd]?|styling|palette|glass|neon|gradient|UIGradient|UIStroke|UICorner|hover|dark mode|contrast|"
        r"readable|design system|flat|cartoon\w*|chunky|skeuomorphic|look and feel)\b", re.IGNORECASE),
    # Engineering-method packs adapted from MIT-licensed collections (see THIRD_PARTY_NOTICES.md).
    "game-obby": re.compile(r"\b(?:obby|checkpoint|checkpoints|kill brick|stage progression|obstacle course)\b", re.IGNORECASE),
    "game-tycoon": re.compile(r"\b(?:tycoon|dropper|droppers|collector|collectors|purchase button|factory plot)\b", re.IGNORECASE),
    "game-simulator": re.compile(r"\b(?:simulator|clicker|rebirth|rebirths|leaderstats|upgrade loop)\b", re.IGNORECASE),
    "game-rounds": re.compile(r"\b(?:rounds|round-based|intermission|round state|round timer|round winner|minigame)\b", re.IGNORECASE),
    "game-inventory": re.compile(r"\b(?:inventory|equip|unequip|item pickup|item ownership|backpack)\b", re.IGNORECASE),
    "game-npc-quests": re.compile(r"\b(?:NPC quest|NPC quests|quest|quests|quest reward|quest dialogue|dialogue)\b", re.IGNORECASE),
    "eng-debugging": re.compile(
        r"\b(?:debug\w*|bugs?|root cause|fix(?:es)?|stack trace|errors?|crash\w*|broken|fails|failing|attempt to \w+|regression)\b",
        re.IGNORECASE),
    "eng-test-first": re.compile(
        r"\b(?:test-?first|TDD|tests? first|unit tests?|write (?:the )?tests?|red-?green|failing tests?|regression tests?|"
        r"asserts?)\b", re.IGNORECASE),
    "eng-verify-before-done": re.compile(
        r"\b(?:verif\w*|double-?check\w*|how (?:do|can) I (?:know|confirm|be sure)|(?:what|how) you (?:checked|tested)|"
        r"make sure (?:it|this) works|confirm (?:that|it))\b", re.IGNORECASE),
}


@dataclass(frozen=True)
class Pack:
    name: str
    description: str
    body: str
    file: Path


@lru_cache(maxsize=1)
def available() -> tuple[Pack, ...]:
    """Every pack shipped in this folder, in the order of TRIGGERS. A broken pack is skipped, never fatal."""
    found = []
    for name in TRIGGERS:
        file = PACKS_DIR / name / "SKILL.md"
        try:
            fields, body = _frontmatter(file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        if fields.get("name") != name or not fields.get("description"):
            continue
        found.append(Pack(name, fields["description"], body.strip(), file))
    return tuple(found)


def enabled_names(environ=None, *, home=None) -> frozenset[str]:
    """Pack names that may be used now: STAR_SKILL_PACKS, else DEFAULT_ENABLED."""
    raw = (os.environ if environ is None else environ).get(ENV_VAR, "").strip().lower()
    known = {p.name for p in available()}
    if not raw:
        defaults = frozenset(known & set(DEFAULT_ENABLED))
        if home is not None:
            from ..promoter import enabled_skill_packs
            return enabled_skill_packs(home, defaults)
        return defaults
    if raw in {"off", "none", "no", "false", "0"}:
        return frozenset()
    if raw in {"all", "on", "true", "1"}:
        return frozenset(known)
    return frozenset(known & {part.strip() for part in raw.split(",")})


def select(prompt, *, enabled=None, limit: int = MAX_PACKS_PER_TURN, home=None) -> list[Pack]:
    """The packs for this prompt, best match first. Empty for anything that is not a Roblox question."""
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20_000:
        return []
    allowed = enabled_names(home=home) if enabled is None else frozenset(enabled)
    if not allowed or not _ROBLOX_CONTEXT.search(prompt):
        return []
    scored = []
    for order, pack in enumerate(available()):
        if pack.name in allowed:
            hits = {m.group(0).lower() for m in TRIGGERS[pack.name].finditer(prompt)}
            # One generic word ("UI", "Tool", "validate") is not enough to spend the reader's time.
            if len(hits) >= 2 or any(len(h) > 6 for h in hits):
                scored.append((-len(hits), order, pack))
    return [pack for _, _, pack in sorted(scored)[:max(0, limit)]]


def render(packs) -> str:
    """The text added to the turn under BLOCK_HEADING, '' when no pack applies. Bounded by MAX_BLOCK_CHARS."""
    packs = list(packs)
    if not packs:
        return ""
    text = "\n\n".join(p.body for p in packs)
    return text[:MAX_BLOCK_CHARS].rstrip() + "\n"


def matching_names(prompt, *, enabled=None) -> list[str]:
    return [p.name for p in select(prompt, enabled=enabled)]
