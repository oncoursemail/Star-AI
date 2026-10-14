--!strict
-- Pure language smoke for record aliases and typed returns from candidate lessons.
-- Executed by the checksum-pinned headless Luau CLI; not a Roblox Studio test.
type PlatformMotion = {active: boolean, speed: number}
type CheckpointByUser = {[number]: number}
type InventoryEntry = {itemId: string, quantity: number}
type Receipt = {itemId: string}
type CoinBalance = number
type RoundDecision = {allowed: boolean, reason: string}
type EquippedItem = {itemId: string}
type InventoryBuilder = {create: () -> InventoryEntry}

local function reward(): CoinBalance
    return 75
end
local function decide(players: number): RoundDecision
    if players < 2 then return {allowed = false, reason = "waiting"} end
    return {allowed = true, reason = ""}
end
local builder: InventoryBuilder = {
    create = function(): InventoryEntry return {itemId = "potion", quantity = 1} end,
}
local receiptFactory = {
    makeReceipt = function(itemId: string): Receipt return {itemId = itemId} end,
}

return {
    ["RT-01 platform record aliases are accepted"] = function()
        local motion: PlatformMotion = {active = false, speed = 8}
        assert(not motion.active and motion.speed == 8)
    end,
    ["RT-02 checkpoint number map aliases are accepted"] = function()
        local stages: CheckpointByUser = {[10] = 2}
        assert(stages[10] == 2)
    end,
    ["RT-03 inventory records have the declared shape"] = function()
        local item: InventoryEntry = {itemId = "potion", quantity = 3}
        assert(item.quantity == 3)
    end,
    ["RT-07 ModuleScript returns a real value instead of an alias"] = function()
        assert(receiptFactory.makeReceipt("ticket").itemId == "ticket")
    end,
    ["RT-08 typed currency return has the correct value"] = function()
        assert(reward() == 75)
    end,
    ["RT-09 round branches both produce records"] = function()
        assert(decide(1).reason == "waiting" and decide(2).allowed)
    end,
    ["RT-10 optional slot permits nil"] = function()
        local equipped: EquippedItem? = nil
        assert(equipped == nil)
        equipped = {itemId = "potion"}
        assert(equipped.itemId == "potion")
    end,
    ["RT-11 typed module table returns a record"] = function()
        assert(builder.create().itemId == "potion")
    end,
}
