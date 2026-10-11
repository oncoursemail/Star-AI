"""Headless Roblox build-and-test: source folder -> place file -> private test experience -> Luau test -> logs.

No Studio and no screen: this runs on the PC or on a Linux server with only the API key.

    python -m star.roblox_pipeline --source examples/roblox-test-place            # build + check the key
    python -m star.roblox_pipeline --set-test-experience <universe> <place>       # the owner chooses it
    python -m star.roblox_pipeline --source examples/roblox-test-place --publish-and-test

Each step reports what happened; the run stops at the first step that cannot be done and says exactly
what the owner has to do. `--publish-and-test` typed by the owner is the approval for that one run;
the model has no way to start this command (its own requests wait in the action list).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from .roblox_cloud import NO_EXPERIENCE, CloudError, RobloxCloud
from .roblox_place import BuildError, Build, build_place, rojo_build

RESULT_MARK = "STAR_TEST_RESULT "
# Runs inside the published place on Roblox's servers. Every ModuleScript under
# ServerScriptService.Tests whose name ends in ".spec" returns a table of named functions.
TEST_HARNESS = r"""
local HttpService = game:GetService("HttpService")
local ServerScriptService = game:GetService("ServerScriptService")

local report = { passed = 0, failed = 0, cases = {} }
local function record(name, ok, message)
	if ok then
		report.passed += 1
	else
		report.failed += 1
	end
	table.insert(report.cases, { name = name, ok = ok, message = if ok then nil else tostring(message) })
end

local folder = ServerScriptService:FindFirstChild("Tests")
if not folder then
	record("ServerScriptService.Tests", false, "the published place has no Tests folder")
else
	local modules = {}
	for _, item in ipairs(folder:GetDescendants()) do
		if item:IsA("ModuleScript") and string.sub(item.Name, -5) == ".spec" then
			table.insert(modules, item)
		end
	end
	table.sort(modules, function(a, b)
		return a:GetFullName() < b:GetFullName()
	end)
	for _, module in ipairs(modules) do
		local loaded, cases = pcall(require, module)
		if not loaded or type(cases) ~= "table" then
			record(module.Name, false, if loaded then "the spec must return a table of functions" else cases)
		else
			local names = {}
			for name, case in pairs(cases) do
				if type(name) == "string" and type(case) == "function" then
					table.insert(names, name)
				end
			end
			table.sort(names)
			for _, name in ipairs(names) do
				local ok, message = pcall(cases[name])
				record(module.Name .. ": " .. name, ok, message)
			end
		end
	end
end

print("STAR_TEST_RESULT " .. HttpService:JSONEncode(report))
return report
"""

OWNER_STEPS = (
    "1. Open Roblox Studio signed in as STAR's own Roblox account (the account the API key belongs to).\n"
    "2. New > Baseplate, then File > Publish to Roblox, create a NEW experience (for example 'STAR Test "
    "Place') and leave it Private.\n"
    "3. On create.roblox.com > Creations, open the experience's ... menu: Copy Universe ID and Copy Start "
    "Place ID.\n"
    "4. In STAR: Settings > Roblox > Test experience, enter both numbers and press Use this experience "
    "(or run: python -m star.roblox_pipeline --set-test-experience <universe> <place>).")


def summarize_test(record: dict) -> dict | None:
    """The harness report: from the task's returned value, else from its marked log line."""
    output = record.get("output")
    results = output.get("results") if isinstance(output, dict) else None
    candidates = list(results) if isinstance(results, list) else []
    for line in reversed(record.get("logs") or []):
        position = line.find(RESULT_MARK)
        if position >= 0:
            try:
                candidates.append(json.loads(line[position + len(RESULT_MARK):]))
            except ValueError:
                pass
    for item in candidates:
        if isinstance(item, dict) and type(item.get("passed")) is int and type(item.get("failed")) is int:
            cases = item.get("cases") if isinstance(item.get("cases"), list) else []
            return {"passed": item["passed"], "failed": item["failed"],
                    "cases": [{"name": str(case.get("name"))[:160], "ok": case.get("ok") is True,
                               **({"message": str(case.get("message"))[:400]} if case.get("message") else {})}
                              for case in cases if isinstance(case, dict)][:200]}
    return None


