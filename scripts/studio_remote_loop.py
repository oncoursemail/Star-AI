"""The real build loop on STAR Test Place, through STAR's own code path, against the STAR Studio server.

    star/studio.py (MCP stdio, e.g. over SSH)  ->  star/studio_remote.py (pin to STAR Test Place)
    ->  star/studio_loop.py (sandbox rule, change journal, undo)  ->  Roblox's official Studio connector

What it does, in order: read the instance tree; build a small lobby (anchored parts, a spawn, lighting), a
shop panel made of native layout objects, two RemoteEvents, a server script that validates a purchase
request and a local script that sends it; run a playtest and read the output; report every change with
how to undo it. It never saves and never publishes (that is a separate, deliberate step in Studio).

    python scripts/studio_remote_loop.py --home <STAR data folder> --out <folder>             # reads only
    python scripts/studio_remote_loop.py --home ... --out ... --build                          # build + playtest
    python scripts/studio_remote_loop.py --home ... --out ... --playtest                       # playtest only
    python scripts/studio_remote_loop.py --home ... --out ... --build --undo                   # ...and take it back
    python scripts/studio_remote_loop.py --home ... --out ... --remove                         # remove earlier runs' work by name

`--capture` takes a JSON list: a command that writes a PNG of the true display to standard output (for
example ssh ... import -window root png:-). The connector's own screen_capture is not used for judging.
The target and the launcher command come from `python -m star.studio_remote --home ... --set-...`.
It refuses to change anything unless the open place is STAR Test Place (both ids) and the rule allows it.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import secrets
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from star import studio, studio_loop, studio_remote  # noqa: E402

SERVICES = ["Workspace", "Lighting", "ReplicatedStorage", "ServerScriptService", "ServerStorage", "StarterGui",
            "StarterPack", "StarterPlayer"]
ITEMS = [("sword", "Training Sword", 25), ("shield", "Wooden Shield", 40), ("potion", "Speed Potion", 10)]

LOBBY = """local old = workspace:FindFirstChild("StarLobby")
local kept = if old then old:GetAttributes() else {}
if old then
	old:Destroy()
end
local lobby = Instance.new("Model")
lobby.Name = "StarLobby"
for key, value in pairs(kept) do      -- the record of what Lighting was before the first build survives a rebuild
	lobby:SetAttribute(key, value)
end
local function part(name, size, position, color, material)
	local p = Instance.new("Part")
	p.Name = name
	p.Anchored = true
	p.Size = size
	p.Position = position
	p.Color = color
	p.Material = material or Enum.Material.SmoothPlastic
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.Parent = lobby
	return p
end
local sand, wall, wood = Color3.fromRGB(205, 190, 160), Color3.fromRGB(206, 198, 184), Color3.fromRGB(110, 78, 52)
-- The baseplate's top is y = 0. The floor is 1.5 thick so it covers the template's 1-high spawn pad.
part("Floor", Vector3.new(48, 1.5, 48), Vector3.new(0, 0.75, 0), sand, Enum.Material.WoodPlanks)
part("WallNorth", Vector3.new(48, 12, 1), Vector3.new(0, 7.5, -23.5), wall)
part("WallWest", Vector3.new(1, 12, 46), Vector3.new(-23.5, 7.5, 0), wall)
part("WallEast", Vector3.new(1, 12, 46), Vector3.new(23.5, 7.5, 0), wall)
part("WallSouthLeft", Vector3.new(18, 12, 1), Vector3.new(-15, 7.5, 23.5), wall)
part("WallSouthRight", Vector3.new(18, 12, 1), Vector3.new(15, 7.5, 23.5), wall)
part("DoorLintel", Vector3.new(12, 3, 1), Vector3.new(0, 12, 23.5), wall)
part("ShopCounter", Vector3.new(14, 3, 3), Vector3.new(0, 3, -17), wood, Enum.Material.Wood)
part("BenchWest", Vector3.new(2, 1.5, 10), Vector3.new(-18, 2.25, 4), wood, Enum.Material.Wood)
part("BenchEast", Vector3.new(2, 1.5, 10), Vector3.new(18, 2.25, 4), wood, Enum.Material.Wood)
for _, x in ipairs({ -20, 20 }) do
	part("LampPost", Vector3.new(1, 9, 1), Vector3.new(x, 6, -20), Color3.fromRGB(60, 60, 66), Enum.Material.Metal)
	local head = part("LampHead", Vector3.new(2, 1, 2), Vector3.new(x, 11, -20), Color3.fromRGB(255, 226, 160), Enum.Material.Neon)
	local light = Instance.new("PointLight")
	light.Range = 30
	light.Brightness = 1.4
	light.Color = Color3.fromRGB(255, 226, 170)
	light.Parent = head
