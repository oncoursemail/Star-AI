"""Offline contract checks for the additional Roblox security practice suite.

These probes exercise the production load_suite and score_answer paths; the
illustrative fragments are pattern probes, NOT runtime reference solutions.
Actual Luau compilation, engine behavior, and model improvement are not tested here.
"""
import json
from pathlib import Path
import re

from star.eval_checks import score_answer
from star.eval_runner import load_suite

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "evals" / "roblox"
SUITE = DIR / "practice-tasks-security-v1.json"
PRIOR = ("golden-tasks-v1.json", "golden-tasks-v2.json", "golden-tasks-creation-v1.json", "holdout-v1.json")
TOPICS = {"remote-validation": 8, "economy-receipts": 4, "data-boundaries": 3, "authorization-trust": 5}
OVERLAP_LIMIT = 0.5

# Each pair is a compact syntax probe: safe markers, then an unsafe anti-example.
# They intentionally do not stand in for a compiling implementation.
PROBES = {
  "SEC-01": [
    "local ROUND_REWARD = 40\nFinishRound.OnServerEvent:Connect(function(player, clientAmount)\n if not qualified[player.UserId] then return end\n qualified[player.UserId] = nil\n player.leaderstats.Coins.Value += ROUND_REWARD\nend)",
    "FinishRound.OnServerEvent:Connect(function(player, clientAmount)\n player.leaderstats.Coins.Value += clientAmount\nend)"
  ],
  "SEC-02": [
    "PadTravel.OnServerEvent:Connect(function(player, padId, requestedCFrame)\n if typeof(padId) ~= \"string\" then return end\n local record = DESTINATIONS[padId]\n if not record then return end\n local character = player.Character\n local root = character and character:FindFirstChild(\"HumanoidRootPart\")\n if not root or (root.Position - record.entry.Position).Magnitude > 10 then return end\n character:PivotTo(record.exit.CFrame)\nend)",
    "PadTravel.OnServerEvent:Connect(function(player, padId, requestedCFrame)\n player.Character:PivotTo(requestedCFrame)\nend)"
  ],
  "SEC-03": [
    "ShopBuy.OnServerEvent:Connect(function(player, itemId, clientPrice)\n local item = Catalog[itemId]\n if not item then return end\n local discount = Coupons[player.UserId] and 10 or 0\n local charge = math.max(0, item.price - discount)\n if player.leaderstats.Coins.Value < charge then return end\n player.leaderstats.Coins.Value -= charge\n grant(player, itemId)\nend)",
    "ShopBuy.OnServerEvent:Connect(function(player, itemId, clientPrice)\n player.leaderstats.Coins.Value -= clientPrice\n grant(player, itemId)\nend)"
  ],
  "SEC-04": [
    "local DAMAGE = 8\nFireProjectile.OnServerEvent:Connect(function(player, targetModel, clientDamage, aimDirection)\n if typeof(aimDirection) ~= \"Vector3\" then return end\n local origin = getEquippedMuzzle(player).Position\n local result = workspace:Raycast(origin, aimDirection.Unit * 100)\n if not result or not result.Instance then return end\n local humanoid = result.Instance.Parent:FindFirstChildOfClass(\"Humanoid\")\n if humanoid then humanoid:TakeDamage(DAMAGE) end\nend)",
    "FireProjectile.OnServerEvent:Connect(function(player, targetModel, clientDamage, aimDirection)\n targetModel.Humanoid:TakeDamage(clientDamage)\nend)"
  ],
  "SEC-05": [
    "local MAX_CALLS = 4\nlocal WINDOW = 1\nlocal rates = {}\nSendPing.OnServerEvent:Connect(function(player)\n local now = os.clock()\n local state = rates[player.UserId] or {start = now, count = 0}\n if now - state.start >= WINDOW then state.start, state.count = now, 0 end\n if state.count >= MAX_CALLS then return end\n state.count += 1\n rates[player.UserId] = state\n broadcastPing(player)\nend)\nPlayers.PlayerRemoving:Connect(function(player) rates[player.UserId] = nil end)",
    "SendPing.OnServerEvent:Connect(function(player)\n task.wait(1)\n broadcastPing(player)\nend)"
  ],
  "SEC-06": [
    "LoadSlot.OnServerEvent:Connect(function(player, slotName)\n local key = \"Account_\" .. tostring(player.UserId)\n local ok, data = pcall(function() return store:GetAsync(key) end)\n if ok then SlotReply:FireClient(player, data) end\nend)",
    "LoadSlot.OnServerEvent:Connect(function(player, slotName)\n local ok, data = pcall(function() return store:GetAsync(slotName) end)\n SlotReply:FireClient(player, data)\nend)"
  ],
  "SEC-07": [
    "MarketplaceService.ProcessReceipt = function(receiptInfo)\n local player = Players:GetPlayerByUserId(receiptInfo.PlayerId)\n if not player or not PRODUCT_GRANTS[receiptInfo.ProductId] then\n  return Enum.ProductPurchaseDecision.NotProcessedYet\n end\n local ok = grantPersistedOnce(player, receiptInfo)\n if not ok then return Enum.ProductPurchaseDecision.NotProcessedYet end\n return Enum.ProductPurchaseDecision.PurchaseGranted\nend",
    "MarketplaceService.ProcessReceipt = function(receiptInfo)\n local player = Players:GetPlayerByUserId(receiptInfo.PlayerId)\n if not player then return nil end\n grant(player, receiptInfo)\n return true\nend"
  ],
  "SEC-08": [
    "ChangeTitle.OnServerEvent:Connect(function(player, targetUserId, titleId)\n if not TITLES[titleId] then return end\n local profile = profileCache[player.UserId]\n if not profile then return end\n profile.title = titleId\n saveOwnProfile(player, profile)\nend)",
    "ChangeTitle.OnServerEvent:Connect(function(player, targetUserId, titleId)\n profileCache[targetUserId].title = titleId\nend)"
  ],
  "SEC-09": [
    "EquipBlade.OnServerEvent:Connect(function(player, itemId)\n if typeof(itemId) ~= \"string\" then return end\n local owned = inventories[player.UserId]\n if not owned or not owned[itemId] then return end\n local template = EQUIPPABLE[itemId]\n if not template then return end\n template:Clone().Parent = player.Backpack\nend)",
    "EquipBlade.OnServerEvent:Connect(function(player, itemId)\n itemId:Clone().Parent = player.Backpack\nend)"
  ],
  "SEC-10": [
    "ChooseTeam.OnServerEvent:Connect(function(player, teamId, clientTeam)\n if typeof(teamId) ~= \"string\" then return end\n local team = ALLOWED_TEAMS[teamId]\n if not team or #team:GetPlayers() >= MAX_TEAM_SIZE then return end\n player.Team = team\nend)",
    "ChooseTeam.OnServerEvent:Connect(function(player, teamId, clientTeam)\n player.Team = clientTeam\nend)"
  ],
  "SEC-11": [
    "CollectShell.OnServerEvent:Connect(function(player, pickup, clientCollected)\n if typeof(pickup) ~= \"Instance\" then return end\n if not pickup:IsDescendantOf(workspace.Pickups) then return end\n local root = player.Character and player.Character:FindFirstChild(\"HumanoidRootPart\")\n if not root or (root.Position - pickup.Position).Magnitude > 10 then return end\n claimAndDestroy(pickup, player)\nend)",
    "CollectShell.OnServerEvent:Connect(function(player, pickup, clientCollected)\n if clientCollected then giveShell(player) end\nend)"
  ],
  "SEC-12": [
    "OpenCrate.OnServerEvent:Connect(function(player, crateId, wishedRarity)\n local crates = playerCrates[player.UserId]\n if not crates or not crates[crateId] then return end\n crates[crateId] = nil\n local roll = Random.new():NextInteger(1, 100)\n local reward = REWARDS[roll <= 5 and \"rare\" or \"common\"]\n grantReward(player, reward)\nend)",
    "OpenCrate.OnServerEvent:Connect(function(player, crateId, wishedRarity)\n local reward = REWARDS[wishedRarity]\n grantReward(player, reward)\nend)"
  ],
  "SEC-13": [
    "ClaimQuest.OnServerEvent:Connect(function(player, questId, clientProgress)\n local record = QuestState[player.UserId]\n if not record or record.kills < KILLS_REQUIRED or record.claimed then return end\n record.claimed = true\n awardChest(player)\nend)",
    "ClaimQuest.OnServerEvent:Connect(function(player, questId, clientProgress)\n if clientProgress >= KILLS_REQUIRED then awardChest(player) end\nend)"
  ],
  "SEC-14": [
    "AdminAction.OnServerEvent:Connect(function(player, action, clientIsAdmin)\n if ADMIN_USER_IDS[player.UserId] ~= true then return end\n if action == \"resetRound\" then resetRound() end\nend)",
    "AdminAction.OnServerEvent:Connect(function(player, action, clientIsAdmin)\n if clientIsAdmin then resetRound() end\nend)"
  ],
  "SEC-15": [
    "SkipVote.OnServerEvent:Connect(function(player, clientVotes)\n if voted[player.UserId] then return end\n voted[player.UserId] = true\n local total = 0\n for _ in pairs(voted) do total += 1 end\n if total >= math.ceil(#Players:GetPlayers() / 2) then skipScene() end\nend)",
    "SkipVote.OnServerEvent:Connect(function(player, clientVotes)\n votes += clientVotes\n if votes >= 5 then skipScene() end\nend)"
  ],
  "SEC-16": [
    "SelectVIPEmote.OnServerEvent:Connect(function(player, clientOwns)\n local ok, owns = pcall(function()\n  return MarketplaceService:UserOwnsGamePassAsync(player.UserId, VIP_GAMEPASS_ID)\n end)\n if not ok or not owns then return end\n playVipEmote(player)\nend)",
    "SelectVIPEmote.OnServerEvent:Connect(function(player, clientOwns)\n if clientOwns then playVipEmote(player) end\nend)"
  ],
  "SEC-17": [
    "OpenGate.OnServerEvent:Connect(function(player, gate, clientHasKey, clientOpen)\n if typeof(gate) ~= \"Instance\" or not gate:IsDescendantOf(workspace.Gates) then return end\n local keys = Keyrings[player.UserId]\n if not keys or not keys.Copper then return end\n local root = player.Character and player.Character:FindFirstChild(\"HumanoidRootPart\")\n if not root or (root.Position - gate.Position).Magnitude > 12 then return end\n gate:SetAttribute(\"Open\", true)\nend)",
    "OpenGate.OnServerEvent:Connect(function(player, gate, clientHasKey, clientOpen)\n if clientHasKey then gate:SetAttribute(\"Open\", clientOpen) end\nend)"
  ],
  "SEC-18": [
    "Dash.OnServerEvent:Connect(function(player, requestedSpeed)\n if typeof(requestedSpeed) ~= \"number\" or requestedSpeed ~= requestedSpeed then return end\n local speed = math.clamp(requestedSpeed, 0, DASH_CAP)\n local root = player.Character and player.Character:FindFirstChild(\"HumanoidRootPart\")\n if root then root.AssemblyLinearVelocity = root.CFrame.LookVector * speed end\nend)",
    "Dash.OnServerEvent:Connect(function(player, requestedSpeed, requestedVelocity)\n player.Character.HumanoidRootPart.AssemblyLinearVelocity = requestedVelocity\nend)"
  ],
  "SEC-19": [
    "SavePreference.OnServerEvent:Connect(function(player, key, value, payload)\n if not ALLOWED_SETTINGS[key] or typeof(value) ~= \"boolean\" then return end\n local userKey = \"Prefs_\" .. tostring(player.UserId)\n pcall(function()\n  store:UpdateAsync(userKey, function(old)\n   local saved = old or {}\n   saved[key] = value\n   return saved\n  end)\n end)\nend)",
    "SavePreference.OnServerEvent:Connect(function(player, key, value, payload)\n local userKey = \"Prefs_\" .. tostring(player.UserId)\n store:SetAsync(userKey, payload)\nend)"
  ],
  "SEC-20": [
    "PostSign.OnServerEvent:Connect(function(player, rawText)\n if typeof(rawText) ~= \"string\" or #rawText > 100 then return end\n local ok, filtered = pcall(function()\n  local result = TextService:FilterStringAsync(rawText, player.UserId)\n  return result:GetNonChatStringForBroadcastAsync()\n end)\n if not ok then return end\n SignsChanged:FireAllClients(player, filtered)\nend)",
    "PostSign.OnServerEvent:Connect(function(player, rawText)\n SignsChanged:FireAllClients(player, rawText)\nend)"
  ]
}


