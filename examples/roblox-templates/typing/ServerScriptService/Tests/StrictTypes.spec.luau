--!strict
-- Offline Luau syntax/runtime smoke for types used by eng-debugging.
-- Roblox Model/Humanoid callbacks in the pack need Studio's type environment.
type NPC = {name: string, hp: number}
type Callback = (number) -> ()
type OptionalNPC = NPC?
type NamedNPC = typeof({name = "Scout", hp = 100})
local function heal(npc: NPC, points: number): number
    return npc.hp + points
end
return {
    ["strict alias and scalar annotations compile"] = function()
        local npc: NPC = {name = "Scout", hp = 10}
        local hp: number = heal(npc, 5)
        assert(hp == 15)
    end,
    ["typeof and optional alias compile"] = function()
        local npc: NamedNPC = {name = "Scout", hp = 100}
        local maybe: OptionalNPC = nil
        assert(npc.hp == 100 and maybe == nil)
    end,
    ["typed callback returns no values"] = function()
        local received = 0
        local callback: Callback = function(n: number)
            received = n
        end
        callback(7)
        assert(received == 7)
    end,
}
