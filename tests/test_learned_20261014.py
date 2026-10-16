"""learned-20261014: the practice tasks in server/night_school/practice/ and the shipped lesson candidates.

Practice tasks: every file is loaded by night school's own pool loader (which runs the repository's evaluation
loaders), no task copies an evaluation prompt or id, and every task's pattern checks accept a correct answer and
reject a broken one for the named reason. The Luau compile/type check itself runs only on the server.
Lessons: the shipped bundle parses with the strict star-lessons-v1 importer and imports as candidates only.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server" / "night_school"))

from nightschool.pool import build_guard, load_pool, prompt_hash   # noqa: E402
from star.eval_checks import extract_luau_blocks, pattern_checks    # noqa: E402
from star.lesson_import import import_export, parse_export, read_export   # noqa: E402
from star.lessons import LessonStore                                 # noqa: E402

PRACTICE = ROOT / "server" / "night_school" / "practice"
BUNDLE = ROOT / "star" / "skill_packs" / "lessons_bundled.json"
SUITES = sorted(p for p in (ROOT / "evals" / "roblox").glob("*.json") if "holdout" not in p.name)
FENCE = "`" * 3


def answer(code: str) -> str:
    return f"Here it is.\n\n{FENCE}lua\n{code.strip()}\n{FENCE}\n"


# id suffix -> (correct answer, broken answer, check id the broken answer must fail)
W: dict[str, tuple[str, str, str]] = {
    "types-player-param": ("""
--!strict
local Greeter = {}
function Greeter.welcome(player: Player): string
    return "Welcome, " .. player.DisplayName .. "!"
end
function Greeter.countPlayers(list: {Player}): number
    return #list
end
return Greeter
""", """
--!strict
local Greeter = {}
function Greeter.welcome(player: Players.Player): string
    return "Welcome, " .. player.DisplayName .. "!"
end
function Greeter.countPlayers(list: {Player}): number
    return #list
end
return Greeter
""", "forbid:no_players_player"),
    "types-empty-return": ("""
--!strict
local Log = {}
local level = 1
function Log.setLevel(value: number): ()
    level = value
end
function Log.getLevel(): number
    return level
end
function Log.info(message: string): ()
    if level <= 1 then
        print(message)
    end
end
return Log
""", """
--!strict
local Log = {}
local level = 1
function Log.setLevel(value: number): void
    level = value
end
function Log.getLevel(): number
    return level
end
return Log
""", "forbid:no_void"),
    "types-optional-fields": ("""
--!strict
local Orders = {}
export type Order = { itemId: string, quantity: number, coupon: string?, note: string? }
function Orders.make(itemId: string, quantity: number, coupon: string?): Order
    if quantity ~= math.floor(quantity) or quantity < 1 or quantity > 99 then
        error("quantity must be a whole number from 1 to 99")
    end
    return { itemId = itemId, quantity = quantity, coupon = coupon }
end
return Orders
""", """
--!strict
local Orders = {}
export type Order = { itemId: string, quantity: number, coupon?: string, note?: string }
function Orders.make(itemId: string, quantity: number, coupon: string?): Order
    if quantity ~= math.floor(quantity) then error("bad") end
    return { itemId = itemId, quantity = quantity, coupon = coupon }
end
return Orders
""", "forbid:no_ts_optional"),
    "types-function-type": ("""
--!strict
local Rewards = {}
type Handler = (player: Player, amount: number) -> ()
local handlers: {Handler} = {}
function Rewards.connect(handler: Handler): () -> ()
    table.insert(handlers, handler)
    return function()
        local at = table.find(handlers, handler)
        if at then table.remove(handlers, at) end
    end
end
function Rewards.fire(player: Player, amount: number): ()
    for _, handler in ipairs(table.clone(handlers)) do
        handler(player, amount)
    end
end
return Rewards
""", """
--!strict
local Rewards = {}
type Handler = (player: Player, amount: number) -> ()
local handlers = {}
function Rewards.connect(handler: function): () -> ()
    table.insert(handlers, handler)
    return function() end