def _normal(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9_]+", value.lower()))


def _words(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]{3,}", value.lower()))


def _similarity(a: str, b: str) -> float:
    x, y = _words(a), _words(b)
    return len(x & y) / max(1, len(x | y))


def _score(task: dict, code: str):
    answer = "```luau\n" + code + "\n```"
    return score_answer(task, answer, luau_check=lambda code, strict=False: {"ok": True, "errors": []})


def test_security_practice_loads_with_existing_runner():
    suite = load_suite(SUITE)
    assert len(suite.tasks) == len(suite.runnable()) == 20
    assert {t["id"] for t in suite.tasks} == set(PROBES)
    assert all(t["run_mode"] == "automated" and t["split"] == "development" for t in suite.tasks)


def test_practice_task_contract_and_topic_counts():
    tasks = load_suite(SUITE).tasks
    counts = {topic: sum(t["topic"] == topic for t in tasks) for topic in TOPICS}
    assert counts == TOPICS
    assert len({t["category"] for t in tasks}) == 20  # distinct security mistakes
    for task in tasks:
        auto = task["auto"]
        assert "Roblox" in task["prompt"], task["id"]
        assert task["teaches"].strip() and task["goal"].strip()
        assert task["expected_sources"] and task["required_evidence"]
        assert task["fixture_status"] == "not_needed" and task["fixtures"] == []
        assert auto.get("compile", True) and auto.get("code", True)
        assert len(auto["require"]) >= 2 and auto["forbid"]
        checks = auto["require"] + auto["forbid"]
        assert len({item["id"] for item in checks}) == len(checks), task["id"]
        assert all(item["why"].strip() and item.get("scope", "code") in {"code", "code_nostr", "first_raw"} for item in checks)
        assert task["grader"]["type"] == "static" and len(task["grader"]["checks"]) == 1 + len(checks)


