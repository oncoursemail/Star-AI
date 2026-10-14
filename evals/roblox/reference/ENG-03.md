The cause is a race: Touched fires once per part that touches the coin, so a second touch can start another handler before the first one destroys the coin. The fix claims the coin before paying.

```luau
local Players = game:GetService("Players")
local coin = script.Parent
local collected = false

coin.Touched:Connect(function(hit)
	if collected then
		return
	end
	local player = Players:GetPlayerFromCharacter(hit.Parent)
	if not player then
		return
	end
	collected = true
	local stats = player:FindFirstChild("leaderstats")
	local coins = stats and stats:FindFirstChild("Coins")
	if coins then
		coins.Value += 10
	end
	coin:Destroy()
end)
```

What I checked: I traced the old and new code by hand with two Touched events in the same frame; the old code reaches the award twice, the new code returns at `if collected`. I have not run it in Studio. To verify, walk over the coin and also touch it with two limbs: the Coins value should rise by exactly 10 once.
