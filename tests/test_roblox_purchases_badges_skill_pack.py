"""Receipt-safe Roblox purchases skill pack registration and sample checks."""
from pathlib import Path
import re
from urllib.parse import urlsplit
from star import skill_packs
from star.agent_skills import SkillLibrary
from star.luau_lint import lint
from star.roblox_api_checker import check_luau_api, load_api_dump

NAME = "roblox-purchases-badges"
ROOT = Path(__file__).resolve().parents[1]
PROMPT = "In Roblox Studio, use ProcessReceipt and BadgeService to award developer products."


def test_real_selection_and_library_loading_opt_in_only(tmp_path):
    skill_packs.available.cache_clear()
    p = next(pack for pack in skill_packs.available() if pack.name == NAME)
    assert NAME not in skill_packs.DEFAULT_ENABLED
    assert NAME not in skill_packs.enabled_names({})
    assert skill_packs.enabled_names({skill_packs.ENV_VAR: NAME}) == {NAME}
    assert skill_packs.matching_names(PROMPT) == []
    assert skill_packs.matching_names(PROMPT, enabled={NAME}) == [NAME]
    assert skill_packs.matching_names("Web purchases", enabled={NAME}) == []
    assert skill_packs.matching_names("In Roblox Studio, create a lobby", enabled={NAME}) == []
    assert skill_packs.render(skill_packs.select(PROMPT, enabled={NAME})) == p.body + "\n"
    assert skill_packs.render(skill_packs.select(PROMPT, enabled=set())) == ""
    assert len(p.body) <= skill_packs.MAX_BODY_CHARS
    library = SkillLibrary(workspace=None, home=tmp_path, bundled=skill_packs.PACKS_DIR)
    assert library.load(NAME)["instructions"].strip() == p.body
    assert library.load(NAME)["references"] == ["references/sources.md"]


def test_ten_rules_all_grounded_in_creator_hub_and_deprecation_caught():
    p = next(p for p in skill_packs.available() if p.name == NAME)
    rules = p.body.split("## Ten concrete rules\n", 1)[1].split("\n## ", 1)[0]
    assert re.findall(r"^(\d+)\. ", rules, re.M) == [str(i) for i in range(1, 11)]
    refs = (p.file.parent / "references" / "sources.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (S\d+) \| (.*?) \| (https://\S+) \|$", refs, re.M)
    assert len(rows) == 10 and {r[0] for r in rows} == {f"S{i}" for i in range(1, 11)}
    assert all(any(re.search(r"\b" + str(i) + r"\b", desc) for _, desc, _ in rows) for i in range(1, 11))
    assert all(urlsplit(url).hostname == "create.roblox.com"
               and urlsplit(url).path.startswith("/docs/") for _, _, url in rows)
    assert "AwardBadgeAsync" in rules and "deprecated" in rules


def test_skeleton_checks_real_linter_api_dump_and_replay_guard():
    p = next(p for p in skill_packs.available() if p.name == NAME)
    blocks = re.findall(r"^```luau\n(.*?)\n```$", p.body, re.M | re.S)
    assert len(blocks) == 1
    code = blocks[0]
    for required in ("--!strict", "PurchaseId", "UpdateAsync", "pcall", "NotProcessedYet",
                     "PurchaseGranted", "MarketplaceService.ProcessReceipt = processReceipt",
                     "if old.ReceiptIds[purchaseId] then return old end", "receiptIds[purchaseId] = true",
                     "return nextRecord", "attempt < 3"):
        assert required in code
    assert code.index("if old.ReceiptIds[purchaseId] then return old end") < code.index("receiptIds[purchaseId] = true")
    assert lint(code) == []
    dump = load_api_dump(ROOT / "tests/fixtures/roblox_marketplace_api.json")
    assert check_luau_api(code, dump) == []
    assert {f.rule_id for f in check_luau_api('game:GetService("MarketplaceServce")', dump)} == {"unknown-service"}


def test_default_enabled_constant_is_unchanged():
    assert skill_packs.DEFAULT_ENABLED == ("roblox-secure-remotes", "roblox-animation-craft",
                                           "roblox-vfx", "roblox-building-layout",
                                           "eng-verify-before-done")
