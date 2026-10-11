The migration edits the table in place and fills the defaults with `or`.

```luau
local Migrate = {}

function Migrate.upgrade(data: any): ({ [string]: any }, number)
	local steps = 0
	if data.version == nil then
		data.coins = data.gold or 0
		data.gold = nil
		local counts = {}
		for _, name in data.items or {} do
			counts[name] = (counts[name] or 0) + 1
		end
		data.items = counts
		data.version = 2
		steps += 1
	end
	if data.version == 2 then
		data.version = 3
		steps += 1
	end
	data.settings = data.settings or {}
	data.settings.music = data.settings.music or true
	data.settings.sfx = data.settings.sfx or true
	return data, steps
end

return Migrate
```
