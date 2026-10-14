"""Pathfinding NPC skill pack routing and linter/API-name evidence."""
from pathlib import Path
import re
from urllib.parse import urlsplit
from star import skill_packs
from star.agent_skills import SkillLibrary
from star.luau_lint import lint
from star.roblox_api_checker import check_luau_api, load_api_dump

NAME = "roblox-pathfinding-npc"
ROOT = Path(__file__).resolve().parents[1]
PROMPT = "In Roblox Studio, write PathfindingService movement for an NPC chasing a target."


def test_new_pack_is_registered_bounded_and_requires_opt_in(tmp_path):
    skill_packs.available.cache_clear()
    p = next(pack for pack in skill_packs.available() if pack.name == NAME)
    assert NAME not in skill_packs.DEFAULT_ENABLED
    assert NAME not in skill_packs.enabled_names({})
    assert skill_packs.enabled_names({skill_packs.ENV_VAR: NAME}) == {NAME}
    assert skill_packs.matching_names(PROMPT) == []
    assert skill_packs.matching_names(PROMPT, enabled={NAME}) == [NAME]
    assert skill_packs.matching_names(
        "In Roblox Studio, listen to Path.Blocked on the NPC", enabled={NAME}
    ) == [NAME]  # Regression: dotted event name alone must route.
    assert skill_packs.matching_names(
        r"In Roblox Studio, listen to Path\xBlocked on the NPC", enabled={NAME}
    ) == []
    assert skill_packs.matching_names("Path for a web page", enabled={NAME}) == []
    assert skill_packs.matching_names("In Roblox Studio, build an unrelated lobby", enabled={NAME}) == []
    assert skill_packs.render(skill_packs.select(PROMPT, enabled={NAME})) == p.body + "\n"
    assert skill_packs.render(skill_packs.select(PROMPT, enabled=set())) == ""
    assert len(p.body) <= skill_packs.MAX_BODY_CHARS
    library = SkillLibrary(workspace=None, home=tmp_path, bundled=skill_packs.PACKS_DIR)
    assert library.load(NAME)["instructions"].strip() == p.body
    assert library.load(NAME)["references"] == ["references/sources.md"]


def test_ten_claimed_rules_have_individual_official_references():
    p = next(p for p in skill_packs.available() if p.name == NAME)
    rules = p.body.split("## Ten concrete rules\n", 1)[1].split("\n## ", 1)[0]
    assert re.findall(r"^(\d+)\. ", rules, re.M) == [str(i) for i in range(1, 11)]
    refs = (p.file.parent / "references/sources.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (S\d+) \| (.*?) \| (https://\S+) \|$", refs, re.M)
    assert len(rows) == 8 and {row[0] for row in rows} == {f"S{i}" for i in range(1, 9)}
    assert all(any(re.search(r"\b" + str(i) + r"\b", desc) for _, desc, _ in rows)
               for i in range(1, 11))
    assert all(urlsplit(url).hostname == "create.roblox.com"
               and urlsplit(url).path.startswith("/docs/") for _, _, url in rows)


def test_strict_skeleton_bounded_failure_handling_and_real_api_checker():
    p = next(p for p in skill_packs.available() if p.name == NAME)
    blocks = re.findall(r"^```luau\n(.*?)\n```$", p.body, re.M | re.S)
    assert len(blocks) == 1
    code = blocks[0]
    for token in ("--!strict", "PathfindingService:CreatePath", "ComputeAsync",
                  "pcall(function()", "Enum.PathStatus.NoPath", "path:GetWaypoints()",
                  "Enum.PathWaypointAction.Jump", "humanoid:MoveTo",
                  "humanoid.MoveToFinished:Connect", "path.Blocked:Connect",
                  "blockedWaypointIndex >= nextWaypoint", "MIN_RECOMPUTE_INTERVAL",
                  "moveConnection:Disconnect()", "blockedConnection:Disconnect()",
                  "root:CanSetNetworkOwnership()", "root:SetNetworkOwner(nil)",
                  "humanoid.Health > 0", "target.Parent ~= nil", "os.clock() < deadline"):
        assert token in code, token
    assert lint(code) == []
    dump = load_api_dump(ROOT / "tests/fixtures/roblox_pathfinding_api.json")
    assert check_luau_api(code, dump) == []
    assert {f.rule_id for f in check_luau_api('game:GetService("PathfindingServce")', dump)} == {"unknown-service"}


def test_default_pack_list_is_unchanged():
    assert skill_packs.DEFAULT_ENABLED == (
        "roblox-secure-remotes", "roblox-animation-craft",
        "roblox-vfx", "roblox-building-layout", "eng-verify-before-done",
    )