end
local sign = part("ShopSign", Vector3.new(14, 3, 0.5), Vector3.new(0, 10, -22.75), Color3.fromRGB(28, 32, 48))
local face = Instance.new("SurfaceGui")
face.Name = "SignFace"
face.Face = Enum.NormalId.Back
face.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
face.PixelsPerStud = 40
face.Parent = sign
local label = Instance.new("TextLabel")
label.Name = "Title"
label.Size = UDim2.fromScale(1, 1)
label.BackgroundTransparency = 1
label.Text = "STAR SHOP"
label.TextScaled = true
label.FontFace = Font.fromEnum(Enum.Font.GothamBold)
label.TextColor3 = Color3.fromRGB(255, 226, 160)
label.Parent = face
local pad = Instance.new("SpawnLocation")
pad.Name = "LobbySpawn"
pad.Anchored = true
pad.Size = Vector3.new(8, 1, 8)
pad.Position = Vector3.new(0, 2, 8)
pad.Neutral = true
pad.Duration = 0
pad.Color = Color3.fromRGB(90, 120, 255)
pad.Material = Enum.Material.SmoothPlastic
pad.TopSurface = Enum.SurfaceType.Smooth
pad.Parent = lobby
lobby.Parent = workspace
return "lobby parts: " .. #lobby:GetChildren()
"""

# Property changes on things that already exist. The previous values are kept as attributes on the lobby
# model, so they can be put back by hand or by UNDO_SETTINGS.
SETTINGS = """local Lighting = game:GetService("Lighting")
local lobby = workspace:FindFirstChild("StarLobby")
local function keep(key, value)
	if lobby and lobby:GetAttribute(key) == nil then
		lobby:SetAttribute(key, value)
	end
end
keep("Before_ClockTime", Lighting.ClockTime)
keep("Before_Brightness", Lighting.Brightness)
keep("Before_Ambient", Lighting.Ambient)
keep("Before_OutdoorAmbient", Lighting.OutdoorAmbient)
Lighting.ClockTime = 15.5
Lighting.Brightness = 2
Lighting.Ambient = Color3.fromRGB(70, 70, 80)
Lighting.OutdoorAmbient = Color3.fromRGB(140, 140, 150)
local changed = {}
for _, item in ipairs(workspace:GetChildren()) do
	if item:IsA("SpawnLocation") and item.Enabled then      -- the template's own spawn pad, now under the floor
		keep("Before_TemplateSpawnEnabled", true)
		item.Enabled = false
		table.insert(changed, item:GetFullName())
	end
end
local camera = workspace.CurrentCamera
if camera then
	camera.CFrame = CFrame.lookAt(Vector3.new(30, 44, 50), Vector3.new(0, 2, -2))
end
local was = {}
for key, value in pairs(if lobby then lobby:GetAttributes() else {}) do
	table.insert(was, key .. "=" .. tostring(value))
end
table.sort(was)
return "lighting set; template spawns switched off now: " .. table.concat(changed, ", ") .. "; before the first build: " .. table.concat(was, "; ")
"""

UNDO_SETTINGS = """local Lighting = game:GetService("Lighting")
local lobby = workspace:FindFirstChild("StarLobby")
local put = 0
if lobby then
	for key, property in pairs({ Before_ClockTime = "ClockTime", Before_Brightness = "Brightness",
		Before_Ambient = "Ambient", Before_OutdoorAmbient = "OutdoorAmbient" }) do
		local value = lobby:GetAttribute(key)
		if value ~= nil then
			Lighting[property] = value
			put += 1
		end
	end
	if lobby:GetAttribute("Before_TemplateSpawnEnabled") then
		for _, item in ipairs(workspace:GetChildren()) do
			if item:IsA("SpawnLocation") and not item.Enabled then
				item.Enabled = true
				put += 1
			end
		end
	end