end
function Rewards.fire(player: Player, amount: number)
    for _, handler in ipairs(handlers) do handler(player, amount) end
end
return Rewards
""", "forbid:no_function_type"),
    "types-multiple-returns": ("""
--!strict
local Wallet = {}
function Wallet.trySpend(balance: number, cost: number): (boolean, number, string?)
    if cost ~= cost or cost < 0 then
        return false, balance, "invalid cost"
    end
    if cost > balance then
        return false, balance, "not enough coins"
    end
    return true, balance - cost, nil
end
return Wallet
""", """
--!strict
local Wallet = {}
function Wallet.trySpend(balance: number, cost: number): (ok: boolean, newBalance: number, reason: string?)
    if cost ~= cost or cost < 0 or cost > balance then
        return false, balance, "no"
    end
    return true, balance - cost, nil
end
return Wallet
""", "forbid:no_named_returns"),
    "types-pathwaypoint": ("""
--!strict
local Route = {}
function Route.totalLength(waypoints: {PathWaypoint}): number
    local total = 0
    for i = 2, #waypoints do
        total += (waypoints[i].Position - waypoints[i - 1].Position).Magnitude
    end
    return total
end
function Route.jumpCount(waypoints: {PathWaypoint}): number
    local count = 0
    for _, waypoint in waypoints do
        if waypoint.Action == Enum.PathWaypointAction.Jump then
            count += 1
        end
    end
    return count
end
return Route
""", """
--!strict
local Route = {}
function Route.totalLength(waypoints: {PathfindingService.PathWaypoint}): number
    local total = 0
    for i = 2, #waypoints do
        total += (waypoints[i].Position - waypoints[i - 1].Position).Magnitude
    end
    return total
end
function Route.jumpCount(waypoints: {PathWaypoint}): number
    local count = 0
    for _, w in waypoints do
        if w.Action == Enum.PathWaypointAction.Jump then count += 1 end
    end
    return count
end
return Route
""", "forbid:no_service_type"),
    "types-no-is-operator": ("""
local Players = game:GetService("Players")
local goal = workspace:WaitForChild("Goal")

local function getPlayerFromHit(hit: Instance): Player?
    if typeof(hit) ~= "Instance" or not hit:IsA("BasePart") then
        return nil
    end
    local model = hit:FindFirstAncestorOfClass("Model")
    if model and model:FindFirstChildOfClass("Humanoid") then
        return Players:GetPlayerFromCharacter(model)
    end
    return nil
end

goal.Touched:Connect(function(hit)
    local player = getPlayerFromHit(hit)
    if player then
        print(player.Name) -- this player is at the goal
    end
end)
""", """
local Players = game:GetService("Players")
local goal = workspace:WaitForChild("Goal")

local function getPlayerFromHit(hit)
    if not (hit is BasePart) then return nil end
    local model = hit:FindFirstAncestorOfClass("Model")
    if typeof(model) == "Instance" and model:FindFirstChildOfClass("Humanoid") then
        return Players:GetPlayerFromCharacter(model)
    end
    return nil
end
goal.Touched:Connect(function(hit) print(getPlayerFromHit(hit)) end)
""", "forbid:no_is"),
    "types-class-queue": ("""
--!strict
local Queue = {}
Queue.__index = Queue

type QueueData = { items: {[number]: string}, head: number, tail: number }
export type Queue = typeof(setmetatable({} :: QueueData, Queue))

function Queue.new(): Queue
    return setmetatable({ items = {}, head = 1, tail = 0 }, Queue)
end

function Queue.push(self: Queue, value: string): ()
    self.tail += 1
    self.items[self.tail] = value
end

function Queue.pop(self: Queue): string?
    if self.head > self.tail then
        return nil
    end
    local value = self.items[self.head]
    self.items[self.head] = nil
    self.head += 1
    return value
end

function Queue.size(self: Queue): number
    return self.tail - self.head + 1
end

return Queue
""", """
--!strict
export type Queue = { items: {string}, push: (Queue, string) -> (), pop: (Queue) -> string? }
local Queue: Queue = {} :: any
Queue.__index = Queue
function Queue.new(): Queue
    return setmetatable({ items = {} }, Queue) :: any
