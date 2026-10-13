"""The non-golden Roblox debugging practice tasks use STAR's actual suite and pattern checker."""
from __future__ import annotations

import json
from pathlib import Path
import re

from star import eval_checks
from star.eval_runner import load_suite

ROOT = Path(__file__).resolve().parents[1]
SUITE_DIR = ROOT / "evals" / "roblox"
PATH = SUITE_DIR / "practice-tasks-debugging-v1.json"
OLD = ("golden-tasks-creation-v1.json", "golden-tasks-v1.json",
       "golden-tasks-v2.json", "holdout-v1.json")
GOOD_FIXES = json.loads(r'''{"DBG-01":"local rooms = workspace:WaitForChild(\"VaultRooms\")\nlocal door = rooms:WaitForChild(\"VaultDoor\")\ndoor.CanCollide = false","DBG-02":"local gui = script.Parent\ngui.ResetOnSpawn = false\ngui.Enabled = true","DBG-03":"local cooldown = {}\nscript.Parent.Touched:Connect(function(hit)\n local humanoid = hit.Parent:FindFirstChildOfClass(\"Humanoid\")\n if not humanoid or cooldown[humanoid] then return end\n cooldown[humanoid] = true\n humanoid.Health -= 10\n task.delay(1, function() cooldown[humanoid] = nil end)\nend)","DBG-04":"local label = script.Parent.Label\nwhile true do\n label.Text = \"Loading\"\n task.wait(0.5)\nend","DBG-05":"local signal = game:GetService(\"ReplicatedStorage\"):WaitForChild(\"LampToggle\")\nscript.Parent.Activated:Connect(function() signal:FireServer() end)\n-- In the server Script:\nlocal remote = game:GetService(\"ReplicatedStorage\"):WaitForChild(\"LampToggle\")\nremote.OnServerEvent:Connect(function(player)\n local lamp = workspace:FindFirstChild(\"LobbyLamp\")\n if lamp then lamp.Color = Color3.fromRGB(0, 255, 0) end\nend)","DBG-06":"local ts = game:GetService(\"TweenService\")\nlocal tween = ts:Create(script.Parent, TweenInfo.new(1), {Transparency = 1})\ntween:Play()","DBG-07":"local spark = workspace:FindFirstChild(\"Firework\")\ntask.wait(3)\nif spark and spark.Parent then spark.Transparency = 1 end","DBG-08":"local button = script.Parent.Craft\nlocal connection\nlocal function openMenu()\n if connection then connection:Disconnect() end\n connection = button.Activated:Connect(function() print(\"craft\") end)\nend\nlocal function closeMenu()\n if connection then connection:Disconnect(); connection = nil end\nend\nopenMenu()\ncloseMenu()","DBG-09":"local remote = game:GetService(\"ReplicatedStorage\"):WaitForChild(\"TipRemote\")\nremote.OnServerEvent:Connect(function(player, amount)\n if typeof(amount) ~= \"number\" then return end\n print(player.UserId, amount)\nend)","DBG-10":"local prompt = script.Parent:WaitForChild(\"ProximityPrompt\")\nprompt.Triggered:Connect(function(player)\n    local coins = player:WaitForChild(\"leaderstats\"):WaitForChild(\"Coins\")\n    coins.Value += 5\nend)","DBG-11":"local players = game:GetService(\"Players\")\nplayers.PlayerAdded:Connect(function(player) print(player.Name) end)","DBG-12":"local p = game:GetService(\"Players\").LocalPlayer\nlocal function bind(character)\n local hum = character:WaitForChild(\"Humanoid\")\n hum.Running:Connect(function(speed) print(speed) end)\nend\np.CharacterAdded:Connect(bind)\nif p.Character then bind(p.Character) end","DBG-13":"local remote = game:GetService(\"ReplicatedStorage\"):WaitForChild(\"RoundSignal\")\nremote.OnClientEvent:Connect(function(text) print(text) end)","DBG-14":"local button = Instance.new(\"TextButton\")\nbutton.Parent = script.Parent\nbutton.Activated:Connect(function() print(\"Play\") end)","DBG-15":"local store = game:GetService(\"DataStoreService\"):GetDataStore(\"QuestSave\")\ngame:GetService(\"Players\").PlayerRemoving:Connect(function(player)\n local ok, err = pcall(function() store:SetAsync(tostring(player.UserId), 4) end)\n if not ok then warn(err) end\nend)","DBG-16":"local prompt = script.Parent\nprompt.Triggered:Connect(function(player)\n print(player.UserId)\nend)","DBG-17":"local ding = workspace:WaitForChild(\"LevelJingle\")\nding:Play()","DBG-18":"local pad = script.Parent\npad.Color = Color3.fromRGB(255, 128, 0)","DBG-19":"local ts = game:GetService(\"TweenService\")\nlocal tween = ts:Create(script.Parent, TweenInfo.new(2), {Transparency = 1})\ntween:Play()","DBG-20":"local tool = script.Parent\ntool.RequiresHandle = false\ntool.Activated:Connect(function() print(\"Cast\") end)","DBG-21":"local sparks = script.Parent\nsparks.Rate = 0\nsparks.Enabled = false\nsparks:Emit(20)","DBG-22":"local tool = script.Parent\nlocal oldSpeed, activeHumanoid\ntool.Equipped:Connect(function()\n activeHumanoid = tool.Parent:FindFirstChildOfClass(\"Humanoid\")\n if activeHumanoid then oldSpeed = activeHumanoid.WalkSpeed; activeHumanoid.WalkSpeed = 28 end\nend)\ntool.Unequipped:Connect(function()\n if activeHumanoid and activeHumanoid.Parent and oldSpeed then activeHumanoid.WalkSpeed = oldSpeed end\n activeHumanoid = nil\nend)","DBG-23":"local run = game:GetService(\"RunService\")\nrun.Heartbeat:Connect(function(dt)\n workspace.Sign.Orientation += Vector3.new(0, dt * 30, 0)\nend)","DBG-24":"local gui = game:GetService(\"Players\").LocalPlayer.PlayerGui:WaitForChild(\"PauseGui\")\nlocal function close() gui.Enabled = false end\nlocal function open() gui.Enabled = true end\nclose()\nopen()","DBG-25":"local query = game:GetService(\"ReplicatedStorage\"):WaitForChild(\"GetWave\")\nlocal ok, wave = pcall(function() return query:InvokeServer() end)\nif ok then print(wave) end"}''')


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]{3,}", text.lower()))


