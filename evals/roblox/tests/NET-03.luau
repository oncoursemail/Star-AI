local now = 0
local clock = function() return now end
local playersSvc = { PlayerRemoving = Signal.new(), PlayerAdded = Signal.new(), GetPlayers = function() return {} end }
local g = mockGame({ Players = playersSvc })
local Gate = load_answer({
	game = g, workspace = { GetServerTimeNow = clock },
	os = { clock = clock, time = clock, date = os.date }, time = clock, tick = clock,
})
local A = { Name = "A", UserId = 1 }
local B = { Name = "B", UserId = 2 }
local C = { Name = "C", UserId = 3 }
local accepted, firstAt = 0, nil
for i = 1, 100 do
	now = i * 0.01
	if Gate.tryUse(A) then
		accepted += 1
		firstAt = firstAt or now
	end
end
check("100 calls within 1 second: exactly one is accepted", accepted == 1)
now = (firstAt or 0) + 2.1
check("a call 2.1 s after the accepted one is allowed", Gate.tryUse(A) == true)
now += 8
check("players are gated independently", Gate.tryUse(B) == true and Gate.tryUse(C) == true and Gate.tryUse(B) == false)
local before = Gate.trackedCount()
playersSvc.PlayerRemoving:Fire(B)
check("PlayerRemoving drops trackedCount by one", Gate.trackedCount() == before - 1)