end
function Queue.pop(self: Queue): string?
    return table.remove(self.items, 1)
end
return Queue
""", "forbid:no_typed_class_table"),
    "types-comments-and-floor-div": ("""
local Grid = {}

function Grid.cellOf(position: Vector3, size: number): (number, number)
    -- column from the X axis, rounded down
    local column = position.X // size
    -- row from the Z axis, rounded down
    local row = position.Z // size
    return column, row
end

return Grid
""", """
local Grid = {}

function Grid.cellOf(position: Vector3, size: number): (number, number)
    // column from the X axis
    local column = math.floor(position.X / size)
    // row from the Z axis
    local row = math.floor(position.Z / size)
    return column, row
end

return Grid
""", "forbid:no_slash_comment"),
    "types-dictionary": ("""
--!strict
local Votes = {}
local votes: {[number]: string} = {}

function Votes.cast(userId: number, mapName: string): ()
    votes[userId] = mapName
end

function Votes.tally(): {[string]: number}
    local counts: {[string]: number} = {}
    for _, mapName in votes do
        counts[mapName] = (counts[mapName] or 0) + 1
    end
    return counts
end

function Votes.winner(): string?
    local best: string? = nil
    local bestCount = 0
    for mapName, count in Votes.tally() do
        if count > bestCount or (count == bestCount and best ~= nil and mapName < best) then
            best, bestCount = mapName, count
        end
    end
    return best
end

return Votes
""", """
--!strict
local Votes = {}
local votes: {number: string} = {}
function Votes.cast(userId: number, mapName: string): ()
    votes[userId] = mapName
end
function Votes.tally(): {[string]: number}
    local counts: {[string]: number} = {}
    for _, m in votes do counts[m] = (counts[m] or 0) + 1 end
    return counts
end
function Votes.winner(): string?
    local best, n = nil, 0
    for m, c in Votes.tally() do if c > n or (c == n and m < best) then best, n = m, c end end
    return best
end
return Votes
""", "forbid:no_field_dict"),
    "types-narrow-instance": ("""
--!strict
local UiUtil = {}
function UiUtil.setLabel(gui: Instance, text: string): boolean
    local label = gui:FindFirstChild("Label")
    if label and label:IsA("TextLabel") then
        label.Text = text
        return true
    end
    return false
end
return UiUtil
""", """
--!strict
local UiUtil = {}
function UiUtil.setLabel(gui: Instance, text: string): boolean
    local label = gui:FindFirstChild("Label") :: any
    if label and label:IsA("TextLabel") then
        label.Text = text
        return true
    end
    return false
end
return UiUtil
""", "forbid:no_any"),
    "types-forward-declare": ("""
local lava = workspace:WaitForChild("Lava")
local lastHit: {[Model]: number} = {}

local connection = lava.Touched:Connect(function(hit)
    local character = hit:FindFirstAncestorOfClass("Model")
    local humanoid = character and character:FindFirstChildOfClass("Humanoid")
    if not character or not humanoid then
        return
    end
    local now = os.clock()
    if lastHit[character] and now - lastHit[character] < 1 then
        return
    end
    lastHit[character] = now
    humanoid:TakeDamage(15)
end)

lava.Destroying:Connect(function()
    connection:Disconnect()
    table.clear(lastHit)
end)
""", """
local lava = workspace:WaitForChild("Lava")
local lastHit = {}
lava.Touched:Connect(function(hit)
    local character = hit.Parent
    local humanoid = character and character:FindFirstChildOfClass("Humanoid")
    if humanoid and (not lastHit[character] or os.clock() - lastHit[character] >= 1) then
        lastHit[character] = os.clock()
        humanoid:TakeDamage(15)
    end
end)
lava.Destroying:Connect(function()
    connection:Disconnect()
end)
""", "require:conn_local"),
    "char-existing-and-new": ("""
local Players = game:GetService("Players")

local function tag(character: Model)
    local value = Instance.new("BoolValue")
    value.Name = "Tagged"
    value.Value = false
    value.Parent = character
