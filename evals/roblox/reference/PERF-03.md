```luau
local BulletPool = {}
BulletPool.__index = BulletPool

function BulletPool.new(size: number, template: BasePart)
	local self = setmetatable({ _idle = {}, _isIdle = {} }, BulletPool)
	for _ = 1, size do
		local part = template:Clone()
		part.Parent = nil
		table.insert(self._idle, part)
		self._isIdle[part] = true
	end
	return self
end

function BulletPool:get(): BasePart?
	local part = table.remove(self._idle)
	if part == nil then
		return nil
	end
	self._isIdle[part] = nil
	part.Parent = workspace
	return part
end

function BulletPool:release(part: BasePart)
	if self._isIdle[part] then
		return
	end
	part.Parent = nil
	self._isIdle[part] = true
	table.insert(self._idle, part)
end

function BulletPool:idleCount(): number
	return #self._idle
end

return BulletPool
```