end
workspace:SetAttribute("StarRun", nil)
return "settings put back: " .. put
"""

INTERFACE = """local StarterGui = game:GetService("StarterGui")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
for _, pair in ipairs({ { StarterGui, "StarShop" }, { ReplicatedStorage, "StarShopRemotes" } }) do
	local old = pair[1]:FindFirstChild(pair[2])
	if old then
		old:Destroy()
	end
end
local remotes = Instance.new("Folder")
remotes.Name = "StarShopRemotes"
for _, name in ipairs({ "PurchaseRequest", "PurchaseResult" }) do
	local remote = Instance.new("RemoteEvent")
	remote.Name = name
	remote.Parent = remotes
end
remotes.Parent = ReplicatedStorage

local function corner(parent, radius)
	local c = Instance.new("UICorner")
	c.CornerRadius = UDim.new(0, radius)
	c.Parent = parent
end
local function stroke(parent, color, thickness)
	local s = Instance.new("UIStroke")
	s.Color = color
	s.Thickness = thickness
	s.ApplyStrokeMode = Enum.ApplyStrokeMode.Border
	s.Parent = parent
end
local function text(class, name, order, height, content, size, color, bold)
	local t = Instance.new(class)
	t.Name = name
	t.LayoutOrder = order
	t.Size = UDim2.new(1, 0, 0, height)
	t.BackgroundTransparency = 1
	t.Text = content
	t.TextSize = size
	t.TextColor3 = color
	t.TextWrapped = true
	t.FontFace = Font.fromEnum(if bold then Enum.Font.GothamBold else Enum.Font.Gotham)
	return t
end

local gui = Instance.new("ScreenGui")
gui.Name = "StarShop"
gui.ResetOnSpawn = false
gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
gui:SetAttribute("SelfTest", true)

local panel = Instance.new("Frame")
panel.Name = "Panel"
panel.AnchorPoint = Vector2.new(1, 0.5)
panel.Position = UDim2.new(1, -24, 0.5, 0)
panel.Size = UDim2.new(0.24, 0, 0, 0)
panel.AutomaticSize = Enum.AutomaticSize.Y
panel.BackgroundColor3 = Color3.fromRGB(24, 27, 38)
panel.BorderSizePixel = 0
panel.Parent = gui
corner(panel, 14)
stroke(panel, Color3.fromRGB(90, 120, 255), 2)
local limit = Instance.new("UISizeConstraint")
limit.MinSize = Vector2.new(260, 0)
limit.MaxSize = Vector2.new(400, 560)
limit.Parent = panel
local padding = Instance.new("UIPadding")
padding.PaddingTop = UDim.new(0, 16)
padding.PaddingBottom = UDim.new(0, 16)
padding.PaddingLeft = UDim.new(0, 16)
padding.PaddingRight = UDim.new(0, 16)
padding.Parent = panel
local column = Instance.new("UIListLayout")
column.FillDirection = Enum.FillDirection.Vertical
column.HorizontalAlignment = Enum.HorizontalAlignment.Center
column.SortOrder = Enum.SortOrder.LayoutOrder
column.Padding = UDim.new(0, 10)
column.Parent = panel

text("TextLabel", "Title", 1, 36, "STAR Shop", 26, Color3.fromRGB(255, 255, 255), true).Parent = panel
text("TextLabel", "Balance", 2, 24, "Coins: --", 18, Color3.fromRGB(255, 214, 110), false).Parent = panel

local items = Instance.new("Frame")
items.Name = "Items"
items.LayoutOrder = 3
items.Size = UDim2.new(1, 0, 0, 0)
items.AutomaticSize = Enum.AutomaticSize.Y
items.BackgroundTransparency = 1
items.Parent = panel
local rows = Instance.new("UIListLayout")
rows.FillDirection = Enum.FillDirection.Vertical
rows.SortOrder = Enum.SortOrder.LayoutOrder
rows.Padding = UDim.new(0, 8)
rows.Parent = items
for index, item in ipairs({ %(items)s }) do
	local button = text("TextButton", "Item_" .. item[1], index, 52, item[2] .. "   " .. item[3] .. " coins", 18,
		Color3.fromRGB(255, 255, 255), false)
	button.BackgroundTransparency = 0
	button.BackgroundColor3 = Color3.fromRGB(44, 50, 72)
	button.AutoButtonColor = true
	button:SetAttribute("ItemId", item[1])
	button:SetAttribute("Price", item[3])
	corner(button, 10)
	stroke(button, Color3.fromRGB(70, 80, 110), 1)
	button.Parent = items