end

local function onPlayer(player: Player)
    player.CharacterAdded:Connect(tag)
    if player.Character then
        tag(player.Character)
    end
end

Players.PlayerAdded:Connect(onPlayer)
for _, player in Players:GetPlayers() do
    onPlayer(player)
end
""", """
local Players = game:GetService("Players")
Players.PlayerAdded:Connect(function(player)
    player.CharacterAdded:Connect(function(character)
        local value = Instance.new("BoolValue")
        value.Name = "Tagged"
        value.Parent = character
    end)
end)
""", "require:existing_players"),
    "char-died-event": ("""
local Players = game:GetService("Players")

Players.PlayerAdded:Connect(function(player)
    local stats = Instance.new("Folder")
    stats.Name = "leaderstats"
    stats.Parent = player
    local deaths = Instance.new("IntValue")
    deaths.Name = "Deaths"
    deaths.Parent = stats

    player.CharacterAdded:Connect(function(character)
        local humanoid = character:WaitForChild("Humanoid") :: Humanoid
        humanoid.Died:Once(function()
            deaths.Value += 1
        end)
    end)
end)
""", """
local Players = game:GetService("Players")
Players.PlayerAdded:Connect(function(player)
    local stats = Instance.new("Folder")
    stats.Name = "leaderstats"
    stats.Parent = player
    local deaths = Instance.new("IntValue")
    deaths.Name = "Deaths"
    deaths.Parent = stats
    player.CharacterAdded:Connect(function(character)
        local humanoid = character:WaitForChild("Humanoid")
        while humanoid.Health > 0 do task.wait(0.1) end
        deaths.Value += 1
    end)
end)
""", "require:died"),
    "char-removing-cleanup": ("""
local Players = game:GetService("Players")
local connections: {[Player]: RBXScriptConnection} = {}

local function drop(player: Player)
    local connection = connections[player]
    if connection then
        connection:Disconnect()
    end
    connections[player] = nil
end

Players.PlayerAdded:Connect(function(player)
    player.CharacterAdded:Connect(function(character)
        drop(player)
        local humanoid = character:WaitForChild("Humanoid") :: Humanoid
        connections[player] = humanoid.HealthChanged:Connect(function(health)
            print(player.Name, health)
        end)
    end)
    player.CharacterRemoving:Connect(function()
        drop(player)
    end)
end)

Players.PlayerRemoving:Connect(drop)
""", """
local Players = game:GetService("Players")
local connections = {}
Players.PlayerAdded:Connect(function(player)
    player.CharacterAdded:Connect(function(character)
        local humanoid = character:WaitForChild("Humanoid")
        connections[player] = humanoid.HealthChanged:Connect(function(health) print(health) end)
    end)
end)
""", "require:removing"),
    "char-manual-respawn": ("""
local Players = game:GetService("Players")
Players.CharacterAutoLoads = false

local function spawnPlayer(player: Player)
    if player.Parent ~= Players then
        return
    end
    player:LoadCharacterAsync()
end

Players.PlayerAdded:Connect(function(player)
    player.CharacterAdded:Connect(function(character)
        local humanoid = character:WaitForChild("Humanoid") :: Humanoid
        humanoid.Died:Once(function()
            task.delay(5, spawnPlayer, player)
        end)
    end)
    spawnPlayer(player)
end)
""", """
local Players = game:GetService("Players")
Players.CharacterAutoLoads = false
Players.PlayerAdded:Connect(function(player)
    player.CharacterAdded:Connect(function(character)
        character:WaitForChild("Humanoid").Died:Connect(function()
            task.wait(5)
            if player.Parent then player:LoadCharacter() end
        end)
    end)
    player:LoadCharacter()
end)
""", "forbid:no_deprecated_load"),
    "char-rig-type": ("""
local Rig = {}

function Rig.torsoOf(character: Model): BasePart?
    local humanoid = character:FindFirstChildOfClass("Humanoid")
    if not humanoid then
        return nil
    end
    local name = if humanoid.RigType == Enum.HumanoidRigType.R15 then "UpperTorso" else "Torso"
    local part = character:FindFirstChild(name)
    if part and part:IsA("BasePart") then
        return part
    end
    return nil
