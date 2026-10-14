"""Which systems-language skill pack a prompt is about (lang-c, lang-cpp, lang-rust, ... in this folder).

The packs themselves are ordinary Agent Skills: STAR's agent can list and load them with star_skill_catalog and
star_skill_load. They are not in skill_packs.TRIGGERS, so automatic selection never adds them and Roblox prompts are
unchanged. This module holds the routing data that automatic selection would need: CONTEXTS maps each pack to a
regex that recognises the LANGUAGE ITSELF (not ordinary English or Roblox/Luau prompts). Wiring it into
skill_packs.select, and enabling any pack by default, must wait for the evaluation gate (docs/evals.md) on
evals/languages/golden-tasks-systems-v1.json.
"""
from __future__ import annotations

import re

_I = re.IGNORECASE

CONTEXTS: dict[str, re.Pattern] = {
    # Case-sensitive "C" with explicit cues, so "plan C" or "C++"/"C#" do not count.
    "lang-c": re.compile(
        r"\bC(?:89|99|11|17|23|2y)\b|\b(?:[Ii]n|[Ww]ith|[Uu]sing|plain|ANSI|ISO) C\b(?![+#])|\bC (?:code|program|function|library|"
        r"header|compiler|string)s?\b|\bgcc\b|\bmalloc\b|\brealloc\b|<stdio\.h>|<stdlib\.h>|\b\w+\.c\b|\bsegfault\w*"),
    "lang-cpp": re.compile(
        r"(?<![\w+])C\+\+(?:\d\d)?|\bcpp\b|\b\w+\.(?:cpp|hpp|cc|hh)\b|\bg\+\+|\bclang\+\+|\bMSVC\b|\bCMakeLists\b|"
        r"\bstd::(?:vector|unique_ptr|shared_ptr|string_view|map|unordered_map|optional|expected)\b|\bLNK20\d\d\b"),
    "lang-rust": re.compile(
        r"\b(?:Rust|rustc|rustup|rustlang|Cargo\.toml|crates\.io|borrow[- ]checker|E0\d{3})\b|\bcargo (?:build|run|test|"
        r"check|add|new|clippy|fmt)\b|\b(?:Bevy|tokio)\b"),
    "lang-zig": re.compile(r"\b(?:zig|ziglang|build\.zig(?:\.zon)?)\b", _I),
    # Case-sensitive "Go" with explicit cues, so "go ahead" does not count.
    "lang-go": re.compile(
        r"\b(?:golang|goroutines?|go\.mod|go\.sum|gofmt|govulncheck|Ebitengine)\b|\bgo (?:build|run|test|vet|mod|get|"
        r"fix|work)\b|\b(?:[Ii]n|[Ww]ith|[Uu]sing|written in) Go\b|\bGo (?:code|program|module|service|server|1\.\d+)\b"),
    "lang-csharp": re.compile(
        r"(?<![\w+])C#|\bcsharp\b|\bdotnet\b|(?<!\w)\.NET\b|\b\w+\.csproj\b|\bCS\d{4}\b|\bMonoBehaviour\b|\bNuGet\b|"
        r"\bASP\.NET\b", _I),
    "lang-java": re.compile(
        r"\bJava\b(?!\s*Script)|\bjavac\b|\bJDK\s?\d*\b|\bJVM\b|\bpom\.xml\b|\bMaven\b|\bSpring Boot\b|\bJUnit\b|"
        r"\b(?:ConcurrentModificationException|ClassCastException|UnsupportedClassVersionError)\b", _I),
    "lang-kotlin": re.compile(r"\b(?:kotlin|kotlinx|kotlinc|build\.gradle\.kts|Jetpack Compose|coroutineScope)\b", _I),
    "lang-swift": re.compile(r"\b(?:Swift(?:UI)?|swiftc|Xcode|Package\.swift|SpriteKit|SwiftPM|RealityKit)\b"),
}


def languages_named(prompt) -> list[str]:
    """Pack names whose language the prompt names, most distinct mentions first (ties keep CONTEXTS order)."""
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 20_000:
        return []
    scored = []
    for order, (name, pattern) in enumerate(CONTEXTS.items()):
        hits = {m.group(0).lower() for m in pattern.finditer(prompt)}
        if hits:
            scored.append((-len(hits), order, name))
    return [name for _, _, name in sorted(scored)]
