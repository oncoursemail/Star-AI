"""WCAG 2.2 AA checks on actual STAR OLED desktop CSS rules and tokens.

CSS source (rather than a duplicated palette) is read on every test run.
Only functional control borders are treated as necessary 3:1 boundaries;
decorative panel dividers are not mistakenly asserted as user controls.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import pytest

from star.design_md import contrast_ratio, parse_color

CSS = Path(__file__).resolve().parents[1] / "frontend" / "src"
SHEETS = ("stellar-ui.css", "redesign.css", "settings-ui.css", "chat.css")
TOKEN_FILE = CSS / "tokens.css"


@dataclass(frozen=True)
class Pair:
    name: str
    sheet: str
    selector: str
    role: str
    foreground: str
    background: str
    backdrop: str = ""


# Exact foreground/background usage from shipped desktop selectors, not
# invented combinations. A backdrop is explicit when the CSS uses a wash.
PAIRS = [
    Pair("shell-body", "stellar-ui.css", ".shell", "text", "--star-body", "--star-bg", ""),
    Pair("rail-hover", "stellar-ui.css", ".rail-item:not(:disabled):hover", "text", "--star-text", "--star-surface-1", ""),
    Pair("rail-current", "stellar-ui.css", ".rail-item.is-current", "text", "--star-text", "--star-surface-2", ""),
    Pair("topbar-hover", "stellar-ui.css", ".bar-action[aria-pressed='true']", "text", "--star-text", "--star-surface-2", ""),
    Pair("search-field", "stellar-ui.css", ".shell .bar-find", "text", "--star-text", "--star-surface-1", ""),
    Pair("preview-ribbon", "stellar-ui.css", ".preview-ribbon", "text", "--star-muted", "--star-surface-1", ""),
    Pair("toast", "stellar-ui.css", ".shell .toast", "text", "--star-text", "--star-surface-3", ""),
    Pair("image-dialog", "stellar-ui.css", ".star-image-dialog", "text", "--star-muted", "--star-surface-1", ""),
    Pair("close-button", "stellar-ui.css", ".star-image-close", "text", "--star-text", "--star-surface-3", ""),
    Pair("primary-button", "stellar-ui.css", ".shell .primary-button", "text", "--star-on-gold", "--star-gold", ""),
    Pair("secondary-button", "stellar-ui.css", ".shell .secondary-button", "text", "--star-body", "--star-surface-2", ""),
    Pair("secondary-hover", "stellar-ui.css", ".shell .secondary-button:not(:disabled):hover", "text", "--star-text", "--star-surface-3", ""),
    Pair("tool-icon", "stellar-ui.css", ".shell .tool-icon", "text", "--star-gold-soft", "--star-surface-3", ""),
    Pair("tag", "stellar-ui.css", ".shell .tag", "text", "--star-muted", "--star-surface-2", ""),
    Pair("tag-success", "stellar-ui.css", ".shell .tag-green", "text", "--star-success", "--star-success-wash", "--star-surface-2"),
    Pair("tag-gold", "stellar-ui.css", ".shell .tag-gold", "text", "--star-gold", "--star-gold-wash", "--star-surface-2"),
    Pair("tag-error", "stellar-ui.css", ".shell .tag-red", "text", "--star-danger", "--star-danger-wash", "--star-surface-2"),
    Pair("workflow-picker", "stellar-ui.css", ".shell .workflow-picker", "text", "--star-body", "--star-surface-2", ""),
    Pair("health-result", "stellar-ui.css", ".shell .health-result", "text", "--star-body", "--star-success-wash", "--star-surface-2"),
    Pair("integrated-panel", "stellar-ui.css", ".shell .integrated-panel", "text", "--star-body", "--star-surface-1", ""),
    Pair("rename-field", "redesign.css", ".shell .rail-rename", "text", "--star-text", "--star-surface-2", ""),
    Pair("undo-toast", "redesign.css", ".shell .undo-toast", "text", "--star-body", "--star-surface-3", ""),
    Pair("undo-action", "redesign.css", ".undo-toast button", "text", "--star-gold", "--star-surface-1", ""),
    Pair("consent-dialog", "redesign.css", ".star-layer.consent-dialog", "text", "--star-body", "--star-surface-2", ""),
    Pair("consent-button", "redesign.css", ".consent-button", "text", "--star-text", "--star-surface-3", ""),
    Pair("consent-primary", "redesign.css", ".consent-button.is-primary", "text", "--star-on-gold", "--star-gold", ""),
    Pair("voice-chosen", "settings-ui.css", ".shell .voice-tag.is-chosen", "text", "--star-gold", "--star-gold-wash", "--star-surface-2"),
    Pair("studio-rule", "settings-ui.css", ".shell .studio-rule", "text", "--star-muted", "--star-surface-2", ""),
    Pair("dock-banner", "chat.css", ".dock-banner", "text", "--star-muted", "--star-surface-1", ""),
    Pair("chat-jump", "chat.css", ".chat-jump", "text", "--star-text", "--star-surface-3", ""),
    Pair("starter", "chat.css", ".starter", "text", "--star-muted", "--star-surface-1", ""),
    Pair("file-chip", "chat.css", ".cmp-file", "text", "--star-body", "--star-surface-3", ""),
    Pair("send", "chat.css", ".cmp-send", "text", "--star-on-gold", "--star-gold", ""),
    Pair("send-disabled", "chat.css", ".shell .cmp-send:disabled", "text", "--star-faint", "--star-surface-3", ""),
    Pair("message", "chat.css", ".msg-bubble", "text", "--star-text", "--star-surface-2", ""),
    Pair("correction-input", "chat.css", ".msg-correction textarea", "text", "--star-text", "--star-surface-1", ""),
    Pair("rail-search-border", "stellar-ui.css", ".rail-search", "border", "--star-stroke-control", "--star-surface-1", ""),
    Pair("topbar-search-border", "stellar-ui.css", ".shell .bar-find", "border", "--star-stroke-control", "--star-surface-1", ""),
    Pair("secondary-border", "stellar-ui.css", ".shell .secondary-button", "border", "--star-stroke-control", "--star-surface-2", ""),
    Pair("workflow-border", "stellar-ui.css", ".shell .workflow-picker", "border", "--star-stroke-control", "--star-surface-2", ""),
    Pair("composer-border", "chat.css", ".cmp", "border", "--star-stroke-control", "--star-surface-2", ""),
    Pair("correction-border", "chat.css", ".msg-correction textarea", "border", "--star-stroke-control", "--star-surface-1", ""),
    Pair("jump-border", "chat.css", ".chat-jump", "border", "--star-stroke-control", "--star-surface-3", ""),
    Pair("composer-focus", "chat.css", ".cmp:focus-within", "focus", "--star-stroke-focus", "--star-surface-2", ""),
    Pair("menu-focus", "redesign.css", ".shell .cmp-mode-pop .cmp-mode:focus-visible", "focus", "--star-stroke-focus", "--star-surface-3", ""),
    Pair("rename-gold-line", "redesign.css", ".shell .rail-rename", "border", "--star-gold-line", "--star-surface-2", ""),
]


def _token_values(css: str) -> dict[str, str]:
    return dict(re.findall(
        r"(--star-[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8}|rgba?\([^;]+?\))\s*;",
        re.sub(r"/\*.*?\*/", "", css, flags=re.S),
    ))


def _rule(sheet: str, selector: str) -> dict[str, str]:
    content = re.sub(r"/\*.*?\*/", "", (CSS / sheet).read_text(encoding="utf-8"), flags=re.S)
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", content):
        selectors = [part.strip() for part in match.group(1).split(",")]
        if selector not in selectors:
            continue
        return {key.strip(): value.strip() for key, value
                in re.findall(r"([\w-]+)\s*:\s*([^;]+);", match.group(2))}
    raise AssertionError(f"CSS selector removed: {sheet} {selector}")


def _opaque(value: str, behind: str | None = None) -> str:
    channels = parse_color(value)
    if channels is None:
        raise AssertionError(f"Unmeasurable colour: {value}")
    if channels[3] == 1:
        return value
    assert behind is not None, "An alpha colour needs a real opaque backdrop"
    backing = parse_color(behind)
    assert backing is not None and backing[3] == 1
    mixed = tuple(int(round(255 * (channels[i] * channels[3] +
                                   backing[i] * (1 - channels[3]))))
                  for i in range(3))
    return "#" + "".join(f"{component:02x}" for component in mixed)


def _ratio(pair: Pair, tokens: dict[str, str]) -> float:
    foreground, background = tokens[pair.foreground], tokens[pair.background]
    underneath = tokens[pair.backdrop] if pair.backdrop else None
    solid_background = _opaque(background, underneath)
    return contrast_ratio(_opaque(foreground, solid_background), solid_background)


@pytest.mark.parametrize("pair", PAIRS, ids=[p.name for p in PAIRS])
def test_desktop_colour_pair_meets_wcag_22_aa(pair: Pair):
    assert pair.sheet in SHEETS
    rule = _rule(pair.sheet, pair.selector)
    property_name = ("color" if pair.role == "text" else "border" if pair.role == "border"
                     else "box-shadow" if pair.name == "menu-focus" else "border-color")
    assert f"var({pair.foreground})" in rule[property_name], pair.name
    if pair.role == "text":
        assert f"var({pair.background})" in rule["background"], pair.name
    elif pair.role == "border":
        assert f"var({pair.background})" in rule["background"], pair.name
    else:
        assert "focus" in pair.selector
    tokens = _token_values(TOKEN_FILE.read_text(encoding="utf-8"))
    assert pair.foreground in tokens and pair.background in tokens
    measured = _ratio(pair, tokens)
    minimum = 4.5 if pair.role == "text" else 3.0
    assert measured + 1e-9 >= minimum, f"{pair.name}: {measured:.2f}:1 < {minimum}:1"


def test_source_palette_is_not_duplicated_and_has_one_shipped_dark_scheme():
    css = TOKEN_FILE.read_text(encoding="utf-8")
    assert ".shell,\n.star-layer" in css
    assert "@media (prefers-color-scheme: light)" not in css
    assert len(PAIRS) >= 25
    assert {pair.sheet for pair in PAIRS} == set(SHEETS)
    tokens = _token_values(css)
    assert len(tokens) == len(set(re.findall(
        r"(--star-[\w-]+)\s*:\s*(?:#|rgba?\()", css)))
    assert _ratio(next(p for p in PAIRS if p.name == "composer-focus"), tokens) >= 3


def test_composer_focus_edge_differs_from_its_resting_edge():
    """The composer hides the text-field ring and shows focus only on its edge (desktop-styles.test.ts),
    so the focused edge must stay clearly brighter than the resting control border, not the same colour."""
    tokens = _token_values(TOKEN_FILE.read_text(encoding="utf-8"))
    assert "var(--star-stroke-control)" in _rule("chat.css", ".cmp")["border"]
    assert "var(--star-stroke-focus)" in _rule("chat.css", ".cmp:focus-within")["border-color"]
    rest, focus = tokens["--star-stroke-control"], tokens["--star-stroke-focus"]
    assert rest.lower() != focus.lower()
    assert contrast_ratio(focus, rest) >= 2.0, f"focus edge only {contrast_ratio(focus, rest):.2f}:1 against rest"


def test_contrast_gate_fails_on_mutated_source_token():
    tokens = _token_values(TOKEN_FILE.read_text(encoding="utf-8"))
    healthy = next(p for p in PAIRS if p.name == "preview-ribbon")
    assert _ratio(healthy, tokens) >= 4.5
    bad = {**tokens, "--star-muted": "#404448"}
    assert _ratio(healthy, bad) < 4.5


def test_alpha_wash_is_composited_before_contrast():
    tokens = _token_values(TOKEN_FILE.read_text(encoding="utf-8"))
    pair = next(p for p in PAIRS if p.name == "tag-gold")
    assert parse_color(tokens[pair.background])[3] < 1
    assert _ratio(pair, tokens) > 4.5
    with pytest.raises(AssertionError, match="backdrop"):
        _opaque(tokens[pair.background])