def run_pipeline(cloud: RobloxCloud, source: Path, *, publish_and_test: bool = False,
                 script: str = TEST_HARNESS, builder: str = "builtin", home: Path | None = None) -> dict:
    steps: list[dict] = []
    report = {"ok": False, "steps": steps, "stopped_at": "", "owner_action": ""}

    def stop(step: str, why: str, owner: str = "") -> dict:
        steps.append({"step": step, "ok": False, "detail": why})
        report.update(stopped_at=step, owner_action=owner)
        return report

    try:
        build: Build = rojo_build(home, source) if builder == "rojo" else build_place(source)
    except (BuildError, OSError) as exc:
        return stop("build", str(exc))
    steps.append({"step": "build", "ok": True, "builder": build.builder, "bytes": len(build.data),
                  "sha256": build.sha256, "instances": build.instances, "files": len(build.files)})

    check = cloud.check_key()
    if check["state"] == "no_key":
        return stop("key", check["message"], "Create an Open Cloud API key on STAR's own Roblox account and "
                    "paste it in Settings > Roblox (or save it as ROBLOX_OPEN_CLOUD_API_KEY=<key> in the key file).")
    if check["state"] != "valid":
        owner = ("In the Creator Dashboard, add to the key: " + ", ".join(check.get("missing") or [])
                 if check["state"] == "missing_permission" else "")
        return stop("key", check["message"], owner)
    steps.append({"step": "key", "ok": True, "state": "valid", "account": check.get("account"),
                  "calls": check.get("calls")})

    try:
        target = cloud.guard_write()
    except CloudError as exc:
        return stop("test experience", str(exc), OWNER_STEPS if str(exc) == NO_EXPERIENCE else "")
    steps.append({"step": "test experience", "ok": True, "universe_id": target["universe_id"],
                  "place_id": target["place_id"], "visibility": target["visibility"]})

    if not publish_and_test:
        report.update(ok=True, stopped_at="publish",
                      owner_action="Ready. Run again with --publish-and-test to publish to the test "
                                   "experience and run the tests.")
        return report
    try:
        published = cloud.publish_place(build.data, xml=True, version_type="Saved")
    except CloudError as exc:
        return stop("publish", str(exc))
    steps.append({"step": "publish", "ok": True, **published})

    try:
        record = cloud.run_luau(script, version=published["version"])
    except CloudError as exc:
        return stop("run test", str(exc))
    summary = summarize_test(record)
    finished = record.get("state") == "COMPLETE" and not record.get("error")
    steps.append({"step": "run test", "ok": finished, **record})
    if not finished:
        report["stopped_at"] = "run test"
        return report
    steps.append({"step": "result", "ok": bool(summary) and summary["failed"] == 0, "summary": summary})
    report["ok"] = bool(summary) and summary["failed"] == 0
    return report


def _print(value) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, indent=1) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Headless Roblox build and test for STAR")
    parser.add_argument("--source", type=Path, help="folder with ServerScriptService/, ReplicatedStorage/, ...")
    parser.add_argument("--home", type=Path, help="STAR data folder (default: the desktop app's)")
    parser.add_argument("--builder", choices=("builtin", "rojo"), default="builtin")
    parser.add_argument("--out", type=Path, help="also write the built place file here")
    parser.add_argument("--set-test-experience", nargs=2, metavar=("UNIVERSE", "PLACE"))
    parser.add_argument("--publish-and-test", action="store_true",
                        help="publish to the test experience and run the tests (the owner's approval for this run)")
    args = parser.parse_args(argv)
    if args.home is None:
        from .desktop_core import app_data
        args.home = app_data()
    cloud = RobloxCloud(home=args.home)
    try:
        if args.set_test_experience:
            ids = [int(value) if re.fullmatch(r"\d{1,19}", value) else value for value in args.set_test_experience]
            _print({"test_experience": cloud.set_test_experience(*ids, human_approved=True)})
        if args.source is None:
            _print(cloud.status() if args.set_test_experience else cloud.check_key())
            return 0
        if args.out is not None:
            args.out.write_bytes(build_place(args.source).data)
        report = run_pipeline(cloud, args.source, publish_and_test=args.publish_and_test,
                              builder=args.builder, home=args.home)
        _print(report)
        return 0 if report["ok"] else 1
    except (CloudError, BuildError, PermissionError) as exc:
        _print({"ok": False, "error": str(exc)})
        return 1
    finally:
        cloud.close()


if __name__ == "__main__":
    raise SystemExit(main())
