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
    )
