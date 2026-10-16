local M = {}
function M.pick(weights: { [string]: number }, rng: Random): string
	local keys, total = {}, 0
	for key, weight in weights do
		if weight > 0 then
			table.insert(keys, key)
			total += weight
		end
	end
	if total <= 0 then error("total weight must be > 0") end
	table.sort(keys)
	local roll = rng:NextNumber() * total
	for _, key in keys do
		roll -= weights[key]
		if roll < 0 then return key end
	end
	return keys[#keys]
end
return M