end

return Rig
""", """
local Rig = {}
function Rig.torsoOf(character: Model): BasePart?
    local part = character:FindFirstChild("UpperTorso") or character:FindFirstChild("Torso")
    return part
end
return Rig
""", "require:rigtype"),
    "char-isa-inheritance": ("""
local ghost = workspace:WaitForChild("Ghost")
for _, item in ghost:GetDescendants() do
    if item:IsA("BasePart") then
        item.CanCollide = false
        item.Transparency = 0.5
    end
end
""", """
local ghost = workspace:WaitForChild("Ghost")
for _, item in ghost:GetDescendants() do
    if item.ClassName == "Part" then
        item.CanCollide = false
        item.Transparency = 0.5
    end
end
""", "forbid:no_classname"),
    "char-spawn-teleport": ("""
local Players = game:GetService("Players")
local pad = workspace:WaitForChild("SpawnPad") :: BasePart

Players.PlayerAdded:Connect(function(player)
    player.CharacterAdded:Connect(function(character)
        local root = character:WaitForChild("HumanoidRootPart", 10)
        if not root then
            return
        end
        character:PivotTo(pad.CFrame + Vector3.new(0, 3, 0))
    end)
end)
""", """
local Players = game:GetService("Players")
local pad = workspace:WaitForChild("SpawnPad")
Players.PlayerAdded:Connect(function(player)
    player.CharacterAdded:Connect(function(character)
        character:WaitForChild("HumanoidRootPart", 10)
        character:SetPrimaryPartCFrame(pad.CFrame + Vector3.new(0, 3, 0))
    end)
end)
""", "require:pivot"),
    "integrity-refund-validate-first": ("""
local ShopCore = {}
local PRICES = { sword = 100, shield = 75 }

function ShopCore.refund(state, userId: number, itemId: string): (boolean, string?)
    local owned = state.owned[userId]
    if not owned or not owned[itemId] then
        return false, "not owned"
    end
    local price = PRICES[itemId]
    if price == nil then
        return false, "unknown item"
    end
    if state.coins[userId] == nil then
        return false, "no wallet"
    end
    owned[itemId] = nil
    state.coins[userId] += price
    return true
end

return ShopCore
""", """
local ShopCore = {}
local PRICES = { sword = 100 }
function ShopCore.refund(state, userId: number, itemId: string): (boolean, string?)
    state.owned[userId][itemId] = nil
    state.coins[userId] = (state.coins[userId] or 0) + (PRICES[itemId] or 0)
    if PRICES[itemId] == nil then
        return false, "unknown item"
    end
    return true
end
return ShopCore
""", "forbid:no_mutate_then_check"),
    "integrity-lock-expiry": ("""
local LockRules = {}
LockRules.AUTOSAVE_SECONDS = 60

function LockRules.expiryFor(now: number): number
    return now + 2 * LockRules.AUTOSAVE_SECONDS + 30
end

function LockRules.canAcquire(lock: {owner: string, expires: number}?, jobId: string, now: number): boolean
    if not lock then
        return true
    end
    return lock.expires <= now or lock.owner == jobId
end

return LockRules
""", """
local LockRules = {}
LockRules.AUTOSAVE_SECONDS = 60
function LockRules.expiryFor(now: number): number
    return now + 60
end
function LockRules.canAcquire(lock, jobId: string, now: number): boolean
    if not lock then return true end
    return lock.expires < now or lock.owner == jobId
end
return LockRules
""", "require:expiry"),
    "integrity-autosave-snapshot": ("""
local Players = game:GetService("Players")
local DataStoreService = game:GetService("DataStoreService")
local store = DataStoreService:GetDataStore("PlayerData")
local sessions = {}

