"""Look at STAR Test Place from outside Studio, through Roblox Open Cloud (star/roblox_cloud.py).

Run it before and after "Publish to Roblox" in Studio: the place's update time and the version number that
a server-side Luau task runs in must both move, and the task reports what the saved place contains. The
Luau task only reads (it counts instances); it writes no data store and changes no place. The key is read
by star/roblox_cloud.py and is never printed.

    python scripts/studio_remote_verify.py --home <STAR data folder> [--out file.json] [--no-luau]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from star.roblox_cloud import CloudError, RobloxCloud  # noqa: E402
from star.studio_remote import TEST_PLACE_ID, TEST_UNIVERSE_ID  # noqa: E402

CHECK = """local HttpService = game:GetService("HttpService")
local function count(instance)
	return if instance then #instance:GetDescendants() else -1
end
local lobby = workspace:FindFirstChild("StarLobby")
local remotes = game:GetService("ReplicatedStorage"):FindFirstChild("StarShopRemotes")
local shop = game:GetService("StarterGui"):FindFirstChild("StarShop")
local server = game:GetService("ServerScriptService"):FindFirstChild("StarShopServer")
local anchored, parts = 0, 0
if lobby then
	for _, item in ipairs(lobby:GetDescendants()) do
		if item:IsA("BasePart") then
			parts += 1
			if item.Anchored then
				anchored += 1
			end
		end
	end
end
local facts = {
	placeId = game.PlaceId, gameId = game.GameId, placeVersion = game.PlaceVersion,
	lobbyDescendants = count(lobby), lobbyParts = parts, lobbyAnchored = anchored,
	lobbySpawn = lobby ~= nil and lobby:FindFirstChild("LobbySpawn") ~= nil,
	purchaseRequest = remotes ~= nil and remotes:FindFirstChild("PurchaseRequest") ~= nil
		and remotes.PurchaseRequest:IsA("RemoteEvent"),
	purchaseResult = remotes ~= nil and remotes:FindFirstChild("PurchaseResult") ~= nil,
	shopDescendants = count(shop),
	shopLayouts = if shop then #shop:QueryDescendants("UIListLayout") else -1,
	shopClient = shop ~= nil and shop:FindFirstChild("ShopClient") ~= nil and shop.ShopClient:IsA("LocalScript"),
	serverScript = server ~= nil and server:IsA("Script"),
	clockTime = game:GetService("Lighting").ClockTime,
}
print("STAR_VERIFY " .. HttpService:JSONEncode(facts))
return HttpService:JSONEncode(facts)
"""


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--home", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--no-luau", action="store_true", help="only read the place's update time")
    chosen = parser.parse_args(arguments)
    cloud = RobloxCloud(home=Path(chosen.home).expanduser())
    report: dict = {"ok": False}
    try:
        check = cloud.check_key()
        report["key"] = {"state": check.get("state"), "missing": check.get("missing")}
        if check.get("state") != "valid":
            raise CloudError("The key check did not pass: " + str(check.get("message")))
        target = cloud.guard_write()            # owner, private, not denied, place in the experience: asked again now
        if (target["universe_id"], target["place_id"]) != (TEST_UNIVERSE_ID, TEST_PLACE_ID):
            raise CloudError("The chosen test experience is not STAR Test Place")
        report["experience"] = {key: target.get(key) for key in ("universe_id", "place_id", "visibility", "name")}
        report["place"] = cloud.place(TEST_UNIVERSE_ID, TEST_PLACE_ID)["metadata"]
        if not chosen.no_luau:
            record = cloud.run_luau(CHECK, wait_seconds=240.0)
            facts = None
            results = (record.get("output") or {}).get("results") if isinstance(record.get("output"), dict) else None
            if isinstance(results, list) and results and isinstance(results[0], str):
                try:                         # seen 2026-10-11: output = {"results": ["<the returned text>"]}
                    facts = json.loads(results[0])
                except ValueError:
                    facts = None
            report["luau"] = {"state": record.get("state"), "version": record.get("version"), "http": record.get("http"),
                              "error": record.get("error"), "task_error": record.get("task_error"), "facts": facts,
                              "output": record.get("output") if facts is None else None}
            report["ok"] = record.get("state") == "COMPLETE" and facts is not None
        else:
            report["ok"] = True
    except CloudError as error:
        report["problem"] = str(error)
    text = json.dumps(report, indent=1, default=str)
    print(text)
    if chosen.out:
        Path(chosen.out).write_text(text, encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
