Handle what is tagged now, then listen for new instances.

```luau
local CollectionService = game:GetService("CollectionService")

local Tagged = {}

function Tagged.bind(tag: string, handler: (Instance) -> (() -> ())?): () -> ()
	local cleanups = {}
	for _, instance in CollectionService:GetTagged(tag) do
		cleanups[instance] = handler(instance)
	end
	local added = CollectionService:GetInstanceAddedSignal(tag):Connect(function(instance)
		cleanups[instance] = handler(instance)
	end)
	local removed = CollectionService:GetInstanceRemovedSignal(tag):Connect(function(instance)
		if cleanups[instance] then
			cleanups[instance]()
		end
	end)
	return function()
		added:Disconnect()
		removed:Disconnect()
	end
end

return Tagged
```
