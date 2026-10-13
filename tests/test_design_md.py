import pytest

from star import design_md
from star.design_md import DesignMdError, contrast_ratio, lint, parse, render

GOOD = """---
version: alpha
name: Daylight Prestige
colors:
  primary: "#1A1C1E"
  on-primary: "#FFFFFF"
  secondary: "#6C7278"
  neutral: "#F7F5F2"
  surface: "#FFFFFF"
  on-surface: "#1A1C1E"
  error: "#B3261E"
typography:
  headline-lg:
    fontFamily: Public Sans
    fontSize: 48px
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: -0.02em
  body-md:
    fontFamily: Public Sans
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
rounded:
  sm: 4px
  md: 8px
spacing:
  sm: 8px
  md: 16px
  columns: 12
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 12px
omitted:
  - section: elevation
    reason: "Flat design"
---

# Daylight Prestige

## Overview

Calm and precise.

## Colors

- **Primary (#1A1C1E):** deep ink.

## Typography

Public Sans throughout.
"""


def rules(report, severity=None):
    return {f["rule"] for f in report["findings"] if severity is None or f["severity"] == severity}


def test_wcag_contrast_matches_known_values():
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert contrast_ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1.0)
    # WCAG reference: #777777 on white is about 4.48:1 (fails AA), #767676 is 4.54:1 (passes).
    assert contrast_ratio("#777777", "#FFFFFF") == pytest.approx(4.48, abs=0.01)
    assert contrast_ratio("#767676", "#FFFFFF") == pytest.approx(4.54, abs=0.01)
    assert contrast_ratio("#fff", "rgb(0, 0, 0)") == pytest.approx(21.0)
    assert contrast_ratio("hsl(0, 0%, 100%)", "black") == pytest.approx(21.0)
    with pytest.raises(ValueError):
        contrast_ratio("#00000080", "#FFFFFF")   # translucent: depends on the backdrop
    with pytest.raises(ValueError):
        contrast_ratio("oklch(0.5 0.1 200)", "#FFFFFF")


def test_clean_file_lints_without_errors_or_warnings():
    report = lint(GOOD)
    assert report["ok"] and report["errors"] == 0 and report["warnings"] == 0, report["findings"]
    assert report["name"] == "Daylight Prestige"
    assert report["summary"] == {"colors": 7, "typography": 2, "rounded": 2, "spacing": 3, "components": 1}
    parsed = parse(GOOD)
    assert parsed["tokens"]["omitted"] == [{"section": "elevation", "reason": "Flat design"}]
    assert parsed["tokens"]["typography"]["headline-lg"]["fontWeight"] == 600
    assert parsed["sections"] == ["Overview", "Colors", "Typography"]


def test_broken_reference_low_contrast_and_unknown_property():
    text = GOOD.replace('textColor: "{colors.on-primary}"', 'textColor: "{colors.missing}"')
    report = lint(text)
    assert not report["ok"] and "broken-ref" in rules(report, "error")

    low = GOOD.replace('on-primary: "#FFFFFF"', 'on-primary: "#2A2C2E"')
    report = lint(low)
    assert report["ok"]   # contrast is a warning, as in the upstream linter
    messages = [f["message"] for f in report["findings"] if f["rule"] == "contrast-ratio"]
    assert any("below WCAG AA" in m for m in messages)
    assert len(messages) == 2   # the component pair and the on-primary/primary token pair

    odd = GOOD.replace("    padding: 12px", "    padding: 12px\n    borderColor: red")
    assert any(f["path"] == "components.button-primary.borderColor" for f in lint(odd)["findings"])


def test_unquoted_hex_is_a_yaml_comment_and_is_reported():
    text = GOOD.replace('primary: "#1A1C1E"\n', "primary: #1A1C1E\n", 1)
    report = lint(text)
    assert not report["ok"]
    assert any("Quote it" in f["message"] for f in report["findings"])


def test_missing_tokens_sections_and_order():
    text = """---
name: Bare
colors:
  accent: "#FF6600"
  on-surface: "#111111"
---

## Typography

x

## Colors

y

## Colors

z
"""
    report = lint(text)
    found = rules(report)
    assert {"missing-primary", "missing-typography", "missing-sections", "token-completeness",
            "section-order", "duplicate-section"} <= found
    assert not report["ok"]   # duplicate sections are an error in the spec


def test_invalid_values_and_unknown_keys():
    text = """---
name: Bad
theme: dark
colors:
  primary: notacolour!
typography:
  body:
    fontFamily: Inter
    fontSize: 16
    fontWeight: heavy
rounded:
  md: 8
---
"""
    report = lint(text)
    assert "invalid-color" in rules(report, "error")
    assert "unknown-key" in rules(report)
    assert {"invalid-dimension", "invalid-typography"} <= rules(report)


def test_no_front_matter_and_unsupported_yaml():
    assert "no-front-matter" in rules(lint("# Just prose\n\n## Overview\n\nHello\n"))
    assert "yaml-parse" in rules(lint("---\nname: x\ncolors: {primary: '#000'}\n---\n"))
    assert "yaml-parse" in rules(lint("---\nname: x\n"))   # unterminated front matter
    assert "duplicate-key" in rules(lint("---\nname: a\nname: b\n---\n"))
    assert "broken-ref" in rules(lint('---\nname: x\ncolors:\n  primary: "{colors.secondary}"\n'
                                      '  secondary: "{colors.primary}"\n---\n'))   # circular


def test_render_round_trips_through_parse_and_lint():
    tokens = parse(GOOD)["tokens"]
    text = render("Daylight Prestige", tokens, {"Colors": "Ink and limestone.", "Overview": "Calm.",
                                               "Iconography": "Line icons."}, description="A test: system")
    again = parse(text)
    for group in ("colors", "typography", "rounded", "spacing", "components", "omitted"):
        assert again["tokens"][group] == tokens[group]
    assert again["tokens"]["description"] == "A test: system"
    assert again["sections"] == ["Overview", "Colors", "Iconography"]   # spec order, unknown last
    assert lint(text)["ok"]


def test_workspace_read_and_write(tmp_path):
    assert design_md.read(tmp_path)["exists"] is False
    written = design_md.write(tmp_path, GOOD)
    assert written["written"] and (tmp_path / "DESIGN.md").read_text(encoding="utf-8") == GOOD
    with pytest.raises(DesignMdError):
        design_md.write(tmp_path, GOOD)   # no silent overwrite
    design_md.write(tmp_path, GOOD.replace("Calm and precise.", "Calm."), overwrite=True)
    found = design_md.read(tmp_path)
    assert found["exists"] and "Calm." in found["text"] and found["lint"]["ok"]
    with pytest.raises(DesignMdError):
        design_md.write(tmp_path, "---\nname: x\ncolors: {a: b}\n---\n", overwrite=True)   # lint errors
    assert not list(tmp_path.glob(".DESIGN.*"))   # no temporary files left behind
    with pytest.raises(DesignMdError):
        design_md.read(tmp_path / "missing")
    with pytest.raises(DesignMdError):
        design_md.read(None)


def test_oversized_text_is_rejected_by_lint():
    report = lint("x" * (design_md.MAX_BYTES + 1))
    assert not report["ok"] and "too-large" in rules(report)
