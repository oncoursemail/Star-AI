Root cause: `state.last[ability]` is nil before the first use, and `COOLDOWNS[ability]` is nil for an unknown ability, so the subtraction and the comparison see nil.

```luau
local COOLDOWNS = { dash = 3, fireball = 8 }

local function tryUse(state, ability, now)
	local cooldown = COOLDOWNS[ability]
	if cooldown == nil then
		return false
	end
	local last = state.last[ability]
	if last == nil or now - last >= cooldown then
		state.last[ability] = now
		return true
	end
	return false
end

return tryUse
```
