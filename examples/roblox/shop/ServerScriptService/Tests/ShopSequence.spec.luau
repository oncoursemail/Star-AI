--!strict
-- Real ShopCore sequence checks. These run on the pinned standalone Luau CLI, not Studio.
local Core = require("../ShopCore")
local Catalog = require("../../ReplicatedStorage/ShopCatalog")

local function duplicatePurchaseInvariant(api)
    local state = assert(api.new(Catalog))
    assert(api.seed(state, 11, 250))
    assert(api.purchase(state, 11, "WoodenSword", 1))
    assert(not api.purchase(state, 11, "WoodenSword", 1), "duplicate purchase accepted")
    assert(api.balance(state, 11) == 175, "duplicate purchase debited wallet")
    assert(#api.ownedIds(state, 11) == 1, "duplicate purchase granted extra item")
end

return {
    ["pending rollback retry confirmation and multi-item ownership"] = function()
        local state = assert(Core.new(Catalog))
        assert(Core.seed(state, 11, 250))
        assert(Core.purchase(state, 11, "WoodenSword", 1))
        assert(state.pending[11].WoodenSword == 75)
        assert(Core.balance(state, 11) == 175)
        assert(not Core.purchase(state, 11, "WoodenSword", 1))
        assert(Core.rollback(state, 11, "WoodenSword"))
        assert(Core.balance(state, 11) == 250)
        assert(not Core.has(state, 11, "WoodenSword"))
        assert(not Core.rollback(state, 11, "WoodenSword"))
        assert(Core.purchase(state, 11, "WoodenSword", 1))
        assert(Core.confirm(state, 11, "WoodenSword"))
        assert(not Core.confirm(state, 11, "WoodenSword"))
        assert(not Core.rollback(state, 11, "WoodenSword"))
        assert(not Core.purchase(state, 11, "WoodenSword", 1))
        assert(Core.purchase(state, 11, "HealingKit", 1))
        assert(Core.confirm(state, 11, "HealingKit"))
        local owned = Core.ownedIds(state, 11)
        assert(#owned == 2 and owned[1] == "HealingKit" and owned[2] == "WoodenSword")
        assert(Core.balance(state, 11) == 135)
    end,

    ["independent players can settle the same item differently"] = function()
        local state = assert(Core.new(Catalog))
        assert(Core.seed(state, 11, 250))
        assert(Core.seed(state, 12, 250))
        assert(Core.purchase(state, 11, "BlueLantern", 1))
        assert(Core.purchase(state, 12, "BlueLantern", 1))
        assert(Core.rollback(state, 11, "BlueLantern"))
        assert(Core.confirm(state, 12, "BlueLantern"))
        assert(Core.balance(state, 11) == 250)
        assert(Core.balance(state, 12) == 120)
        assert(not Core.has(state, 11, "BlueLantern"))
        assert(Core.has(state, 12, "BlueLantern"))
        assert(not Core.rollback(state, 12, "BlueLantern"))
        assert(Core.purchase(state, 11, "BlueLantern", 1))
        assert(Core.confirm(state, 11, "BlueLantern"))
        assert(Core.balance(state, 12) == 120)
        assert(Core.has(state, 11, "BlueLantern"))
    end,

    ["removal drops pending only for departing player and reseed is clean"] = function()
        local state = assert(Core.new(Catalog))
        assert(Core.seed(state, 11, 250))
        assert(Core.seed(state, 12, 250))
        assert(Core.purchase(state, 11, "WoodenSword", 1))
        assert(Core.purchase(state, 12, "HealingKit", 1))
        assert(Core.confirm(state, 12, "HealingKit"))
        assert(Core.removePlayer(state, 11))
        assert(not Core.removePlayer(state, 11))
        assert(Core.balance(state, 11) == nil)
        assert(not Core.rollback(state, 11, "WoodenSword"))
        assert(not Core.confirm(state, 11, "WoodenSword"))
        assert(not Core.purchase(state, 11, "WoodenSword", 1))
        assert(#Core.ownedIds(state, 11) == 0)
        assert(Core.has(state, 12, "HealingKit"))
        assert(Core.balance(state, 12) == 210)
        assert(Core.seed(state, 11, 250))
        assert(not Core.has(state, 11, "WoodenSword"))
        assert(Core.balance(state, 11) == 250)
        assert(Core.purchase(state, 11, "WoodenSword", 1))
        assert(Core.confirm(state, 11, "WoodenSword"))
        assert(Core.balance(state, 12) == 210)
    end,

    ["malformed requests between valid transitions never change funds"] = function()
        local state = assert(Core.new(Catalog))
        assert(Core.seed(state, 11, 250))
        assert(Core.purchase(state, 11, "HealingKit", 1))
        assert(Core.confirm(state, 11, "HealingKit"))
        for _, amount in {0, -1, 1.5, 2, math.huge, 0 / 0, "1"} do
            assert(not Core.purchase(state, 11, "WoodenSword", amount))
            assert(Core.balance(state, 11) == 210)
            assert(not Core.has(state, 11, "WoodenSword"))
        end
        assert(not Core.purchase(state, 11, "WoodenSword", 1, 0))
        assert(not Core.purchase(state, 11, "WoodenSword", 1, 75))
        assert(not Core.purchase(state, 11, "Nonexistent", 1))
        assert(not Core.purchase(state, 0, "WoodenSword", 1))
        assert(Core.balance(state, 11) == 210)
        assert(Core.purchase(state, 11, "WoodenSword", 1))
        assert(Core.balance(state, 11) == 135)
        assert(Core.confirm(state, 11, "WoodenSword"))
        assert(#Core.ownedIds(state, 11) == 2)
    end,

    ["impossible missing inventory during pending rollback fails before refund"] = function()
        local state = assert(Core.new(Catalog))
        assert(Core.seed(state, 11, 250))
        assert(Core.purchase(state, 11, "WoodenSword", 1))
        -- Not client input: explicitly corrupt otherwise server-owned internal state.
        state.owned[11].WoodenSword = nil
        local before = Core.balance(state, 11)
        local ok = pcall(function() Core.rollback(state, 11, "WoodenSword") end)
        assert(not ok, "inconsistent pending ownership must be an explicit internal error")
        assert(Core.balance(state, 11) == before, "failed rollback must not mint coins")
        assert(state.pending[11].WoodenSword == 75, "failed rollback must retain evidence")
        state.owned[11].WoodenSword = true
        assert(Core.rollback(state, 11, "WoodenSword"))
        assert(Core.balance(state, 11) == 250)
        assert(not Core.rollback(state, 11, "WoodenSword"))
    end,

    ["corrupted pending price and wallet are internal errors before mutation"] = function()
        local state = assert(Core.new(Catalog))
        assert(Core.seed(state, 11, 250))
        assert(Core.purchase(state, 11, "WoodenSword", 1))
        local before = Core.balance(state, 11)
        state.pending[11].WoodenSword = 999
        assert(not pcall(function() Core.rollback(state, 11, "WoodenSword") end))
        assert(Core.balance(state, 11) == before)
        assert(state.pending[11].WoodenSword == 999)
        assert(Core.has(state, 11, "WoodenSword"))
        state.pending[11].WoodenSword = 75
        state.wallets[11] = "corrupted"
        assert(not pcall(function() Core.rollback(state, 11, "WoodenSword") end))
        assert(state.pending[11].WoodenSword == 75)
        assert(Core.has(state, 11, "WoodenSword"))
        state.wallets[11] = before
        assert(Core.rollback(state, 11, "WoodenSword"))
        assert(Core.balance(state, 11) == 250)
        assert(not Core.has(state, 11, "WoodenSword"))
    end,

    ["fixed-seed three-player request history matches state machine"] = function()
        local state = assert(Core.new(Catalog))
        local players = {11, 12, 13}
        local products = {"WoodenSword", "BlueLantern", "HealingKit"}
        local wallets = {}
        local statuses = {}
        local active = {}
        for _, id in players do
            assert(Core.seed(state, id, 250))
            wallets[id] = 250
            statuses[id] = {}
            active[id] = true
        end
        local seed = 37
        for step = 1, 144 do
            seed = (seed * 73 + 29) % 997
            local id = players[(seed % #players) + 1]
            seed = (seed * 47 + 11) % 997
            local product = products[(seed % #products) + 1]
            seed = (seed * 61 + 13) % 997
            local action = seed % 6
            local previous = statuses[id][product]
            if action == 0 then
                local shouldBuy = active[id] and previous == nil and wallets[id] >= Catalog[product]
                local bought = Core.purchase(state, id, product, 1)
                assert(bought == shouldBuy, "purchase diverged at step " .. step)
                if shouldBuy then
                    statuses[id][product] = "pending"
                    wallets[id] -= Catalog[product]
                end
            elseif action == 1 then
                local shouldConfirm = active[id] and previous == "pending"
                assert(Core.confirm(state, id, product) == shouldConfirm)
                if shouldConfirm then statuses[id][product] = "confirmed" end
            elseif action == 2 then
                local shouldRefund = active[id] and previous == "pending"
                assert(Core.rollback(state, id, product) == shouldRefund)
                if shouldRefund then
                    statuses[id][product] = nil
                    wallets[id] += Catalog[product]
                end
            elseif action == 3 then
                assert(not Core.purchase(state, id, product, 2))
            elseif action == 4 then
                assert(Core.removePlayer(state, id) == active[id])
                active[id] = false
                wallets[id] = nil
                statuses[id] = {}
            else
                assert(Core.seed(state, id, 250) == (not active[id]))
                if not active[id] then
                    active[id] = true
                    wallets[id] = 250
                    statuses[id] = {}
                end
            end
            assert(Core.balance(state, id) == wallets[id], "wallet diverged at step " .. step)
            local count = 0
            for _, sku in products do
                local expected = statuses[id][sku] ~= nil
                assert(Core.has(state, id, sku) == expected, "ownership diverged at step " .. step)
                if expected then count += 1 end
            end
            assert(#Core.ownedIds(state, id) == count, "owned-ID count diverged at step " .. step)
        end
    end,

    ["negative duplicate-debit mutant is caught by real purchase invariant"] = function()
        duplicatePurchaseInvariant(Core)
        local mutant = setmetatable({}, {__index = Core})
        mutant.purchase = function(state, id, sku, quantity, price)
            local ok, result = Core.purchase(state, id, sku, quantity, price)
            if not ok and result == "already owned" then
                -- Deliberately incorrect implementation: retry debits a second time.
                state.wallets[id] -= state.prices[sku]
                return true, {item = sku, price = state.prices[sku]}
            end
            return ok, result
        end
        local survived = pcall(function() duplicatePurchaseInvariant(mutant) end)
        assert(not survived, "deliberate double-debit mutant escaped the invariant")
    end,
}