def test_practice_is_not_a_copy_or_near_copy_of_golden_or_holdout():
    ours = json.loads(SUITE.read_text(encoding="utf-8"))
    previous = [(name, row) for name in PRIOR
                for row in json.loads((DIR / name).read_text(encoding="utf-8"))]
    previous_ids = {row["id"] for _, row in previous}
    assert not ({task["id"] for task in ours} & previous_ids)
    for index, task in enumerate(ours):
        for name, old in previous + [("this suite", prior) for prior in ours[:index]]:
            assert _normal(task["prompt"]) != _normal(old["prompt"]), (task["id"], name, old["id"])
            assert _normal(task["goal"]) != _normal(old["goal"]), (task["id"], name, old["id"])
            assert _similarity(task["prompt"], old["prompt"]) < OVERLAP_LIMIT, (task["id"], name, old["id"])


def test_scoring_path_accepts_positive_markers_and_rejects_insecure_probes():
    for task in load_suite(SUITE).tasks:
        good, bad = PROBES[task["id"]]
        secure = _score(task, good)
        insecure = _score(task, bad)
        assert secure.passed, (task["id"], secure.reasons)
        assert not insecure.passed, (task["id"], "insecure probe passed")
        assert any(check.id.startswith(("require:", "forbid:")) and not check.ok
                   for check in insecure.checks), task["id"]


def test_comment_only_markers_cannot_bypass_code_checks():
    for task in load_suite(SUITE).tasks:
        good, _ = PROBES[task["id"]]
        comment = "\n".join("-- " + line for line in good.splitlines())
        assert not _score(task, comment).passed, task["id"]