def normalized(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9_]+", text.lower()))


def test_loads_all_debugging_tasks_with_the_existing_loader():
    suite = load_suite(PATH)
    assert len(suite.tasks) == len(suite.runnable()) == 25
    assert [t["id"] for t in suite.tasks] == [f"DBG-{n:02d}" for n in range(1, 26)]


def test_each_task_has_one_distinct_bug_source_lesson_and_code_checks():
    tasks = load_suite(PATH).tasks
    assert len({t["category"] for t in tasks}) == 25
    assert len({normalized(t["goal"]) for t in tasks}) == 25
    assert set(GOOD_FIXES) == {t["id"] for t in tasks}
    for task in tasks:
        assert task["run_mode"] == "automated" and task["split"] == "development"
        assert task["teaches"].strip() and task["expected_sources"]
        assert all(s.startswith("content/en-us/") for s in task["expected_sources"])
        assert task["auto"]["require"] and task["auto"]["forbid"]
        assert task["fixture_status"] == "not_needed" and task["fixtures"] == []
        assert task["grader"]["type"] == "static"
        assert "Roblox" in task["prompt"] and "Broken Luau:" in task["prompt"]
        assert len(eval_checks.extract_luau_blocks(task["prompt"])) == 1
        rule_ids = [r["id"] for name in ("require", "forbid") for r in task["auto"][name]]
        assert len(rule_ids) == len(set(rule_ids))
        for name in ("require", "forbid"):
            for rule in task["auto"][name]:
                assert rule["re"] and rule["why"]
                re.compile(rule["re"])
    assert next(t for t in tasks if t["id"] == "DBG-05")["auto"]["min_blocks"] == 2


def test_known_good_repair_passes_and_original_bug_fails_real_pattern_checker():
    # Static-pattern regression witnesses, not executed Luau or measured STAR improvement.
    for task in load_suite(PATH).tasks:
        good = eval_checks.pattern_checks(task["auto"], [GOOD_FIXES[task["id"]]], "")
        bad = eval_checks.pattern_checks(task["auto"],
                                         eval_checks.extract_luau_blocks(task["prompt"]), "")
        assert good and all(c.ok for c in good), (
            task["id"], [c.id for c in good if not c.ok]
        )
        assert bad and any(not c.ok for c in bad), task["id"]


def test_no_copy_or_near_copy_of_any_golden_or_holdout_suite():
    new = load_suite(PATH).tasks
    old = [task for name in OLD
           for task in json.loads((SUITE_DIR / name).read_text(encoding="utf-8"))]
    for n, task in enumerate(new):
        for other in new[:n]:
            assert task["id"] != other["id"]
            assert normalized(task["goal"]) != normalized(other["goal"])
            assert normalized(task["prompt"]) != normalized(other["prompt"])
        for other in old:
            assert task["id"] != other["id"]
            assert normalized(task["goal"]) != normalized(other["goal"])
            assert normalized(task["prompt"]) != normalized(other["prompt"])
            a, b = words(task["prompt"]), words(other["prompt"])
            ratio = len(a & b) / max(1, len(a | b))
            assert ratio < 0.5, (task["id"], other["id"], round(ratio, 3))
