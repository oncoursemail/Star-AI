local ret, env = load_answer()
local pack = resolve(ret, env, "pack")
local function triple(flags)
	local a, b, c = pack(flags)
	return a, b, c
end
local a, b, c = triple({ true, false, true, true })
check("pack({T,F,T,T}) returns 13, 3, 6", a == 13 and b == 3 and c == 6)
a, b, c = triple({})
check("pack({}) returns 0, 0, 0", a == 0 and b == 0 and c == 0)
local all = {}
for i = 1, 16 do all[i] = true end
a, b, c = triple(all)
check("16 true flags return 65535, 16383, 32767", a == 65535 and b == 16383 and c == 32767)
