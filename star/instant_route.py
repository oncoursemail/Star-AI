"""Conservative, side-effect-free eligibility for on-device instant answers.

This policy never starts, lists, downloads or swaps models. Callers must separately
prove that an already-loaded model is reachable on the loopback interface.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .brain_router import _CODING, _DEEP, deep_request, grounding_plan, is_roblox_task


_COMPLEX = re.compile(
    r"\b(?:explain in detail|step.by.step|current|latest|today|yesterday|"
    r"search|look up|cite|source|documentation|docs|research|compare|"
    r"write|build|create|make|generate|edit|analy[sz]e)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class InstantDecision:
    use_local: bool
    reason: str


def decide_instant_route(
    prompt: str, *, mode: str, provider: str, enabled: bool,
    installed: bool, loaded: bool, model: str,
    attachments: int = 0, tools: bool = False, research: bool = False,
    documentation: bool = False, deep: bool = False,
) -> InstantDecision:
    """Fail closed to the existing route whenever an input is uncertain."""
    if provider != "star_server":
        return InstantDecision(False, "provider")
    if (any(type(value) is not bool for value in (enabled, installed, loaded, tools,
                                                  research, documentation, deep))
            or type(attachments) is not int or attachments < 0
            or not isinstance(model, str) or not model.strip()):
        return InstantDecision(False, "invalid-input")
    if not enabled or not installed or not loaded:
        return InstantDecision(False, "not-ready")
    if mode not in ("fast", "auto"):
        return InstantDecision(False, "mode")
    if attachments or tools or research or documentation or deep:
        return InstantDecision(False, "needs-capability")
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 180:
        return InstantDecision(False, "length")
    if len(prompt.split()) > 30 or "\n" in prompt or "`" in prompt:
        return InstantDecision(False, "complex")
    requested_deep, _ = deep_request(prompt)
    if requested_deep or is_roblox_task(prompt) or _CODING.search(prompt) or _DEEP.search(prompt) or _COMPLEX.search(prompt):
        return InstantDecision(False, "complex")
    if grounding_plan(prompt, mode=mode).retrieve != "none":
        return InstantDecision(False, "documentation")
    return InstantDecision(True, "instant")
