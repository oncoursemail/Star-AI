A tag binder has to cover three moments: instances that are already tagged, instances tagged later, and instances that lose the tag. The added and removed signals are connected first and the existing instances are handled afterwards, so nothing slips through between the two. A set of bound instances stops double handling, `pcall` keeps one broken handler from affecting the rest, and the returned function disconnects both signals and runs every live cleanup.

```luau
--!strict
local CollectionService = game:GetService("CollectionService")

local Tagged = {}

function Tagged.bind(tag: string, handler: (Instance) -> (() -> ())?): () -> ()
	local bound: { [Instance]: boolean } = {}
	local cleanups: { [Instance]: () -> () } = {}

	local function onAdded(instance: Instance)
		if bound[instance] then
			return
		end
		bound[instance] = true
		local ok, cleanup = pcall(handler, instance)
		if not ok then
			warn("Tagged.bind handler failed for " .. instance.Name .. ": " .. tostring(cleanup))
		elseif type(cleanup) == "function" then
			cleanups[instance] = cleanup
		end
	end

	local function onRemoved(instance: Instance)
		if not bound[instance] then
			return
		end
		bound[instance] = nil
		local cleanup = cleanups[instance]
		cleanups[instance] = nil
		if cleanup ~= nil then
			pcall(cleanup)
		end
	end

	local addedConnection = CollectionService:GetInstanceAddedSignal(tag):Connect(onAdded)
	local removedConnection = CollectionService:GetInstanceRemovedSignal(tag):Connect(onRemoved)
	for _, instance in CollectionService:GetTagged(tag) do
		onAdded(instance)
	end

	return function()
		addedConnection:Disconnect()
		removedConnection:Disconnect()
		local live = {}
		for instance in bound do
			table.insert(live, instance)
		end
		for _, instance in live do
			onRemoved(instance)
		end
	end
end

return Tagged
```
