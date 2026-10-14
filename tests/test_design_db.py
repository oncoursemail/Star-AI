import csv
import hashlib
import json

import pytest

from star import design_db, design_md
from star.design_db import DATA_DIR


def test_vendored_files_match_provenance_and_license():
    provenance = json.loads((DATA_DIR / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert provenance["source_repository"] == "https://github.com/nextlevelbuilder/ui-ux-pro-max-skill"
    assert len(provenance["source_commit"]) == 40
    assert provenance["license"] == "MIT"
    license_text = (DATA_DIR / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in license_text and "Next Level Builder" in license_text
    for name, meta in provenance["files"].items():
        data = (DATA_DIR / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == meta["sha256"], name
        if "rows" in meta:
            with open(DATA_DIR / name, encoding="utf-8", newline="") as handle:
                assert sum(1 for _ in csv.DictReader(handle)) == meta["rows"], name


def test_no_brand_design_md_files_are_bundled():
    root = DATA_DIR.parent
    assert not [path for path in root.rglob("*") if path.name.upper() == "DESIGN.MD"]


def test_every_domain_loads_and_searches():
    assert len(design_db.rows("style")) == 88
    assert len(design_db.rows("palette")) == 192
    assert len(design_db.rows("typography")) == 74
    assert len(design_db.rows("ux")) == 119
    found = design_db.search("palette", "gaming", 3)
    assert found["results"][0]["name"] == "Gaming"
    assert found["untrusted"] is True and "MIT" in found["note"]


def test_style_search_skips_deprecated_and_prefers_main_styles():
    deprecated = {row["Style Category"] for row in design_db.rows("style") if row["Status"] == "deprecated"}
    for query in ("vaporwave retro", "dashboard analytics", "landing page hero"):
        names = {item["name"] for item in design_db.search("style", query, 10)["results"]}
        assert not names & deprecated
    old_row = next(row for row in design_db.rows("style") if row["Status"] == "deprecated")
    with_old = design_db.search("style", old_row["Style Category"], 10, include_deprecated=True)["results"]
    assert old_row["Style Category"] in {item["name"] for item in with_old}
    without = design_db.search("style", old_row["Style Category"], 10)["results"]
    assert old_row["Style Category"] not in {item["name"] for item in without}
    top = design_db.search("style", "luxury fashion ecommerce", 1)["results"][0]
    assert top["status"] == "active"


def test_typography_and_ux_results_have_useful_fields():
    fonts = design_db.search("typography", "playful kids game", 3)["results"]
    assert fonts and all(item["heading_font"] and item["body_font"] for item in fonts)
    rules = design_db.search("ux", "touch target size mobile", 5)["results"]
    assert any("Touch" in item["issue"] for item in rules)
    assert all(set(item) >= {"do", "dont", "severity"} for item in rules)


def test_palette_contrast_is_measured_with_wcag_formula():
    palette = design_db.search("palette", "saas general", 1)["results"][0]
    assert palette["colors"]["primary"].startswith("#")
    pair = next(c for c in palette["contrast"] if c["text"] == "on-primary")
    expected = design_md.contrast_ratio(palette["colors"]["on-primary"], palette["colors"]["primary"])
    assert pair["ratio"] == round(expected, 2)
    assert pair["wcag_aa_normal_text"] == (expected >= 4.5)


def test_recommend_gives_tokens_that_draft_a_clean_design_md():
    rec = design_db.recommend("cozy pet adoption mobile app")
    assert rec["style"] and rec["palette"] and rec["typography"] and rec["ux_rules"]
    tokens = rec["tokens"]
    assert tokens["colors"]["primary"] == rec["palette"]["colors"]["primary"]
    assert tokens["typography"]["body-md"]["fontFamily"] == rec["typography"]["body_font"]
    text = design_md.draft(rec, "Paws Starter")
    report = design_md.lint(text)
    assert report["ok"], report["findings"]
    assert report["summary"]["colors"] == len(tokens["colors"])


def test_unmatched_query_and_bad_arguments():
    assert design_db.search("ux", "zzqqxx", 3)["results"] == []
    assert "No row matched" in design_db.search("ux", "zzqqxx", 3)["note"]
    rec = design_db.recommend("zzqqxx")   # falls back to neutral defaults instead of failing
    assert rec["style"] and rec["palette"]
    for bad in (("colour", "x", 3), ("style", "", 3), ("style", "x" * 301, 3), ("style", "x", 0), ("style", "x", 11)):
        with pytest.raises(ValueError):
            design_db.search(*bad)
