local timeLeft = Instance.new("IntValue")
timeLeft.Name = "TimeLeft"
timeLeft.Value = 10
timeLeft.Parent = script.Parent
local status = Instance.new("StringValue")
status.Name = "Status"
status.Value = "Running"
status.Parent = script.Parent
while timeLeft.Value > 0 do
	task.wait(1)
	timeLeft.Value -= 1
end
status.Value = "Ended"
