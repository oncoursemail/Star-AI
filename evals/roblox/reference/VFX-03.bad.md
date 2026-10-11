```luau
local EffectPool = {}
EffectPool.__index = EffectPool
function EffectPool.new(maxActive: number, factory: () -> any)
	return setmetatable({ maxActive = maxActive, factory = factory, idle = {}, activeN = 0, created = 0 }, EffectPool)
end
function EffectPool:acquire(): any?
	if self.activeN >= self.maxActive then return nil end
	self.activeN += 1
	local n = #self.idle
	if n > 0 then
		local e = self.idle[n]
		self.idle[n] = nil
		return e
	end
	self.created += 1
	return self.factory()
end
function EffectPool:release(effect: any)
	self.activeN -= 1
	table.insert(self.idle, effect)
end
function EffectPool:activeCount(): number return self.activeN end
function EffectPool:totalCreated(): number return self.created end
return EffectPool
```
