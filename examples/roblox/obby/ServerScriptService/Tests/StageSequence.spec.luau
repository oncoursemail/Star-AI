--!strict
-- Pure StageCore multi-action invariants: native Luau only, not engine Touched/respawn.
local Core = require("../StageCore")

local function orderedCheckpointsInvariant(api)
    local state = assert(api.new(4))
    assert(api.advance(state, 11, 1))
    assert(not api.advance(state, 11, 3), "skipping checkpoint 2 must fail")
    assert(api.stage(state, 11) == 1, "skipped checkpoint changed state")
    assert(api.advance(state, 11, 2))
    assert(api.stage(state, 11) == 2)
end

return {
    ["interleaved checkpoints prevent skips and award each player once"] = function()
        local state = assert(Core.new(4))
        assert(not Core.claimFinish(state, 11))
        assert(not Core.advance(state, 11, 2))
        assert(Core.advance(state, 11, 1))
        assert(not Core.advance(state, 11, 1))
        assert(Core.advance(state, 12, 1))
        assert(not Core.advance(state, 12, 3))
        assert(Core.advance(state, 11, 2))
        assert(not Core.advance(state, 11, 4))
        assert(Core.advance(state, 11, 3))
        assert(Core.advance(state, 11, 4))
        assert(Core.claimFinish(state, 11))
        assert(not Core.claimFinish(state, 11))
        assert(not Core.advance(state, 11, 4))
        assert(Core.stage(state, 12) == 1)
        assert(not Core.claimFinish(state, 12))
        assert(Core.advance(state, 12, 2))
        assert(Core.advance(state, 12, 3))
        assert(Core.advance(state, 12, 4))
        assert(Core.claimFinish(state, 12))
        assert(not Core.claimFinish(state, 12))
        assert(Core.stage(state, 11) == 4)
        assert(Core.stage(state, 12) == 4)
    end,

    ["departure resets only removed stages rewards and hazard clock"] = function()
        local state = assert(Core.new(2))
        assert(Core.advance(state, 11, 1))
        assert(Core.advance(state, 11, 2))
        assert(Core.claimFinish(state, 11))
        assert(Core.advance(state, 12, 1))
        assert(Core.shouldKill(state, 11, 10, 1))
        assert(Core.shouldKill(state, 12, 10, 1))
        assert(not Core.shouldKill(state, 11, 10.5, 1))
        assert(Core.removePlayer(state, 11))
        assert(Core.stage(state, 11) == 0)
        assert(Core.stage(state, 12) == 1)
        assert(not Core.claimFinish(state, 11))
        assert(not Core.advance(state, 11, 2))
        assert(Core.shouldKill(state, 11, 10.5, 1))
        assert(not Core.shouldKill(state, 12, 10.5, 1))
        assert(Core.advance(state, 11, 1))
        assert(Core.advance(state, 11, 2))
        assert(Core.claimFinish(state, 11))
        assert(not Core.claimFinish(state, 11))
        assert(Core.advance(state, 12, 2))
        assert(Core.claimFinish(state, 12))
        assert(not Core.claimFinish(state, 12))
    end,

    ["kill cooldown is independent monotonic and exact at boundary"] = function()
        local state = assert(Core.new(1))
        assert(Core.shouldKill(state, 11, 0, 0.75))
        assert(not Core.shouldKill(state, 11, 0, 0.75))
        assert(not Core.shouldKill(state, 11, 0.749, 0.75))
        assert(Core.shouldKill(state, 12, 0.25, 0.75))
        assert(Core.shouldKill(state, 11, 0.75, 0.75))
        assert(not Core.shouldKill(state, 11, 0.7, 0.75))
        assert(not Core.shouldKill(state, 11, 1.49, 0.75))
        assert(Core.shouldKill(state, 11, 1.5, 0.75))
        assert(not Core.shouldKill(state, 12, 0.999, 0.75))
        assert(Core.shouldKill(state, 12, 1, 0.75))
        assert(Core.removePlayer(state, 12))
        assert(Core.shouldKill(state, 12, 1.1, 0.75))
        assert(not Core.shouldKill(state, 12, 1.11, 0.75))
    end,

    ["malformed input is a refusal and internal corruption is not a normal request"] = function()
        local state = assert(Core.new(3))
        assert(Core.advance(state, 11, 1))
        for _, value in {0, -1, 1.5, 4, math.huge, -math.huge, 0 / 0} do
            assert(not Core.advance(state, 11, value))
            assert(Core.stage(state, 11) == 1)
        end
        assert(not Core.advance(state, 0, 2))
        assert(not Core.advance(state, math.huge, 2))
        assert(not Core.claimFinish(state, -1))
        assert(not Core.shouldKill(state, 11, 0 / 0, 0.75))
        assert(not Core.shouldKill(state, 11, 2, -0.75))
        assert(Core.stage(state, 11) == 1)
        -- An impossible corrupted server-owned stage is not an invalid player request.
        state.stages[11] = "corrupt"
        assert(not pcall(function() Core.advance(state, 11, 2) end))
        state.stages[11] = 1
        assert(Core.advance(state, 11, 2))
        assert(Core.advance(state, 11, 3))
        assert(Core.claimFinish(state, 11))
    end,

    ["finish and checkpoint state survive valid repeated contacts without reset"] = function()
        local state = assert(Core.new(1))
        assert(Core.advance(state, 11, 1))
        assert(Core.claimFinish(state, 11))
        for _ = 1, 20 do
            assert(not Core.advance(state, 11, 1))
            assert(not Core.claimFinish(state, 11))
            assert(Core.stage(state, 11) == 1)
        end
        assert(Core.advance(state, 12, 1))
        assert(Core.claimFinish(state, 12))
        assert(not Core.claimFinish(state, 11))
        assert(not Core.claimFinish(state, 12))
    end,

    ["fixed-seed three-player action history follows reference state"] = function()
        local state = assert(Core.new(4))
        local players = {11, 12, 13}
        local stageByPlayer = {[11] = 0, [12] = 0, [13] = 0}
        local finished = {[11] = false, [12] = false, [13] = false}
        local offsets = {1, 0, 2}
        local seed = 37
        for step = 1, 144 do
            seed = (seed * 71 + 29) % 997
            local id = players[(seed % #players) + 1]
            seed = (seed * 43 + 7) % 997
            local action = seed % 6
            if action <= 2 then
                local target = stageByPlayer[id] + offsets[action + 1]
                local allowed = target >= 1 and target <= 4 and target == stageByPlayer[id] + 1
                assert(Core.advance(state, id, target) == allowed,
                    "checkpoint diverged at step " .. step)
                if allowed then stageByPlayer[id] = target end
            elseif action == 3 then
                local allowed = stageByPlayer[id] == 4 and not finished[id]
                assert(Core.claimFinish(state, id) == allowed,
                    "finish diverged at step " .. step)
                if allowed then finished[id] = true end
            elseif action == 4 then
                assert(Core.removePlayer(state, id))
                stageByPlayer[id] = 0
                finished[id] = false
            else
                assert(Core.shouldKill(state, id, step, 0.75))
            end
            for _, player in players do
                assert(Core.stage(state, player) == stageByPlayer[player],
                    "stage diverged at step " .. step)
            end
        end
    end,

    ["negative skipped-checkpoint mutant is caught by real progression invariant"] = function()
        orderedCheckpointsInvariant(Core)
        local mutant = setmetatable({}, {__index = Core})
        mutant.advance = function(state, id, stage)
            if state.stages[id] == 1 and stage == 3 then
                -- Deliberately incorrect implementation: allow jumping over stage 2.
                state.stages[id] = stage
                return true, stage
            end
            return Core.advance(state, id, stage)
        end
        local survived = pcall(function() orderedCheckpointsInvariant(mutant) end)
        assert(not survived, "deliberate checkpoint-skip mutant escaped the invariant")
    end,
}
