"""Regression checks for the four source-audited DataStore/remote packs."""
from pathlib import Path
import re
from collections import Counter
from urllib.parse import urlsplit

from star import skill_packs
from star.luau_lint import lint

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "agents" / "skill-pack-audit-datastores-remotes.md"
NAMES = (
    "roblox-datastore-safety",
    "roblox-datastore-service-patterns",
    "roblox-remote-event-function-patterns",
    "roblox-secure-remotes",
)
EXPECTED_DEFAULT = (
    "roblox-secure-remotes", "roblox-animation-craft", "roblox-vfx",
    "roblox-building-layout", "eng-verify-before-done",
)


def test_audit_rows_have_live_pack_line_source_and_disposition():
    rows = [line for line in AUDIT.read_text(encoding="utf-8").splitlines()
            if line.startswith("| `star/skill_packs/")]
    assert len(rows) >= 40
    verdicts = Counter()
    counts = Counter()
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split(" | ")]
        assert len(cells) == 5, row
        original, claim, verdict, source, treatment = cells
        match = re.fullmatch(r"`(star/skill_packs/([^/]+)/SKILL.md):(\d+)`", original)
        assert match is not None, original
        path, name, line = match.groups()
        assert name in NAMES and int(line) > 0
        assert (ROOT / path).is_file()
        assert claim and treatment
        assert verdict in {"**true**", "**partly**", "**false**", "**unverifiable**"}
        url = re.fullmatch(r"\[Creator Hub\]\((https://[^)]+)\)", source)
        assert url and urlsplit(url[1]).hostname == "create.roblox.com"
        assert urlsplit(url[1]).path.startswith("/docs/")
        counts[name] += 1
        verdicts[verdict.strip("*")] += 1
    assert set(counts) == set(NAMES)
    assert min(counts.values()) >= 10
    assert sum(verdicts.values()) == len(rows)
    report = AUDIT.read_text(encoding="utf-8")
    for status, count in verdicts.items():
        assert f"| {status} | {count} |" in report


def test_all_unchanged_pack_defaults_and_size_limits():
    skill_packs.available.cache_clear()
    packs = {pack.name: pack for pack in skill_packs.available()}
    assert tuple(skill_packs.DEFAULT_ENABLED) == EXPECTED_DEFAULT
    assert all(name in packs for name in NAMES)
    for name in NAMES:
        assert len(packs[name].body) <= skill_packs.MAX_BODY_CHARS
        assert skill_packs.render([packs[name]]) == packs[name].body + "\n"
        assert (packs[name].file.parent / "references" / "sources.md").is_file()


def test_corrected_claims_remove_absences_and_absolute_prohibitions():
    pack = {p.name: p.body for p in skill_packs.available() if p.name in NAMES}
    assert "4,194,304 characters" in pack["roblox-datastore-safety"]
    assert "SetAsync is valid" in pack["roblox-datastore-safety"]
    assert "never grant the same ID twice" in pack["roblox-datastore-safety"]
    assert "current server budget documentation" in pack["roblox-datastore-service-patterns"]
    assert "independently validates and authorizes" in pack["roblox-remote-event-function-patterns"]
    secure = pack["roblox-secure-remotes"]
    assert "OnServerEvent supplies the sender Player first" in secure
    assert "Do not depend on RemoteFunction:InvokeClient" in secure
    assert "under 1000 bytes" not in secure
    assert "guarantees eventual arrival" not in secure
    assert "PurchaseId" in secure


def test_all_six_real_pack_luau_code_blocks_are_lint_clean():
    packs = {pack.name: pack for pack in skill_packs.available() if pack.name in NAMES}
    examples = [
        (name, code)
        for name in NAMES
        for code in re.findall(r"^~~~luau\n(.*?)\n~~~$", packs[name].body, re.M | re.S)
    ]
    assert len(examples) == 6
    for name, code in examples:
        assert lint(code) == [], name
    assert lint("local x = (") != []
