"""Offline, advisory checklist for explicitly requested Roblox features.

These deterministic hints never certify behavior, and nothing imports them into
the app's answer path. Unknown requested features are deliberately not guessed.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from .eval_checks import extract_luau_blocks, strip_luau


@dataclass(frozen=True)
class Requirement:
    key: str
    label: str


@dataclass(frozen=True)
class FeatureCheck:
    requirement: Requirement
    keyword_found: bool
    api_found: bool

    @property
    def present(self) -> bool:
        """Evidence only, never proof that the feature behaves correctly."""
        return self.keyword_found and self.api_found


@dataclass(frozen=True)
class _Rule:
    key: str
    label: str
    request: str
    keyword: str
    api: str


# Intentionally bounded to concrete beginner requests. Any one API match is
# weak evidence, not a substitute for compile, Luau assertions or Studio tests.
_RULES = (
    _Rule("shop", "shop", r"\bshop\b|\bstore menu\b|\bbuy menu\b",
          r"\b(?:shop|purchase|buy)\w*\b",
          r"\b(?:OnServerEvent|MarketplaceService|PromptProductPurchase)\b"),
    _Rule("timer", "timer", r"\btimer\b|\bcountdown\b",
          r"\b(?:timer|countdown|remaining)\b",
          r"\b(?:task\.wait|os\.clock|time)\s*\("),
    _Rule("leaderboard", "leaderboard", r"\bleaderboard\b|\bleaderstats\b|\bscoreboard\b",
          r"\b(?:leaderstats|leaderboard|scoreboard)\b",
          r"Instance\.new\s*\(\s*['\"](?:IntValue|NumberValue|Folder)['\"]\s*\)"),
    _Rule("checkpoint", "checkpoints", r"\bcheckpoints?\b|\brespawn points?\b",
          r"\b(?:checkpoint|respawn)\w*\b",
          r"\b(?:Touched|RespawnLocation|CharacterAdded)\b"),
    _Rule("door", "prompt-operated door", r"\bdoors?\b",
          r"\bdoor\w*\b", r"\b(?:ProximityPrompt|TweenService)\b"),
    _Rule("coin", "coin pickup", r"\bcoins?\b|\bcollectible currency\b",
          r"\bcoin\w*\b", r"\b(?:Touched|IntValue|NumberValue)\b"),
    _Rule("day-night", "day and night cycle", r"\bday\s*(?:and|\/|-)\s*night\b|\bnight cycle\b",
          r"\b(?:day|night|lighting|clocktime)\b",
          r"\b(?:Lighting|ClockTime|TimeOfDay)\b"),
    _Rule("speed", "speed boost", r"\bspeed boost\b|\bspeed pad\b|\bsprint\b",
          r"\b(?:speed|boost|sprint)\w*\b", r"\b(?:WalkSpeed|Humanoid)\b"),
    _Rule("teams", "team spawns", r"\bteam spawns?\b|\bteams?\b",
          r"\bteam\w*\b", r"\b(?:TeamColor|SpawnLocation|Teams)\b"),
    _Rule("platform", "moving platform", r"\bmoving platforms?\b|\btween(?:ed)? platforms?\b",
          r"\bplatform\w*\b", r"\b(?:TweenService|TweenInfo)\b"),
    _Rule("sound", "touch sound", r"\bsounds?\b|\bsfx\b",
          r"\b(?:sound|sfx)\w*\b",
          r"\b(?:Sound|Touched|Play)\b"),
)
_BY_KEY = {rule.key: rule for rule in _RULES}
_NEGATED = re.compile(r"\b(?:no|without|exclude|omit|don't add|do not add)\s+(?:an?\s+|the\s+)?$", re.I)
_NEGATIVE_GROUP = re.compile(
    r"\b(?:no|without|exclude|omit|don't add|do not add)\s+"
    r"(?:(?:an?\s+|the\s+)?[\w-]+\s+(?:and|or)\s+){1,3}(?:an?\s+|the\s+)?$", re.I
)


def required_features(request: str) -> tuple[Requirement, ...]:
    """Return recognized feature requirements in mention order, deduplicated.

    This extracts independent coordinated features such as 'a shop and a timer
    and a leaderboard' without pretending to understand arbitrary intent.
    """
    if not isinstance(request, str):
        raise TypeError("request must be a string")
    found: list[tuple[int, Requirement]] = []
    for rule in _RULES:
        for match in re.finditer(rule.request, request, re.I):
            prefix = request[max(0, match.start() - 80):match.start()]
            if _NEGATED.search(prefix) or _NEGATIVE_GROUP.search(prefix):
                continue
            found.append((match.start(), Requirement(rule.key, rule.label)))
            break
    return tuple(requirement for _, requirement in sorted(found, key=lambda pair: pair[0]))


def check_answer(answer: str, requirements: tuple[Requirement, ...]) -> tuple[FeatureCheck, ...]:
    """Check *code*, not prose/comments, for BOTH feature words and API hints.

    No result certifies behavior or proves the feature works in Roblox Studio.
    An unrecognized requirement is an error rather than an implicit pass.
    """
    if not isinstance(answer, str):
        raise TypeError("answer must be a string")
    blocks = extract_luau_blocks(answer)
    if blocks:
        code = "\n".join(blocks)
    elif re.search(r"\b(?:local|function|Instance|game|task)\b", answer):
        code = answer  # raw Luau snippets are permitted, but never prose alone
    else:
        code = ""
    clean = strip_luau(code)[:60_000]
    verdicts = []
    for requirement in requirements:
        try:
            rule = _BY_KEY[requirement.key]
        except KeyError as exc:
            raise ValueError("unsupported feature key: " + requirement.key) from exc
        verdicts.append(FeatureCheck(
            requirement=Requirement(rule.key, rule.label),
            keyword_found=bool(re.search(rule.keyword, clean, re.I)),
            api_found=bool(re.search(rule.api, clean, re.I)),
        ))
    return tuple(verdicts)
