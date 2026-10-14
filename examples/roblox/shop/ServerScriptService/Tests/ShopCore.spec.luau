--!strict
local Core = require("../ShopCore")
local Catalog = require("../../ReplicatedStorage/ShopCatalog")

return {
    ["valid purchase debits only server price"] = function()
        local state = assert(Core.new(Catalog))
        assert(Core.seed(state, 11, 250))
        local ok, receipt = Core.purchase(state, 11, "WoodenSword", 1)
        assert(ok and receipt.price == 75 and receipt.remaining == 175)
        assert(Core.has(state, 11, "WoodenSword"))
    end,
    ["unknown item cannot spend money"] = function()
        local state = assert(Core.new(Catalog))
        Core.seed(state, 11, 250)
        assert(not Core.purchase(state, 11, "NoSuchItem", 1))
        assert(Core.balance(state, 11) == 250)
    end,
    ["insufficient coins leaves inventory unchanged"] = function()
        local state = assert(Core.new(Catalog))
        Core.seed(state, 11, 10)
        assert(not Core.purchase(state, 11, "BlueLantern", 1))
        assert(not Core.has(state, 11, "BlueLantern"))
        assert(Core.balance(state, 11) == 10)
    end,
    ["negative zero fractional and bulk quantities are refused"] = function()
        local state = assert(Core.new(Catalog))
        Core.seed(state, 11, 250)
        for _, count in {-1, 0, 1.5, 2} do
            assert(not Core.purchase(state, 11, "HealingKit", count))
        end
        assert(Core.balance(state, 11) == 250)
    end,
    ["client fabricated price never overrides catalog"] = function()
        local state = assert(Core.new(Catalog))
        Core.seed(state, 11, 250)
        assert(not Core.purchase(state, 11, "BlueLantern", 1, 1))
        assert(Core.balance(state, 11) == 250)
        assert(not Core.has(state, 11, "BlueLantern"))
    end,
    ["even true price sent by client is refused"] = function()
        local state = assert(Core.new(Catalog))
        Core.seed(state, 11, 250)
        assert(not Core.purchase(state, 11, "WoodenSword", 1, 75))
        assert(Core.balance(state, 11) == 250)
    end,
    ["double click cannot grant or debit again"] = function()
        local state = assert(Core.new(Catalog))
        Core.seed(state, 11, 250)
        assert(Core.purchase(state, 11, "WoodenSword", 1))
        assert(Core.confirm(state, 11, "WoodenSword"))
        assert(not Core.purchase(state, 11, "WoodenSword", 1))
        assert(Core.balance(state, 11) == 175)
        assert(#Core.ownedIds(state, 11) == 1)
    end,
    ["pending grant can be refunded exactly once"] = function()
        local state = assert(Core.new(Catalog))
        Core.seed(state, 11, 250)
        assert(Core.purchase(state, 11, "WoodenSword", 1))
        assert(Core.rollback(state, 11, "WoodenSword"))
        assert(not Core.rollback(state, 11, "WoodenSword"))
        assert(Core.balance(state, 11) == 250)
        assert(not Core.has(state, 11, "WoodenSword"))
    end,
    ["confirmed purchase cannot be refunded arbitrarily"] = function()
        local state = assert(Core.new(Catalog))
        Core.seed(state, 11, 250)
        assert(Core.purchase(state, 11, "HealingKit", 1))
        assert(Core.confirm(state, 11, "HealingKit"))
        assert(not Core.rollback(state, 11, "HealingKit"))
        assert(Core.balance(state, 11) == 210)
    end,
    ["players have independent balances and inventory"] = function()
        local state = assert(Core.new(Catalog))
        Core.seed(state, 11, 250)
        Core.seed(state, 12, 50)
        assert(Core.purchase(state, 11, "WoodenSword", 1))
        assert(not Core.purchase(state, 12, "WoodenSword", 1))
        assert(Core.balance(state, 11) == 175 and Core.balance(state, 12) == 50)
    end,
    ["catalog copied before client-side modifications"] = function()
        local prices = {WoodenSword = 75}
        local state = assert(Core.new(prices))
        prices.WoodenSword = 1
        Core.seed(state, 11, 100)
        assert(Core.purchase(state, 11, "WoodenSword", 1))
        assert(Core.balance(state, 11) == 25)
    end,
    ["invalid catalog and player seed inputs refused"] = function()
        assert(Core.new({}) == nil)
        assert(Core.new({Bad = -1}) == nil)
        local state = assert(Core.new(Catalog))
        assert(not Core.seed(state, 0, 50))
        assert(not Core.seed(state, 11, -50))
        assert(not Core.purchase(state, 11, "WoodenSword", 1))
    end,
    ["respawn retains owned item list until player departs"] = function()
        local state = assert(Core.new(Catalog))
        Core.seed(state, 11, 250)
        assert(Core.purchase(state, 11, "HealingKit", 1))
        Core.confirm(state, 11, "HealingKit")
        assert(Core.ownedIds(state, 11)[1] == "HealingKit")
        assert(Core.removePlayer(state, 11))
        assert(#Core.ownedIds(state, 11) == 0)
    end,
}
