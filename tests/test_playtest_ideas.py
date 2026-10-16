import json

from star import playtest_ideas as ideas
from star import playtest_learning as pl


def idea(name="LavaDash", difficulty="simple", hook="Race across sinking stones before the lava rises.", **extra):
    base = {"name": name, "difficulty": difficulty, "hook": hook,
            "brief": "Stones over lava lead to a goal pad.", "rules": ["Lava kills.", "Reach the goal."],
            "win": "Stand on Goal.", "contract": ["Stones are Parts named Stage1..Stage4; the finish is a Part named Goal."],
            "checks": [{"do": "route", "prefix": "Stage", "target": "Goal", "min": 4}]}
    return base | extra


class Brain:
    def __init__(self, text):
        self.text, self.calls = text, []

    def __call__(self, messages):
        self.calls.append(messages)
        return {"ok": True, "text": self.text, "seconds": 2.0}


def test_check_idea_validates_spec_and_names():
    good, problems = ideas.check_idea(idea())
    assert good and not problems and good["spec"]["kind"] == "idea-simple" and "Win: Stand on Goal." in good["spec"]["brief"]
    bad, problems = ideas.check_idea(idea(checks=[{"do": "reach", "target": "Castle"}]))
    assert bad is None and any("Castle" in p for p in problems)
    bad, problems = ideas.check_idea(idea(difficulty="medium", checks=[{"do": "fly"}]))
    assert bad is None and len(problems) >= 2


def test_invent_dedupes_against_specs_and_ledger(tmp_path):
    specs, _ = pl.load_specs(pl.SPECS_DIR)
    answer = json.dumps([
        idea(),
        idea(name="LavaDashToo"),                                    # same hook/brief: duplicate
        idea(name="StageObby", hook="Jump floating platforms."),     # same name as a shipped spec
        idea(name="ShopRounds", difficulty="hard", hook="Earn coins in timed rounds, then spend them.",
             brief="Rounds of coin hunting with a shop between them.", win="Own the SpeedCoil.",
             contract=["Coins are Parts named Coin worth 5 into leaderstats Coins; BuyPad sells a Tool named SpeedCoil "
                       "for 10."],
             checks=[{"do": "collect", "name": "Coin", "stat": "Coins", "min": 2, "each": 5},
                     {"do": "touch", "target": "BuyPad"}, {"do": "expect_item", "item": "SpeedCoil"}]),
        {"name": "Broken"},
    ])
    brain = Brain("Here you go:\n" + answer)
    result = ideas.invent(brain, tmp_path, specs, count=4, log=lambda *_: None)
    assert [a["name"] for a in result["added"]] == ["LavaDash", "ShopRounds"]
    assert {d["name"] for d in result["duplicates"]} == {"LavaDashToo", "StageObby"}
    assert result["refused"][0]["name"] == "Broken"
    assert "StageObby" in brain.calls[0][-1]["content"]           # STAR is told what exists
    again = ideas.invent(Brain(json.dumps([idea()])), tmp_path, specs, count=2, log=lambda *_: None)
    assert not again["added"] and again["duplicates"][0]["like"] == "LavaDash"


def report(name, passed, builds, legs):
    its = [{"index": i + 1, "report": {"passed": False, "checks": 1}} for i in range(builds - 1)]
    its.append({"index": builds, "report": {"passed": passed, "checks": 1},
                "robot": {"checks": [{"do": "route", "ok": passed, "facts": {"legs": legs}}]}})
    return {"game": name, "run": "r1", "passed": passed, "first_pass": passed and builds == 1, "iterations": its}


def test_signals_rating_and_build_list(tmp_path):
    ledger = {"ideas": []}
    for name, difficulty in (("LavaDash", "simple"), ("ShopRounds", "hard"), ("Fresh", "simple"), ("Stuck", "simple")):
        found, _ = ideas.check_idea(idea(name=name, difficulty=difficulty, hook=f"{name} hook words {name}"))
        ledger["ideas"].append(found | {"id": name, "runs": [], "rating": None})
    ideas.save_ledger(tmp_path, ledger)
    legs = [{"seconds": 20, "jumps": 2, "stuck": 0}, {"seconds": 20, "jumps": 1, "stuck": 1}]
    recorded = ideas.record_results(tmp_path, [report("LavaDash", True, 1, legs), report("ShopRounds", True, 2, legs),
                                               report("Stuck", False, 3, legs)])
    assert recorded == 3
    by = {i["name"]: i for i in ideas.load_ledger(tmp_path)["ideas"]}
    s = by["ShopRounds"]["runs"][0]["signals"]
    assert s == {"passed": True, "first_pass": False, "builds": 2, "failed_playtests": 1, "checks": 1,
                 "time_to_win": 40.0, "jumps": 3, "stuck_points": 1}
    assert by["LavaDash"]["rating"] == round(1 + 40 / 120 + 0.3 - 0.1, 3)
    assert by["ShopRounds"]["rating"] > by["LavaDash"]["rating"] and by["Stuck"]["rating"] == 0.0
    assert [s["name"] for s in ideas.build_list(tmp_path)] == ["Fresh", "ShopRounds", "LavaDash"]


def test_ideas_need_both_switches(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv(pl.SWITCH, "1")
    monkeypatch.delenv(ideas.IDEAS_SWITCH, raising=False)
    monkeypatch.setenv("STAR_PLAYTEST_BRAIN_URL", "http://brain.invalid:8080")
    assert pl.main(["ideas", str(pl.SPECS_DIR), "--ideas-dir", str(tmp_path)]) == 3
    assert "switched off" in capsys.readouterr().out
