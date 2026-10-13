"""Offline scoring contracts for the non-golden Roblox round lifecycle practice suite.

These tests drive production load_suite() and score_answer() with a stubbed
Luau checker. The positive/negative snippets are structural probes, not certified
round systems; they are intentionally kept OUT of the public task JSON.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re

from star.eval_checks import score_answer
from star.eval_runner import load_suite

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "evals" / "roblox"
PATH = DIR / "practice-tasks-round-lifecycle-v1.json"
PRIOR = (
    "golden-tasks-v1.json",
    "golden-tasks-v2.json",
    "golden-tasks-creation-v1.json",
    "holdout-v1.json",
    "practice-tasks-security-v1.json",
    "practice-tasks-debugging-v1.json",
)
CATEGORIES = {"round-state-transitions": 3,"round-time-cancellation": 3,"round-joins-leaves": 3,"round-results-cleanup": 3}
OFFICIAL_ENGINE = {
    "Players:GetPlayers": "https://create.roblox.com/docs/reference/engine/classes/Players",
    "Players.PlayerAdded": "https://create.roblox.com/docs/reference/engine/classes/Players",
    "Players.PlayerRemoving": "https://create.roblox.com/docs/reference/engine/classes/Players",
    "Player.UserId": "https://create.roblox.com/docs/reference/engine/classes/Player",
    "RunService.Heartbeat": "https://create.roblox.com/docs/reference/engine/classes/RunService",
    "task.delay": "https://create.roblox.com/docs/reference/engine/libraries/task",
    "RBXScriptConnection:Disconnect": "https://create.roblox.com/docs/reference/engine/datatypes/RBXScriptConnection",
    "BasePart.Touched": "https://create.roblox.com/docs/reference/engine/classes/BasePart",
    "Instance:Destroy": "https://create.roblox.com/docs/reference/engine/classes/Instance",
    "table.clear": "https://create.roblox.com/docs/reference/engine/libraries/table"
}
KNOWN_DOCS = [
    "https://create.roblox.com/docs/scripting/module",
    "https://create.roblox.com/docs/luau",
    "https://create.roblox.com/docs/reference/engine/classes/Players",
    "https://create.roblox.com/docs/reference/engine/classes/Player",
    "https://create.roblox.com/docs/reference/engine/classes/RunService",
    "https://create.roblox.com/docs/reference/engine/libraries/task",
    "https://create.roblox.com/docs/reference/engine/datatypes/RBXScriptConnection",
    "https://create.roblox.com/docs/reference/engine/classes/BasePart",
    "https://create.roblox.com/docs/reference/engine/classes/Instance",
    "https://create.roblox.com/docs/reference/engine/libraries/table"
]
PROBES = json.loads(r'''{"RND-01":["local Round = {}\nlocal phase = \"Waiting\"\nlocal TRANSITIONS = {Waiting = \"Intermission\", Intermission = \"Playing\", Playing = \"Results\", Results = \"Waiting\"}\nfunction Round.transition(nextPhase)\n if TRANSITIONS[phase] ~= nextPhase then return false end\n phase = nextPhase\n return true\nend\nfunction Round.phase() return phase end\nreturn Round","local Round = {}\nlocal phase = \"Waiting\"\nfunction Round.transition(nextPhase)\n phase = nextPhase\n return true\nend\nfunction Round.phase() return phase end\nreturn Round"],"RND-02":["local Round = {}\nlocal phase, roundId = \"Waiting\", 0\nfunction Round.begin()\n if phase ~= \"Waiting\" then return false end\n roundId += 1\n phase = \"Playing\"\n return roundId\nend\nfunction Round.finish()\n if phase ~= \"Playing\" then return false end\n phase = \"Results\"\n return true\nend\nfunction Round.reset()\n if phase ~= \"Results\" then return false end\n phase = \"Waiting\"\n return true\nend\nreturn Round","local Round = {}\nlocal phase, roundId = \"Waiting\", 0\nfunction Round.begin()\n roundId += 1\n phase = \"Playing\"\n return roundId\nend\nfunction Round.finish() phase = \"Results\" return true end\nfunction Round.reset()\n roundId = 0\n phase = \"Waiting\"\n return true\nend\nreturn Round"],"RND-03":["local Round = {}\nlocal phase, revision = \"Waiting\", 0\nlocal allowed = {Waiting = \"Intermission\", Intermission = \"Playing\", Playing = \"Results\", Results = \"Waiting\"}\nlocal listeners = {}\nfunction Round.advance(nextPhase)\n if allowed[phase] ~= nextPhase then return false end\n phase = nextPhase\n revision += 1\n for _, callback in ipairs(listeners) do callback(phase, revision) end\n return true\nend\nfunction Round.subscribe(callback) table.insert(listeners, callback) end\nreturn Round","local Round = {}\nlocal phase, revision = \"Waiting\", 0\nlocal listeners = {}\nfunction Round.subscribe(callback)\n callback(phase, revision)\n table.insert(listeners, callback)\nend\nfunction Round.advance(nextPhase)\n phase = nextPhase\n revision += 1\n for _, callback in ipairs(listeners) do callback(phase, revision) end\n return true\nend\nreturn Round"],"RND-04":["local RunService = game:GetService(\"RunService\")\nlocal Countdown = {}\nfunction Countdown.start(seconds, now, onTick, onExpire)\n local deadline = now() + math.max(0, seconds)\n local connection\n connection = RunService.Heartbeat:Connect(function(_dt)\n  local remaining = math.max(0, deadline - now())\n  onTick(remaining)\n  if remaining <= 0 then\n   connection:Disconnect()\n   onExpire()\n  end\n end)\n return function()\n  if connection.Connected then connection:Disconnect() end\n end\nend\nreturn Countdown","local RunService = game:GetService(\"RunService\")\nlocal Countdown = {}\nfunction Countdown.start(seconds, now, onTick, onExpire)\n local remaining = seconds\n RunService.Heartbeat:Connect(function(dt)\n  remaining -= dt\n  onTick(remaining)\n  if remaining <= 0 then onExpire() end\n end)\nend\nreturn Countdown"],"RND-05":["local Round = {}\nlocal phase, generation = \"Waiting\", 0\nfunction Round.begin()\n if phase == \"Playing\" then return false end\n generation += 1\n phase = \"Playing\"\n return true\nend\nfunction Round.scheduleFinish(seconds)\n if phase ~= \"Playing\" then return false end\n local token = generation\n task.delay(seconds, function()\n  if token ~= generation or phase ~= \"Playing\" then return end\n  phase = \"Results\"\n end)\n return true\nend\nfunction Round.cancel()\n generation += 1\n phase = \"Waiting\"\nend\nreturn Round","local Round = {}\nlocal phase = \"Playing\"\nfunction Round.scheduleFinish(seconds)\n task.delay(seconds, function() phase = \"Results\" end)\nend\nfunction Round.cancel() phase = \"Waiting\" end\nreturn Round"],"RND-06":["local Timer = {}\nfunction Timer.new(duration, now)\n local deadline = now() + math.max(0, duration)\n local pausedAt = nil\n local object = {}\n function object:pause()\n  if pausedAt == nil then pausedAt = now() end\n end\n function object:resume()\n  if pausedAt ~= nil then\n   deadline += now() - pausedAt\n   pausedAt = nil\n  end\n end\n function object:remaining()\n  return math.max(0, deadline - (pausedAt or now()))\n end\n return object\nend\nreturn Timer","local Timer = {}\nfunction Timer.new(duration, now)\n local deadline = now() + duration\n local object = {}\n function object:pause() end\n function object:resume() end\n function object:remaining() return deadline - now() end\n return object\nend\nreturn Timer"],"RND-07":["local Players = game:GetService(\"Players\")\nlocal Roster = {}\nlocal members, spectators, active = {}, {}, false\nfunction Roster.start()\n members = {}\n spectators = {}\n for _, player in ipairs(Players:GetPlayers()) do\n  members[player.UserId] = true\n end\n active = true\nend\nfunction Roster.isParticipant(player)\n return members[player.UserId] == true\nend\nPlayers.PlayerAdded:Connect(function(player)\n if active then spectators[player.UserId] = true end\nend)\nreturn Roster","local Players = game:GetService(\"Players\")\nlocal Roster = {}\nlocal members = {}\nfunction Roster.start()\n for _, player in ipairs(Players:GetPlayers()) do members[player.UserId] = true end\nend\nfunction Roster.isParticipant(player) return members[player.UserId] == true end\nPlayers.PlayerAdded:Connect(function(player)\n members[player.UserId] = true\nend)\nreturn Roster"],"RND-08":["local Players = game:GetService(\"Players\")\nlocal Lobby = {}\nlocal phase, countdownVersion = \"Waiting\", 0\nlocal function countExcluding(exiting)\n local count = 0\n for _, p in ipairs(Players:GetPlayers()) do\n  if p ~= exiting then count += 1 end\n end\n return count\nend\nfunction Lobby.start()\n if phase ~= \"Waiting\" or countExcluding(nil) < 2 then return false end\n phase = \"Intermission\"\n countdownVersion += 1\n return countdownVersion\nend\nfunction Lobby.complete(token)\n if phase ~= \"Intermission\" or token ~= countdownVersion or countExcluding(nil) < 2 then return false end\n phase = \"Playing\"\n return true\nend\nPlayers.PlayerRemoving:Connect(function(player)\n if phase == \"Intermission\" and countExcluding(player) < 2 then\n  countdownVersion += 1\n  phase = \"Waiting\"\n end\nend)\nreturn Lobby","local Players = game:GetService(\"Players\")\nlocal Lobby = {}\nlocal phase = \"Waiting\"\nfunction Lobby.start()\n if #Players:GetPlayers() >= 2 then phase = \"Intermission\" end\nend\nPlayers.PlayerRemoving:Connect(function(player)\n if #Players:GetPlayers() < 2 then phase = \"Waiting\" end\nend)\nreturn Lobby"],"RND-09":["local Players = game:GetService(\"Players\")\nlocal Round = {winnerId = nil}\nlocal phase = \"Waiting\"\nlocal alive = {}\nfunction Round.start(players)\n table.clear(alive)\n Round.winnerId = nil\n phase = \"Playing\"\n for _, player in ipairs(players) do alive[player.UserId] = true end\nend\nlocal function leave(player)\n if phase ~= \"Playing\" or not alive[player.UserId] then return end\n alive[player.UserId] = nil\n local count, last = 0, nil\n for userId in pairs(alive) do\n  count += 1\n  last = userId\n end\n if count == 0 then\n  Round.winnerId = nil\n  phase = \"Waiting\"\n elseif count == 1 then\n  Round.winnerId = last\n  phase = \"Results\"\n end\nend\nPlayers.PlayerRemoving:Connect(leave)\nreturn Round","local Players = game:GetService(\"Players\")\nlocal Round = {}\nlocal alive = {}\nPlayers.PlayerRemoving:Connect(function(player)\n alive[player.UserId] = nil\n Round.winnerId = player.UserId\nend)\nreturn Round"],"RND-10":["local Results = {}\nfunction Results.winner(scores)\n local bestId, bestScore = nil, nil\n for id, score in pairs(scores) do\n  if bestScore == nil or score > bestScore or (score == bestScore and id < bestId) then\n   bestId, bestScore = id, score\n  end\n end\n return bestId\nend\nreturn Results","local Results = {}\nfunction Results.winner(scores)\n local bestId, bestScore = nil, -math.huge\n for id, score in pairs(scores) do\n  if score > bestScore then\n   bestId, bestScore = id, score\n  elseif score == bestScore and math.random(2) == 1 then\n   bestId = id\n  end\n end\n return bestId\nend\nreturn Results"],"RND-11":["local Results = {}\nlocal current, phase, finished = 0, \"Waiting\", false\nfunction Results.begin()\n if phase == \"Playing\" then return false end\n current += 1\n finished = false\n phase = \"Playing\"\n return current\nend\nfunction Results.finish(token, winnerId, award)\n if token ~= current or phase ~= \"Playing\" or finished then return false end\n finished = true\n phase = \"Results\"\n if winnerId ~= nil then award(winnerId) end\n return true\nend\nreturn Results","local Results = {}\nlocal current = 1\nlocal phase = \"Playing\"\nlocal finished = false\nfunction Results.finish(token, winnerId, award)\n award(winnerId)\n finished = true\n phase = \"Results\"\n return true\nend\nreturn Results"],"RND-12":["local Arena = {}\nlocal connections = {}\nlocal spawned = {}\nfunction Arena.attach(part)\n table.insert(connections, part.Touched:Connect(function(otherPart)\n  if otherPart then print(otherPart.Name) end\n end))\nend\nfunction Arena.addObject(instance) table.insert(spawned, instance) end\nfunction Arena.cleanup()\n for _, connection in ipairs(connections) do connection:Disconnect() end\n table.clear(connections)\n for _, instance in ipairs(spawned) do instance:Destroy() end\n table.clear(spawned)\nend\nreturn Arena","local Arena = {}\nlocal connections = {}\nlocal spawned = {}\nfunction Arena.attach(part)\n part.Touched:Connect(function(hit) print(hit.Name) end)\nend\nfunction Arena.addObject(instance) table.insert(spawned, instance) end\nfunction Arena.cleanup()\n connections = {}\n spawned = nil\nend\nreturn Arena"]}''')


def _normal(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9_]+", value.lower()))


def _words(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]{3,}", value.lower()))


def _jaccard(a: str, b: str) -> float:
    left, right = _words(a), _words(b)
    return len(left & right) / max(1, len(left | right))


def _score(task: dict, source: str):
    calls = []

    def check(code: str, *, strict: bool):
        calls.append((code, strict))
        return {"ok": True, "errors": []}

    score = score_answer(
        task, "```luau\n" + source + "\n```", luau_check=check
    )
    assert len(calls) == 1, task["id"]
    assert calls[0] == (source + "\n", False), task["id"]
    return score


def test_schema_and_balanced_categories():
    suite = load_suite(PATH)
    assert len(suite.tasks) == len(suite.runnable()) == 12
    assert len({t["id"] for t in suite.tasks}) == 12
    assert {t["id"] for t in suite.tasks} == set(PROBES)
    assert Counter(t["category"] for t in suite.tasks) == CATEGORIES
    assert all(t["id"] == f"RND-{i:02}" for i, t in enumerate(suite.tasks, 1))


def test_documented_contract_and_engine_names():
    for task in load_suite(PATH).tasks:
        tid = task["id"]
        assert task["run_mode"] == "automated" and task["split"] == "development", tid
        assert task["fixtures"] == [] and task["fixture_status"] == "not_needed", tid
        assert task["teaches"].strip() and task["edge_case"].strip(), tid
        assert len(task["expected_behavior"]) >= 2, tid
        assert "Roblox" in task["prompt"] and "fenced Luau" in task["prompt"], tid
        assert task["expected_sources"] and task["required_evidence"], tid
        assert set(task["source_urls"]) <= set(KNOWN_DOCS), tid
        assert all(url.startswith("https://create.roblox.com/docs/") for url in task["source_urls"]), tid
        assert set(task["engine_symbols"]) <= set(OFFICIAL_ENGINE), tid
        assert all(OFFICIAL_ENGINE[symbol] in task["source_urls"]
                   for symbol in task["engine_symbols"]), tid
        assert "static" in task["scoring_scope"], tid
        auto = task["auto"]
        assert auto.get("compile", True) and auto.get("code", True), tid
        assert auto["compile_mode"] == "exact", tid
        assert len(auto["require"]) >= 4 and len(auto["forbid"]) >= 1, tid
        checks = auto["require"] + auto["forbid"]
        assert len({rule["id"] for rule in checks}) == len(checks), tid
        assert all(rule["why"].strip() and rule["scope"] == "code" for rule in checks), tid
        assert all("re" in rule and re.compile(rule["re"]) for rule in checks), tid
        assert task["grader"]["type"] == "static"
        assert len(task["grader"]["checks"]) == 1 + len(checks), tid


def test_no_prompt_overlap_with_golden_holdout_or_prior_practice():
    ours = load_suite(PATH).tasks
    previous = [
        (name, row)
        for name in PRIOR
        if (DIR / name).is_file()
        for row in json.loads((DIR / name).read_text(encoding="utf-8"))
    ]
    prior_ids = {row["id"] for _, row in previous}
    assert not ({task["id"] for task in ours} & prior_ids)
    for index, task in enumerate(ours):
        for origin, old in previous + [
            ("current suite", row) for row in ours[:index]
        ]:
            assert _normal(task["prompt"]) != _normal(old["prompt"]), (task["id"], origin, old["id"])
            assert _normal(task["goal"]) != _normal(old["goal"]), (task["id"], origin, old["id"])
            assert _jaccard(task["prompt"], old["prompt"]) < 0.5, (task["id"], origin, old["id"])


def test_positive_and_negative_probes_through_real_scoring():
    good_passed = bad_rejected = 0
    for task in load_suite(PATH).tasks:
        good, bad = PROBES[task["id"]]
        positive, negative = _score(task, good), _score(task, bad)
        assert positive.blocks == negative.blocks == 1, task["id"]
        assert positive.passed, (task["id"], positive.reasons)
        assert not negative.passed, (task["id"], "negative probe passed")
        assert any(check.id.startswith(("require:", "forbid:")) and not check.ok
                   for check in negative.checks), task["id"]
        good_passed += 1
        bad_rejected += 1
    assert (good_passed, bad_rejected) == (12, 12)


def test_comment_only_and_forged_explanations_do_not_pass():
    for task in load_suite(PATH).tasks:
        good, _ = PROBES[task["id"]]
        answer = "\n".join("-- " + line for line in good.splitlines())
        assert not _score(task, answer).passed, task["id"]


def test_real_compiler_rejection_is_still_respected():
    for task in load_suite(PATH).tasks:
        good, _ = PROBES[task["id"]]
        result = score_answer(
            task, "```luau\n" + good + "\n```",
            luau_check=lambda code, strict=False: {
                "ok": False,
                "errors": [{"kind": "SyntaxError", "line": 1, "message": "bad syntax"}],
            },
        )
        assert not result.passed, task["id"]
        assert any(check.id.startswith("luau_check") and not check.ok for check in result.checks), task["id"]