end

text("TextLabel", "Status", 4, 44, "Pick an item", 16, Color3.fromRGB(170, 180, 200), false).Parent = panel
gui.Parent = StarterGui
return "interface built: " .. #panel:GetDescendants() .. " objects under the panel"
""" % {"items": ", ".join(f'{{ "{key}", "{name}", {price} }}' for key, name, price in ITEMS)}

SERVER = """-- STAR Test Place: shop server. Every purchase request is checked here; the client is never trusted.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local remotes = ReplicatedStorage:WaitForChild("StarShopRemotes")
local purchaseRequest = remotes:WaitForChild("PurchaseRequest")
local purchaseResult = remotes:WaitForChild("PurchaseResult")

local CATALOG = {
%(catalog)s
}
local START_COINS = 100
local MAX_QUANTITY = 10
local MIN_SECONDS_BETWEEN_REQUESTS = 0.25

local lastRequest = {}
local owned = {}

local function setUp(player)
	if player:FindFirstChild("leaderstats") then
		return
	end
	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"
	local coins = Instance.new("IntValue")
	coins.Name = "Coins"
	coins.Value = START_COINS
	coins.Parent = stats
	stats.Parent = player
	owned[player] = {}
end

local function reject(player, reason)
	print("[StarShop] rejected request from " .. player.Name .. ": " .. reason)
	purchaseResult:FireClient(player, false, reason)
end

purchaseRequest.OnServerEvent:Connect(function(player, itemId, quantity)
	local now = os.clock()
	if lastRequest[player] and now - lastRequest[player] < MIN_SECONDS_BETWEEN_REQUESTS then
		return reject(player, "too many requests")
	end
	lastRequest[player] = now
	if typeof(itemId) ~= "string" or #itemId > 32 then
		return reject(player, "bad item id")
	end
	local item = CATALOG[itemId]
	if not item then
		return reject(player, "unknown item")
	end
	if typeof(quantity) ~= "number" or quantity ~= quantity or quantity %% 1 ~= 0
		or quantity < 1 or quantity > MAX_QUANTITY then
		return reject(player, "bad quantity")
	end
	local stats = player:FindFirstChild("leaderstats")
	local coins = stats and stats:FindFirstChild("Coins")
	if not coins or not owned[player] then
		return reject(player, "no wallet")
	end
	local cost = item.price * quantity
	if coins.Value < cost then
		return reject(player, "not enough coins")
	end
	coins.Value -= cost
	owned[player][itemId] = (owned[player][itemId] or 0) + quantity
	print(string.format("[StarShop] purchase ok: %%s bought %%d x %%s for %%d coins, %%d left",
		player.Name, quantity, itemId, cost, coins.Value))
	purchaseResult:FireClient(player, true, item.name, coins.Value)
end)

Players.PlayerAdded:Connect(setUp)
for _, player in ipairs(Players:GetPlayers()) do
	setUp(player)
end
Players.PlayerRemoving:Connect(function(player)
	lastRequest[player] = nil
	owned[player] = nil
end)
print("[StarShop] server ready, run " .. tostring(workspace:GetAttribute("StarRun")))
""" % {"catalog": "\n".join(f'\t{key} = {{ name = "{name}", price = {price} }},' for key, name, price in ITEMS)}

CLIENT = """-- STAR Test Place: shop client. It only asks; the server decides.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local player = Players.LocalPlayer
local gui = script.Parent
local panel = gui:WaitForChild("Panel")
local items = panel:WaitForChild("Items")
local status = panel:WaitForChild("Status")
local balance = panel:WaitForChild("Balance")
local remotes = ReplicatedStorage:WaitForChild("StarShopRemotes")
local purchaseRequest = remotes:WaitForChild("PurchaseRequest")
local purchaseResult = remotes:WaitForChild("PurchaseResult")

local function showCoins(value)
	balance.Text = "Coins: " .. tostring(value)
end

task.spawn(function()
	local stats = player:WaitForChild("leaderstats", 10)
	local coins = stats and stats:WaitForChild("Coins", 10)
	if coins then
		showCoins(coins.Value)
		coins.Changed:Connect(showCoins)
	end
end)

