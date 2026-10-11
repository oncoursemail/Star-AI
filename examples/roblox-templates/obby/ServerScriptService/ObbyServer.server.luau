--!strict
-- Boot order matters: build the pads before wiring touches or placing characters.
local Players = game:GetService("Players")
local CourseBuilder = require(script.Parent.CourseBuilder)
local PlayerData = require(script.Parent.PlayerData)
local CheckpointService = require(script.Parent.CheckpointService)
local KillService = require(script.Parent.KillService)
local FinishService = require(script.Parent.FinishService)

local course = CourseBuilder.build()
CheckpointService.connect(course.checkpoints, PlayerData.advance)
KillService.connect(course.killParts)
FinishService.connect(course.finish, PlayerData.finish)

local function placeCharacter(player: Player, character: Model)
	task.spawn(function()
		local root = character:WaitForChild("HumanoidRootPart", 10)
		if not root or not root:IsA("BasePart") then
			return
		end
		while player.Parent == Players and player.Character == character do
			local stage = PlayerData.getStage(player)
			if stage then
				character:PivotTo(course.respawns[stage] or course.respawns[1])
				return
			end
			task.wait(0.1)
		end
	end)
end

local function onPlayerAdded(player: Player)
	player.RespawnLocation = course.spawn
	player.CharacterAdded:Connect(function(character: Model)
		placeCharacter(player, character)
	end)
	if player.Character then
		placeCharacter(player, player.Character)
	end
	if not PlayerData.load(player) and player.Parent == Players then
		player:Kick("Progress could not be loaded safely. Please rejoin.")
	end
end

Players.PlayerAdded:Connect(function(player: Player)
	task.spawn(onPlayerAdded, player)
end)
for _, player in ipairs(Players:GetPlayers()) do
	task.spawn(onPlayerAdded, player)
end

Players.PlayerRemoving:Connect(function(player: Player)
	PlayerData.close(player)
end)

task.spawn(function()
	while true do
		task.wait(30)
		PlayerData.autosave()
	end
end)

game:BindToClose(function()
	local pending = 0
	for _, player in ipairs(Players:GetPlayers()) do
		pending += 1
		task.spawn(function()
			PlayerData.close(player)
			pending -= 1
		end)
	end
	local deadline = os.clock() + 25
	while pending > 0 and os.clock() < deadline do
		task.wait(0.1)
	end
end)