task.spawn(function()
    while true do
        task.wait(60)
        local toSave = {}
        for player, data in sessions do
            table.insert(toSave, { player = player, data = table.clone(data) })
        end
        for _, entry in toSave do
            local ok, err = pcall(function()
                store:UpdateAsync("player_" .. entry.player.UserId, function()
                    return entry.data
                end)
            end)
            if not ok then
                warn("autosave failed", entry.player.UserId, err)
            end
        end
    end
end)

Players.PlayerRemoving:Connect(function(player)
    sessions[player] = nil
end)
""", """
local DataStoreService = game:GetService("DataStoreService")
local store = DataStoreService:GetDataStore("PlayerData")
local sessions = {}
while true do
    task.wait(60)
    for player, data in sessions do
        local ok = pcall(function() store:SetAsync("player_" .. player.UserId, data) end)
        if not ok then warn("failed") end
    end
end
""", "require:update"),
    "integrity-purchase-once": ("""
local PurchaseCore = {}

function PurchaseCore.buy(state, userId: number, requestId: string, price: number): (boolean, string)
    if state.done[requestId] then
        return true, "duplicate"
    end
    local coins = state.coins[userId] or 0
    if coins < price then
        return false, "not enough coins"
    end
    state.coins[userId] = coins - price
    state.done[requestId] = true
    return true, "ok"
end

return PurchaseCore
""", """
local PurchaseCore = {}
function PurchaseCore.buy(state, userId: number, requestId: string, price: number): (boolean, string)
    if (state.coins[userId] or 0) < price then
        return false, "not enough coins"
    end
    state.coins[userId] -= price
    return true, "ok"
end
return PurchaseCore
""", "require:remember"),
}


def _tasks() -> list[dict]:
    rows = []
    for path in sorted(PRACTICE.glob("*.json")):
        rows.extend(json.loads(path.read_text(encoding="utf-8")))
    return rows


def _results(task: dict, code: str) -> dict[str, bool]:
    body = answer(code)
    return {c.id: c.ok for c in pattern_checks(task["auto"], extract_luau_blocks(body), body)}


def test_pool_loader_accepts_every_task():
    pool = load_pool(PRACTICE)
    assert pool.dropped == {}, pool.summary()
    assert len(pool.tasks) == len(_tasks()) == len(W) == 23
    assert pool.files == 3


def test_no_copy_of_an_evaluation_task():
    guard = build_guard(SUITES)          # refuses the holdout by name; it is never read here
    ids, hashes = set(guard["ids"]), set(guard["prompt_sha256"])
    words = lambda text: set(re.findall(r"[a-z]+", text.lower()))   # noqa: E731
    suite_prompts = [row["prompt"] for path in SUITES for row in json.loads(path.read_text(encoding="utf-8"))
                     if isinstance(row, dict) and isinstance(row.get("prompt"), str)]
    for task in _tasks():
        assert task["id"] not in ids and prompt_hash(task["prompt"]) not in hashes
        mine = words(task["prompt"])
        worst = max(len(mine & words(p)) / len(mine | words(p)) for p in suite_prompts)
        assert worst < 0.5, (task["id"], worst)


@pytest.mark.parametrize("suffix", sorted(W), ids=lambda s: s)
def test_checks_accept_good_and_reject_broken(suffix):
    task = next(t for t in _tasks() if t["id"] == "practice-learned-" + suffix)
    good, bad, reason = W[suffix]
    passed = _results(task, good)
    assert all(passed.values()), {k: v for k, v in passed.items() if not v}
    failed = _results(task, bad)
    assert failed[reason] is False, failed


def test_bundled_lessons_import_as_candidates(tmp_path):
    data = read_export(BUNDLE)
    project, entries = parse_export(data)
    assert project == "STAR" and len(entries) == len(data["lessons"]) == data["counts"]["candidate"] >= 10
    assert all(row["status"] == "candidate" and row["evidence"].strip() for row in data["lessons"])
    store = LessonStore(tmp_path)
    try:
        first = import_export(store, data)
        assert first["imported"] == len(entries) and import_export(store, data)["imported"] == 0
        assert store.recall("STAR", "strict Luau Player type for a remote handler") == []   # not live until reviewed
    finally:
        store.close()