for _, button in ipairs(items:GetChildren()) do
	if button:IsA("TextButton") then
		button.Activated:Connect(function()
			status.Text = "Asking the server..."
			purchaseRequest:FireServer(button:GetAttribute("ItemId"), 1)
		end)
	end
end

purchaseResult.OnClientEvent:Connect(function(ok, detail, coinsLeft)
	if ok then
		status.Text = "Bought " .. tostring(detail)
		print("[StarShop] client: bought " .. tostring(detail) .. ", coins left " .. tostring(coinsLeft))
	else
		status.Text = "Not bought: " .. tostring(detail)
		print("[StarShop] client: refused (" .. tostring(detail) .. ")")
	end
end)

print("[StarShop] client ready")

if gui:GetAttribute("SelfTest") then
	-- Four requests for the playtest check: one valid, three the server must refuse.
	task.wait(2)
	purchaseRequest:FireServer("sword", 1)
	task.wait(0.6)
	purchaseRequest:FireServer("castle", 1)
	task.wait(0.6)
	purchaseRequest:FireServer("potion", 9999)
	task.wait(0.6)
	purchaseRequest:FireServer("shield", 10)
end
"""

SCRIPTS = [
    {"path": "game.ServerScriptService.StarShopServer", "class_name": "Script", "source": SERVER},
    {"path": "game.StarterGui.StarShop.ShopClient", "class_name": "LocalScript", "source": CLIENT},
]
# Studio's output can still hold the lines of an earlier playtest, word for word the same. Each playtest
# therefore gets a run mark (an attribute on Workspace) that the server script prints first; only what
# follows this run's mark is judged.
MARK_RUN = """workspace:SetAttribute("StarRun", "%s")
return "run marked"
"""
RUN_LINE = "[StarShop] server ready, run %s"
REMOVE = """local removed = {}
for _, pair in ipairs({ { workspace, "StarLobby" }, { game:GetService("ReplicatedStorage"), "StarShopRemotes" },
	{ game:GetService("StarterGui"), "StarShop" }, { game:GetService("ServerScriptService"), "StarShopServer" } }) do
	local item = pair[1]:FindFirstChild(pair[2])
	if item then
		table.insert(removed, item:GetFullName())
		item:Destroy()
	end
