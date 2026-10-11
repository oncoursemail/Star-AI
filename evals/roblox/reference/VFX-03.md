```luau
local EffectPool = {}
EffectPool.__index = EffectPool

function EffectPool.new(maxActive: number, factory: () -> any)
	return setmetatable({ maxActive = maxActive, factory = factory, idle = {}, active = {}, activeN = 0, created = 0 }, EffectPool)
end

function EffectPool:acquire(): any?
	if self.activeN >= self.maxActive then
		return nil
	end
	local n = #self.idle
	local effect
	if n > 0 then
		effect = self.idle[n]
		self.idle[n] = nil
	else
		effect = self.factory()
		self.created += 1
	end
	self.active[effect] = true
	self.activeN += 1
	return effect
end

function EffectPool:release(effect: any)
	if effect ~= nil and self.active[effect] then
		self.active[effect] = nil
		self.activeN -= 1
		table.insert(self.idle, effect)
	end
end

function EffectPool:activeCount(): number
	return self.activeN
end

function EffectPool:totalCreated(): number
	return self.created
end

return EffectPool
```
