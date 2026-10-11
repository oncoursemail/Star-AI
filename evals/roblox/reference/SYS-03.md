```luau
--!strict
type Config = { baseIncome: number, incomePerLevel: number, baseCost: number, growth: number, upgrades: number }

local function simulate(config: Config): { number }
	local bought: { number } = {}
	local coins, income, level, second = 0, config.baseIncome, 0, 0
	while #bought < config.upgrades do
		second += 1
		coins += income
		while #bought < config.upgrades do
			local cost = math.ceil(config.baseCost * config.growth ^ level)
			if coins < cost then
				break
			end
			coins -= cost
			income += config.incomePerLevel
			level += 1
			table.insert(bought, second)
		end
	end
	return bought
end

return simulate
```

For the given config the purchases happen at seconds 10, 18, 26, 34, 45, 57, 74, 95, 124 and 162. The gap between purchases grows from 8 s to 38 s, so the pacing slows down steadily.