end
workspace:SetAttribute("StarRun", nil)
return "removed: " .. table.concat(removed, ", ")
"""
EXPECTED = [
    "[StarShop] client ready", "purchase ok", "75 left",
    "rejected request from", "unknown item", "bad quantity", "not enough coins",
    "client: bought Training Sword",
]
CREATED = [   # every instance the build adds, with how to take it back by hand
    ("Workspace.StarLobby", "Model with 15 parts, the spawn LobbySpawn, 2 PointLights and the sign's SurfaceGui",
     "delete Workspace.StarLobby"),
    ("ReplicatedStorage.StarShopRemotes", "Folder with RemoteEvents PurchaseRequest and PurchaseResult",
     "delete ReplicatedStorage.StarShopRemotes"),
    ("StarterGui.StarShop", "ScreenGui: Panel (UICorner, UIStroke, UISizeConstraint, UIPadding, UIListLayout), Title, "
     "Balance, Items (UIListLayout, 3 buttons), Status, and the LocalScript ShopClient", "delete StarterGui.StarShop"),
    ("ServerScriptService.StarShopServer", "Script: validates purchase requests", "delete ServerScriptService.StarShopServer"),
]


def capture(command, target: Path) -> dict:
    if not command:
        return {"ok": False, "detail": "no capture command"}
    try:
        done = subprocess.run(command, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "detail": type(error).__name__}
    if done.returncode or not done.stdout.startswith(b"\x89PNG"):
        return {"ok": False, "detail": f"exit {done.returncode}, {len(done.stdout)} bytes"}
    target.write_bytes(done.stdout)
    return {"ok": True, "file": target.name, "bytes": len(done.stdout)}


async def main(chosen) -> int:
    out = Path(chosen.out)
    out.mkdir(parents=True, exist_ok=True)
    grab = json.loads(chosen.capture) if chosen.capture else None
    report = {"steps": [], "ok": False}
    steps = report["steps"]

    def step(name, ok, **more):
        steps.append({"step": name, "ok": bool(ok), **more})
        print(("ok   " if ok else "FAIL ") + name + (" " + json.dumps(more)[:300] if more else ""), flush=True)
        return ok

    async with studio_remote.connect(chosen.home) as session:
        discovered = await studio.list_tools(session)
        guarded, facts = await studio_remote.open_server(session, discovered, home=chosen.home, opted_in=True)
        report["connection"] = {"tools": len(discovered), **facts}
        if guarded is None:
            step("connect", False, problem=facts.get("problem")); return finish(report, out, 2)
        sid = guarded.studio_id
        step("connect", True, tools=len(discovered), place=facts["verdict"].get("place"), rule=facts["verdict"]["kind"],
             editable=facts["verdict"]["editable"])

        async def read(name, **arguments):
            result = await guarded.call_tool(name, {"studio_id": sid, **arguments})
            return studio_loop.result_text(result), studio_loop.result_failed(result)

        async def tree(label):
            rows, problems = [], []
            for service in SERVICES:      # one call per service: the whole DataModel does not fit in one answer
                text, failed = await read("search_game_tree", datamodel_type="Edit", path=service, max_depth=5, head_limit=300)
                start = text.find("[")    # the answer can begin with a note ("Output limited to ...")
                try:
                    found = json.JSONDecoder().raw_decode(text[start:])[0] if start >= 0 else None
                except ValueError:
                    found = None
                if failed or not isinstance(found, list):
                    problems.append(service)
                else:
                    rows.extend(row for row in found if isinstance(row, dict))
            (out / f"tree-{label}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
            step(f"read tree ({label})", bool(rows) and not problems, instances=len(rows), unreadable=problems)
            return {row.get("fullPath") for row in rows}

        before = await tree("before")
        lighting, _failed = await read("inspect_instance", path="Lighting")
        (out / "lighting-before.json").write_text(lighting, encoding="utf-8")
        step("display capture (before)", **capture(grab, out / "studio-loop-01-before.png"))
        want_change = chosen.build or chosen.playtest or chosen.undo or chosen.remove
        if not want_change:
            good = all(item["ok"] for item in steps)
            return finish(report, out, 0 if good else 1, ok=good)
        if not (guarded.verdict.editable and facts.get("is_test_place")):
            step("sandbox rule", False, reason=facts["verdict"]["reason"]); return finish(report, out, 3)
        step("sandbox rule", True, reason=guarded.verdict.reason)

        async def luau(name, code):
            result = await guarded.call_tool("execute_luau", {"studio_id": sid, "datamodel_type": "Edit", "code": code})
            entry = guarded.journal.entries[-1] if guarded.journal.entries else {}
            text = studio_loop.result_text(result)
            return step(name, not studio_loop.result_failed(result) and entry.get("ok") is True,
                        added=entry.get("added_count"), removed=entry.get("removed"), answer=text[-260:])

        if chosen.remove:      # everything an earlier run built, by name: works without that run's journal
            await luau("put settings back", UNDO_SETTINGS)
            await luau("remove what earlier runs built", REMOVE)
            guarded.journal.entries.clear()     # nothing to take back from a removal
            before = await tree("after-remove")
        if chosen.build:
            await luau("build lobby", LOBBY)
            await luau("lighting, template spawn, camera", SETTINGS)
            await luau("build shop interface and remotes", INTERFACE)
            for item in SCRIPTS:
                existing = await guarded._read(item["path"])
                if existing == item["source"]:
                    step("write " + item["path"], True, detail="unchanged"); continue
                edit = {"old_string": existing or "", "new_string": item["source"]}
                result = await guarded.call_tool("multi_edit", {
                    "studio_id": sid, "datamodel_type": "Edit", "file_path": item["path"], "edits": [edit],
                    **({} if existing is not None else {"className": item["class_name"]})})
                back = await guarded._read(item["path"])
                step("write " + item["path"], not studio_loop.result_failed(result) and back is not None
                     and back.strip() == item["source"].strip(), lines=item["source"].count("\n"),
                     detail=studio_loop.result_text(result)[:200])
            after = await tree("after-build")
            report["added_paths"] = sorted(path for path in after - before if path)[:200]
            for path in ("Workspace.StarLobby.Floor", "Workspace.StarLobby.LobbySpawn", "StarterGui.StarShop.Panel"):
                text, failed = await read("inspect_instance", path=path)
                (out / f"inspect-{path.split('.')[-1]}.json").write_text(text, encoding="utf-8")
                step("inspect " + path, not failed and '"className"' in text)
            step("display capture (built, edit mode)", **capture(grab, out / "studio-loop-02-built.png"))

        if chosen.build or chosen.playtest:
            token = secrets.token_hex(4)
            await luau("mark this playtest run", MARK_RUN % token)
            started = await guarded.call_tool("start_stop_play", {"studio_id": sid, "is_start": True})
            if step("playtest start", not studio_loop.result_failed(started), detail=studio_loop.result_text(started)[:160]):
                await asyncio.sleep(chosen.play_seconds)
                state, _failed = await read("get_studio_state")
                output, failed = await read("get_console_output")
                step("display capture (playtest)", **capture(grab, out / "studio-loop-03-playtest.png"))
                stopped = await guarded.call_tool("start_stop_play", {"studio_id": sid, "is_start": False})
                step("playtest stop", not studio_loop.result_failed(stopped), detail=studio_loop.result_text(stopped)[:160])
                at = output.rfind(RUN_LINE % token)
                new = output[at:] if at >= 0 else ""
                (out / "playtest-output.txt").write_text(new, encoding="utf-8")
                (out / "console-all.txt").write_text(output, encoding="utf-8")
                step("this run's first line is in the output", at >= 0, run=token)
                errors = studio_loop.console_errors(new)
                missing = [line for line in EXPECTED if line not in new]
                step("read output", not failed, chars=len(new), state=state[:80].replace("\n", " "))
                step("output has no errors", not errors, errors=errors[:8])
                step("output shows the purchase checks", not missing, missing=missing)
                await asyncio.sleep(3)
                step("display capture (after, edit mode)", **capture(grab, out / "studio-loop-04-after.png"))

        report["changes"] = guarded.journal.report()
        report["created"] = [{"instance": path, "what": what, "undo": undo} for path, what, undo in CREATED]
        report["changed_properties"] = [
            {"instance": "Lighting", "what": "ClockTime 15.5, Brightness 2, Ambient 70,70,80, OutdoorAmbient 140,140,150",
             "undo": "the previous values are attributes Before_* on Workspace.StarLobby (also in lighting-before.json)"},
            {"instance": "Workspace.SpawnLocation (the template's pad)", "what": "Enabled true -> false (it lies under the lobby floor)",
             "undo": "set Enabled back to true"},
            {"instance": "Workspace.Camera", "what": "the editor camera was pointed at the lobby", "undo": "move the camera"},
            {"instance": "Workspace (attributes)", "what": "StarRun = the last playtest's mark; StarSandbox = true (set by STAR's edit wrapper)",
             "undo": "remove the two attributes in the Properties panel"}]
        if chosen.undo:
            result = await guarded.call_tool("execute_luau", {"studio_id": sid, "datamodel_type": "Edit", "code": UNDO_SETTINGS})
            step("put settings back", not studio_loop.result_failed(result), answer=studio_loop.result_text(result)[-120:])
            report["undo"] = await guarded.undo()
            left = await tree("after-undo")
            still = sorted(path for path in left if any(path == made or path.startswith(made + ".") for made, _w, _u in CREATED))
            step("undo removed what was built", not still, undone=report["undo"]["undone"], left=report["undo"]["left"], still=still[:10])
    return finish(report, out, 0 if all(item["ok"] for item in steps) else 1, ok=all(item["ok"] for item in steps))


def finish(report, out: Path, code: int, ok: bool = False) -> int:
    report["ok"] = ok
    (out / "report.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    print("RESULT:", "ok" if ok else "NOT ok", "| report:", out / "report.json")
    return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--home", required=True, help="STAR's data folder (studio/remote.json and the Roblox key check)")
    parser.add_argument("--out", required=True, help="folder for the report, trees, output and captures")
    parser.add_argument("--build", action="store_true", help="build the lobby, the shop and the scripts, then playtest")
    parser.add_argument("--playtest", action="store_true", help="playtest what is there")
    parser.add_argument("--undo", action="store_true", help="take this run's edits back at the end")
    parser.add_argument("--remove", action="store_true", help="first remove, by name, what earlier runs built")
    parser.add_argument("--capture", default="", help="JSON list: command that writes a PNG of the display to stdout")
    parser.add_argument("--play-seconds", type=float, default=14.0)
    raise SystemExit(asyncio.run(main(parser.parse_args())))
