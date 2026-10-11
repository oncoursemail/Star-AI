local ret, env = load_answer()
local Pool = (type(ret) == "table" and ret.new ~= nil and ret) or (type(ret) == "table" and ret.EffectPool) or env.EffectPool
local made = 0
local function factory()
	made += 1
	return { id = made }
end
local pool = Pool.new(3, factory)
local a, b, c = pool:acquire(), pool:acquire(), pool:acquire()
check("three acquires give three distinct objects", a ~= nil and b ~= nil and c ~= nil and a ~= b and b ~= c and a ~= c)
check("a 4th acquire returns nil at the cap", pool:acquire() == nil)
check("activeCount is 3 and totalCreated is 3", pool:activeCount() == 3 and pool:totalCreated() == 3)
pool:release(b)
check("activeCount drops to 2 after a release", pool:activeCount() == 2)
local again = pool:acquire()
check("a released object is reused and nothing new is built", again == b and made == 3 and pool:totalCreated() == 3)
pool:release(a)
pool:release(a)
check("a double release counts once", pool:activeCount() == 2)
local x1 = pool:acquire()
local x2 = pool:acquire()
check("after a double release exactly one extra object is available", x1 == a and x2 == nil)
pool:release({})
check("releasing a foreign object changes nothing", pool:activeCount() == 3)
local okZero, zero = pcall(Pool.new, 0, factory)
check("maxActive 0 is rejected or never builds anything", not okZero or (zero:acquire() == nil and zero:totalCreated() == 0))
local before = made
local p3 = Pool.new(2, factory)
for _ = 1, 50 do
	local o = p3:acquire()
	if o then p3:release(o) end
end
check("50 acquire/release cycles build only one object", made - before == 1)
