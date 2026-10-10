"""Deterministic, zero-extra-inference STAR model routing.

The owner must explicitly configure every alternative model ID. All routes use the
SAME selected provider/endpoint: routing never transfers private prompts to cloud.
A single-model llama-server remains fully supported when aliases are left blank.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .providers import provider_kind


_ROBLOX = re.compile(r"\b(?:roblox|luau|rojo|r6|r15|studio|ugc)\b", re.IGNORECASE)
_DEEP = re.compile(
    r"\b(?:architect(?:ure)?|debug(?:ging)?|fix|implement|refactor|"
    r"design|optimi[sz](?:e|ation)|benchmark|security|audit|"
    r"reason(?:ing)?|investigat(?:e|ion)|train(?:ing)?|complex|"
    r"compare|analyse|analyze|plan|code|program(?:ming)?|"
    r"animation|animate|model(?:ling|ing)|research)\b",
    re.IGNORECASE,
)
_MODEL_ID = re.compile(r"^[^\s\x00-\x1f\x7f]{1,180}$")

ROBLOX_QUALITY_NOTES = (
    "\n\nROBLOX QUALITY CHECKLIST (requirements, not evidence of completion): "
    "read the actual Studio hierarchy and references first; prefer native responsive "
    "UI with verified alignment and reduced-motion behavior; use --!strict Luau, "
    "server-owned game state and validated RemoteEvents; correctly rig and keyframe "
    "animations; reuse optimized meshes and texture budgets; playtest in an "
    "unpublished place at desktop and mobile resolutions. "
    "Never claim a test, screenshot check, Studio edit, or animation preview "
    "happened unless a tool returned that evidence."
)


# --- Grounding in the official documentation (STAR Knowledge) -----------------------------
# Stricter than _ROBLOX on purpose: every retrieved passage costs seconds of prompt time on a
# CPU server, so "studio" or "ugc" alone must not trigger a documentation search.
_ROBLOX_DEV = re.compile(
    r"\b(?:roblox|luau|rojo|devforum|"
    r"remote(?:event|function)s?|bindable(?:event|function)s?|(?:ordered)?datastores?|datastoreservice|"
    r"memorystore(?:service)?|tweenservice|runservice|userinputservice|contextactionservice|"
    r"replicatedstorage|replicatedfirst|serverscriptservice|serverstorage|startergui|starterplayer|"
    r"starterpack|playergui|humanoid(?:rootpart)?|(?:local|module|server)\s?scripts?|"
    r"(?:screen|surface|billboard)gui|ui(?:list|grid|page|table)layout|uiaspectratioconstraint|"
    r"text(?:label|button|box)|image(?:label|button)|scrollingframe|proximityprompt|clickdetector|"
    r"pathfindingservice|collectionservice|marketplaceservice|teleportservice|messagingservice|"
    r"httpservice|soundservice|physicsservice|textchatservice|basepart|meshpart|cframe|vector3|udim2|"
    r"tweeninfo|raycast(?:params)?|waitforchild|findfirstchild|getservice|leaderstats|"
    r"game\s?pass(?:es)?|developer\s+products?|animationtrack|animator|character(?:added|appearance)|"
    r"playeradded|playerremoving|r6|r15)\b|\binstance\.new\b|\bgame:|\bworkspace[.:]|\benum\.[a-z]",
    re.IGNORECASE,
)
# `TweenService:Create`, `Humanoid.WalkSpeed`, `Enum.EasingStyle`: an exact engine name.
_API_SYMBOL = re.compile(r"\b(?:Enum\.[A-Z][A-Za-z0-9]+|[A-Z][A-Za-z0-9]{2,40}[.:][A-Z][A-Za-z0-9]{1,48})\b")
_WANTS_CODE = re.compile(
    r"\b(?:write|make|create|build|fix|refactor|convert|implement|script|code|add|generate|rewrite|debug)\b|```",
    re.IGNORECASE,
)
# Public game statistics, not development: the documentation cannot answer these.
_GAME_STATS = re.compile(
    r"\b(?:how\s+many\s+(?:players|visits)|player\s+count|most\s+popular|top\s+games?|trending|"
    r"concurrent\s+players|visits|favorites|universe\s+id)\b|roblox\.com/games/",
    re.IGNORECASE,
)
_TRIVIAL = re.compile(
    r"^\W*(?:hi|hello|hey|yo|thanks?(?:\s+you)?|thx|ty|ok(?:ay)?|cool|nice|great|good\s+(?:morning|night)|"
    r"bye|yes|no|sure|got\s+it)\b[\s\W]*$",
    re.IGNORECASE,
)
_REFERENTIAL = re.compile(
    r"\b(?:it|this|that|same|again|those|these|them|instead)\b|^\s*(?:and|but|what about|how about)\b",
    re.IGNORECASE)
# (passages, character budget) per chat mode: about 500, 1,200 and 1,800 prompt tokens.
GROUNDING_BUDGET = {"fast": (2, 1700), "auto": (4, 4080), "agent": (6, 6120)}


@dataclass(frozen=True)
class GroundingPlan:
    """What to fetch from the official documentation before the model is called.

    A plan is a decision about the prompt only. Whether the knowledge service is
    configured or reachable is decided later; an unavailable service is never an error.
    """
    retrieve: str = "none"            # "none" | "docs" (search) | "api" (exact engine name first)
    passages: int = 0
    max_chars: int = 0
    check_luau: bool = False          # statically check fenced Luau in the answer
    symbols: tuple[str, ...] = ()     # exact engine names found in the prompt
    reasons: tuple[str, ...] = ()


NO_GROUNDING = GroundingPlan()


def is_roblox_dev_prompt(prompt: str) -> bool:
    """A Roblox or Luau *development* question (strict; see _ROBLOX_DEV)."""
    return isinstance(prompt, str) and bool(
        _ROBLOX_DEV.search(prompt) or (_API_SYMBOL.search(prompt) and _ROBLOX.search(prompt)))


def grounding_plan(prompt: str, *, mode: str = "auto", image_count: int = 0, research: bool = False,
                   roblox_context: bool = False) -> GroundingPlan:
    """Deterministic: should this prompt be answered from the official documentation?

    First match wins. No model call, no network, no clock.
    """
    if mode not in GROUNDING_BUDGET or not isinstance(prompt, str) or not prompt.strip():
        return NO_GROUNDING
    text = prompt.strip()
    if _TRIVIAL.match(text):
        return GroundingPlan(reasons=("greeting or acknowledgement",))
    if not (is_roblox_dev_prompt(text) or roblox_context):
        return GroundingPlan(reasons=("not a Roblox or Luau development question",))
    if _GAME_STATS.search(text) and not _WANTS_CODE.search(text):
        return GroundingPlan(reasons=("public game statistics, not documentation",))
    passages, max_chars = GROUNDING_BUDGET[mode]
    symbols = tuple(dict.fromkeys(_API_SYMBOL.findall(text)))[:3]
    wants_code = bool(_WANTS_CODE.search(_API_SYMBOL.sub(" ", text)))   # "Create" in TweenService:Create is a name
    reasons = ["Roblox or Luau development question", f"{mode} mode budget"]
    retrieve = "docs"
    if symbols and not wants_code:
        # An exact engine name with a factual question: its reference entry is enough.
        retrieve = "api"
        passages = 1 if mode == "fast" else 2
        max_chars = min(max_chars, 1700 if mode == "fast" else 2400)
        reasons.append("names an exact engine API")
    if image_count or research:
        # The picture or the web results already take prompt time: keep the docs short.
        passages = min(passages, 2)
        max_chars = min(max_chars, 2040)
        reasons.append("reduced: images or web results are also in the prompt")
    return GroundingPlan(retrieve=retrieve, passages=passages, max_chars=max_chars, check_luau=True,
                         symbols=symbols, reasons=tuple(reasons))


def followup_grounding(prompt: str, prior_user_turns: list[str] | None, *, mode: str = "auto"
                       ) -> tuple[GroundingPlan, str]:
    """A short referential follow-up ("and how do I reverse it?") to a Roblox question.

    Returns (plan, search query). The query is the earlier Roblox turn plus the new one:
    string concatenation, not a model call. (NO_GROUNDING, "") when this is not a follow-up.
    """
    if (not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 160
            or _TRIVIAL.match(prompt.strip()) or not _REFERENTIAL.search(prompt)):
        return NO_GROUNDING, ""
    for turn in reversed([t for t in (prior_user_turns or []) if isinstance(t, str)][-2:]):
        if is_roblox_dev_prompt(turn):
            plan = grounding_plan(turn + "\n" + prompt, mode=mode)
            if plan.retrieve == "none":
                return NO_GROUNDING, ""
            return (GroundingPlan(retrieve="docs", passages=plan.passages, max_chars=plan.max_chars,
                                  check_luau=True, reasons=("follow-up to a Roblox or Luau question",)),
                    (turn.strip()[:400] + " " + prompt.strip())[:600])
    return NO_GROUNDING, ""


def is_roblox_task(prompt: str) -> bool:
    """Detect Roblox-specific quality constraints even in explicit Agent mode."""
    return isinstance(prompt, str) and bool(_ROBLOX.search(prompt))


def validate_alias(value: str, *, field: str = "model") -> None:
    """Only ID strings, never arbitrary provider URLs, controls or shell fragments."""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a model ID string")
    if value and (value != value.strip() or not _MODEL_ID.fullmatch(value)
                  or value.lower().startswith(("http://", "https://", "file://"))):
        raise ValueError(f"{field} must be a single model ID without whitespace (max 180 characters)")


@dataclass(frozen=True)
class BrainRoute:
    profile: str
    model: str
    subagent_model: str
    quick: bool
    use_tools: bool
    response_tokens: int
    max_calls: int
    task_timeout: int
    description: str
    grounding: GroundingPlan = NO_GROUNDING


def select_route(settings, prompt: str, *, mode: str = "auto",
                 image_count: int = 0, research: bool = False,
                 project_tools: bool = False, roblox_context: bool = False) -> BrainRoute:
    """Select a capability profile, not a different privacy or permission policy.

    Auto complexity detection is deliberately cheap and deterministic. It is not
    a benchmark nor a guarantee that a selected model supports vision/tools.
    """
    if mode not in {"fast", "auto", "agent"}:
        raise ValueError("Unknown chat mode")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Prompt is empty")
    if not isinstance(image_count, int) or not 0 <= image_count <= 4:
        raise ValueError("0..4 images are allowed")
    if type(research) is not bool or type(project_tools) is not bool or type(roblox_context) is not bool:
        raise ValueError("Route flags must be boolean")

    configured = {}
    for name in ("model", "fast_model", "reasoning_model", "roblox_model", "vision_model"):
        value = getattr(settings, name, "")
        validate_alias(value, field=name)
        configured[name] = value
    roblox_topic = is_roblox_task(prompt) or roblox_context
    primary = configured["model"]
    if not primary:
        raise ValueError("Select a primary model first")

    if mode == "fast":
        profile = "vision" if image_count else "fast"
    elif mode == "agent":
        profile = "agent"
    elif image_count:
        profile = "vision"
    elif roblox_topic:
        profile = "roblox"
    elif research:
        profile = "research"
    elif project_tools or _DEEP.search(prompt):
        profile = "reasoning"
    else:
        profile = "fast"

    quick = mode == "fast" or profile == "fast"
    use_tools = mode == "agent" or (mode == "auto" and project_tools)
    # Image tasks must never silently fall through to a configured text-only
    # reasoning model. Use an explicit vision specialist or the primary model
    # that the owner chose for image-capable work.
    if image_count:
        chosen = configured["vision_model"] or primary
    elif profile == "fast":
        chosen = configured["fast_model"] or primary
    elif profile == "roblox":
        chosen = configured["roblox_model"] or configured["reasoning_model"] or primary
    elif profile == "vision":
        chosen = configured["vision_model"] or configured["reasoning_model"] or primary
    elif profile == "agent" and roblox_topic and configured["roblox_model"]:
        chosen = configured["roblox_model"]
    else:
        chosen = configured["reasoning_model"] or primary

    # A configured smaller model can draft subagent analyses while the main
    # reasoning model synthesizes; this never starts several models by itself.
    subagent = (configured["fast_model"] or chosen) if mode == "agent" else chosen
    kind = provider_kind(settings)
    # (agent, tools, quick answer, deep answer) whole-task budgets in seconds.
    if kind == "lan":
        # A CPU server streams a few tokens per second, so scale every budget
        # from the owner's per-request server timeout instead of GPU numbers.
        per_request = getattr(settings, "server_timeout", 600)
        per_request = per_request if type(per_request) is int and 30 <= per_request <= 1800 else 600
        budgets = tuple(min(3600, per_request * factor) for factor in (6, 3, 1, 2))
    elif kind == "local":
        budgets = (480, 180, 85, 180)
    else:
        budgets = (480, 180, 55, 100)
    if mode == "agent":
        max_calls = min(settings.max_calls, 20)
        timeout = budgets[0]
    elif use_tools:
        max_calls = min(settings.max_calls, 5)
        timeout = budgets[1]
    else:
        max_calls = 1
        timeout = budgets[2] if quick else budgets[3]

    return BrainRoute(
        profile=profile, model=chosen, subagent_model=subagent,
        quick=quick, use_tools=use_tools,
        response_tokens=650 if quick else 1600,
        max_calls=max_calls, task_timeout=timeout,
        description={
            "fast": "Fast answer", "reasoning": "Deeper reasoning",
            "roblox": "Roblox engineering", "vision": "Visual analysis",
            "research": "Source-grounded research", "agent": "Agent workflow",
        }[profile],
        grounding=grounding_plan(prompt, mode=mode, image_count=image_count, research=research,
                                 roblox_context=roblox_context),
    )
