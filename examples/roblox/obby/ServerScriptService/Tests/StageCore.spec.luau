--!strict
local Core = require("../StageCore")

return {
    ["sequential checkpoints raise stage"] = function()
        local state = assert(Core.new(3))
        assert(Core.stage(state, 11) == 0)
        assert(Core.advance(state, 11, 1))
        assert(Core.advance(state, 11, 2))
        assert(Core.stage(state, 11) == 2)
    end,
    ["skipped checkpoint is refused"] = function()
        local state = assert(Core.new(4))
        assert(not Core.advance(state, 11, 3))
        assert(Core.stage(state, 11) == 0)
    end,
    ["duplicate touches are idempotent"] = function()
        local state = assert(Core.new(2))
        assert(Core.advance(state, 11, 1))
        assert(not Core.advance(state, 11, 1))
        assert(Core.stage(state, 11) == 1)
    end,
    ["negative fractional and oversized checkpoints rejected"] = function()
        local state = assert(Core.new(2))
        for _, stage in {-1, 0, 1.5, 3} do
            assert(not Core.advance(state, 11, stage))
        end
        assert(Core.stage(state, 11) == 0)
    end,
    ["malformed or empty stage configuration rejected"] = function()
        for _, value in {0, -1, 1.3, 65, "bad"} do
            assert(Core.new(value) == nil)
        end
    end,
    ["one player cannot progress another"] = function()
        local state = assert(Core.new(2))
        assert(Core.advance(state, 11, 1))
        assert(Core.stage(state, 12) == 0)
        assert(Core.stage(state, 11) == 1)
    end,
    ["finish requires last checkpoint"] = function()
        local state = assert(Core.new(2))
        assert(not Core.claimFinish(state, 11))
        assert(Core.advance(state, 11, 1))
        assert(not Core.claimFinish(state, 11))
    end,
    ["finish grants exactly once"] = function()
        local state = assert(Core.new(2))
        assert(Core.advance(state, 11, 1))
        assert(Core.advance(state, 11, 2))
        assert(Core.claimFinish(state, 11))
        assert(not Core.claimFinish(state, 11))
    end,
    ["different players may finish independently"] = function()
        local state = assert(Core.new(1))
        assert(Core.advance(state, 11, 1))
        assert(Core.advance(state, 12, 1))
        assert(Core.claimFinish(state, 11))
        assert(Core.claimFinish(state, 12))
    end,
    ["kill brick debounce rejects repeated contact"] = function()
        local state = assert(Core.new(1))
        assert(Core.shouldKill(state, 11, 1.0, 0.75))
        assert(not Core.shouldKill(state, 11, 1.4, 0.75))
        assert(Core.shouldKill(state, 11, 1.8, 0.75))
    end,
    ["invalid kill time and cooldown rejected"] = function()
        local state = assert(Core.new(1))
        assert(not Core.shouldKill(state, 0, 2, 1))
        assert(not Core.shouldKill(state, 11, -1, 1))
        assert(not Core.shouldKill(state, 11, 1, -1))
        assert(not Core.shouldKill(state, 11, 0/0, 1))
        assert(not Core.shouldKill(state, 11, 2, math.huge))
    end,
    ["removal clears player state"] = function()
        local state = assert(Core.new(1))
        assert(Core.advance(state, 11, 1))
        assert(Core.claimFinish(state, 11))
        assert(Core.removePlayer(state, 11))
        assert(Core.stage(state, 11) == 0)
        assert(Core.advance(state, 11, 1))
        assert(Core.claimFinish(state, 11))
    end,
}
