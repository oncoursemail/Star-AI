"""Per-cause practice tasks with real runnable checks (W4 of docs/research/self-improving-star-claude-v2.md).

The failure ledger (star/failure_ledger.py) labels every failed evaluation attempt with one of five causes. This module
holds one family of task specifications per cause, so a practice task named after a cause really exercises it:

* wrong logic            - small behaviour specs with exact boundaries (cooldowns, falloff, ranking ties, ...); the
                           unit test pins the edge cases, the bad answer has the classic off-by-one / tie bug;
* required feature missing - specs that enumerate every method; the unit test asserts each one exists
                           ("required feature: X") and works; the bad answer leaves one method out;
* self-check error left unrepaired - `--!strict` modules; the bad answer carries a real strict-mode type or parse
                           error that Luau's own checker reports (and that also breaks the run);
* answer cut off          - long modules (8-9 functions) that must be finished in one compact block; the bad answer
                           stops mid-module inside an unclosed code fence;
* invented API name       - utilities that must use Luau's real built-in libraries; the bad answer calls a helper
                           module that does not exist (Luau reports "Unknown global").

Every task has: a runtime unit test executed in the server's Luau VM with the evaluation harness prelude
(evals/roblox/prelude.luau), static Luau checking, required/forbidden patterns, a reference answer that must pass and a
bad answer that must fail **for its named cause** (the ledger's own rules label the bad answer's result record).

Nothing here reads the blind holdout, a golden prompt or a stored answer. Reference and bad answers are only written to a
separate self-test folder, never into a practice pool. Pure Python; no model, no network.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
import math
import re
from string import Template

FENCE = chr(96) * 3

WL, RF, SC, CO, IA = ("wrong logic", "required feature missing", "self-check error left unrepaired",
                      "answer cut off", "invented API name")
CAUSE_CODES = {WL: "WL", RF: "RF", SC: "SC", CO: "CO", IA: "IA"}
CAUSE_SLUGS = {WL: "logic-edge-cases", RF: "complete-api", SC: "strict-types", CO: "long-module",
               IA: "real-builtins"}
CAUSE_TAILS = {
    WL: "Watch the exact boundaries: the tests check the edge cases named above. Return one fenced Luau code block "
        "with the ModuleScript; it must run as plain Luau without Roblox services.",
    RF: "Implement every listed function or method; a missing one fails the task. Return one fenced Luau code block "
        "with the ModuleScript; it must run as plain Luau without Roblox services.",
    SC: "Start the module with --!strict and annotate the functions; it must pass Luau strict type checking with no "
        "errors and must parse cleanly. Return one fenced Luau code block with the ModuleScript.",
    CO: "Write the whole module in ONE fenced Luau code block, compact: no comments and no explanation, and finish "
        "with the module's return statement. An unfinished module fails.",
    IA: "Use only Luau's real built-in libraries (string, table, math, bit32, os.time) and functions you define "
        "yourself; do not call helper modules that are not defined in your answer. Return one fenced Luau code block "
        "with the ModuleScript.",
}

TEST_HEAD = """local ret, env = load_answer()
local M = type(ret) == "table" and ret or {}
local function safe(f)
	local ok, v = pcall(f)
	return ok and v == true
end
"""


@dataclass(frozen=True)
class Variant:
    prompt: str
    test: str            # Luau body appended after the harness prelude
    reference: str       # Luau code of a correct answer
    bad: str             # the full text of a bad answer (may be an unclosed fence on purpose)
    require: tuple = ()
    forbid: tuple = ()
    strict: bool = False
    static_error: str = ""   # regex the real Luau checker is expected to print for the bad answer ("" = none)


@dataclass(frozen=True)
class Spec:
    key: str
    cause: str
    goal: str
    contexts: tuple
    build: object = field(repr=False)   # (variant index, context) -> Variant
    variants: int = 10


def _q(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def lua_list(values) -> str:
    out = []
    for v in values:
        out.append(_q(v) if isinstance(v, str) else repr(v) if not isinstance(v, bool) else str(v).lower())
    return "{ " + ", ".join(out) + " }" if out else "{}"


def _t(_tpl: str, **values) -> str:
    return Template(_tpl).substitute(**{k: str(v) for k, v in values.items()})


def _num(x) -> str:
    """A Luau number literal (integers without a trailing .0)."""
    return str(int(x)) if float(x).is_integer() else repr(float(x))


def _fence(code: str) -> str:
    return FENCE + "luau\n" + code.strip("\n") + "\n" + FENCE


def _pattern(pid: str, regex: str, why: str) -> dict:
    return {"id": pid, "re": regex, "why": why, "scope": "code"}


def _raw(pid: str, regex: str, why: str) -> dict:
    """A pattern on the code as written (comments kept): `--!strict` is a comment to the default "code" scope."""
    return {"id": pid, "re": regex, "why": why, "scope": "raw"}


def _method(name: str) -> dict:
    return _pattern("defines_" + name.lower(), r"function\s+\w+\s*[:.]\s*" + name + r"\s*\(", f"defines {name}")


def count_checks(test_body: str) -> int:
    return len(re.findall(r'(?m)^\s*check\(', test_body))


# =====================================================================================================================
# wrong logic: exact edge cases
# =====================================================================================================================

def _wl_cooldown(v: int, ctx: str) -> Variant:
    d = (1.5, 2, 3, 4, 5, 6, 8, 10, 0.5, 2.5)[v % 10]
    prompt = (f"For {ctx} in my Roblox game (the game uses a {_num(d)} second cooldown), write a ModuleScript Cooldown "
              "with Cooldown.new(duration) returning an object with a method :tryUse(now: number): boolean. tryUse "
              "returns true and records the use when the object has never been used, or when at least `duration` "
              "seconds have passed since the last SUCCESSFUL use (exactly `duration` seconds later counts as ready). "
              "Otherwise it returns false and changes nothing, so a refused attempt never restarts the timer. Each "
              "object keeps its own timer.")
    ref = """local Cooldown = {}
Cooldown.__index = Cooldown
function Cooldown.new(duration: number)
	return setmetatable({ duration = duration, last = -math.huge }, Cooldown)
end
function Cooldown:tryUse(now: number): boolean
	if now - self.last >= self.duration then
		self.last = now
		return true
	end
	return false
end
return Cooldown"""
    bad = ref.replace(">= self.duration", "> self.duration")
    test = TEST_HEAD + _t("""local d = $d
local c = M.new and select(2, pcall(M.new, d)) or {}
local c2 = M.new and select(2, pcall(M.new, d)) or {}
check("the first use is allowed", safe(function() return c:tryUse(0) == true end))
check("a use before the cooldown ends is refused", safe(function() return c:tryUse(d - 0.25) == false end))
check("exactly duration seconds later is ready", safe(function() return c:tryUse(d) == true end))
check("the timer restarts from the last successful use", safe(function() return c:tryUse(2 * d - 0.25) == false end))
check("a refused attempt does not restart the timer", safe(function() return c:tryUse(2 * d) == true end))
check("separate objects keep separate timers", safe(function() return c2:tryUse(2 * d + 0.25) == true and c:tryUse(2 * d + 0.25) == false end))
""", d=_num(d))
    return Variant(prompt, test, ref, _fence(bad), (_method("tryUse"),))


def _wl_falloff(v: int, ctx: str) -> Variant:
    top, near = 20 + 5 * v, 4 + v
    far = near + 10 + 2 * v

    def dmg(x):
        if x <= near:
            return top
        if x >= far:
            return 0
        return math.floor(Fraction(top * (far - x), far - near))
    mid = (near + far) // 2
    prompt = (f"For {ctx}, write a ModuleScript that returns a function damageAt(distance: number): number. Damage is "
              f"{top} at any distance up to and including {near} studs (negative distances count as 0), falls off "
              f"linearly to 0 at {far} studs, and is 0 at or beyond {far} studs. Round the linear part down with "
              "math.floor.")
    ref = _t("""local function damageAt(distance: number): number
	if distance <= $near then
		return $top
	end
	if distance >= $far then
		return 0
	end
	return math.floor($top * ($far - distance) / ($far - $near))
end
return damageAt""", near=near, top=top, far=far)
    bad = _t("""local function damageAt(distance: number): number
	if distance <= $near then
		return $top
	end
	return math.floor($top * ($far - distance) / ($far - $near))
end
return damageAt""", near=near, top=top, far=far)
    test = _t("""local ret, env = load_answer()
local damageAt = resolve(ret, env, "damageAt")
local function at(x, want)
	local ok, v = pcall(damageAt, x)
	return ok and v == want
end
check("full damage at distance 0", at(0, $top))
check("full damage exactly at the near distance", at($near, $top))
check("negative distance counts as full damage", at(-3, $top))
check("one stud past near is on the falloff line", at($n1, $d1))
check("the midpoint is rounded down", at($mid, $dmid))
check("zero exactly at the far distance", at($far, 0))
check("zero beyond the far distance, never negative", at($beyond, 0))
""", top=top, near=near, n1=near + 1, d1=dmg(near + 1), mid=mid, dmid=dmg(mid), far=far, beyond=far + 25)
    return Variant(prompt, test, ref, _fence(bad), (_pattern("floor", r"math\s*\.\s*floor\s*\(", "rounds down"),))


def _wl_history(v: int, ctx: str) -> Variant:
    cap = 3 + v % 5
    msgs = [f"{('m', 'k', 't', 'x', 'z')[v // 5 % 5]}{i}" for i in range(1, cap + 3)]
    prompt = (f"For {ctx}, write a ModuleScript History with History.new(capacity) returning an object with "
              ":push(text: string) and :list(): {string}. The object keeps only the newest `capacity` entries "
              f"(the game uses capacity {cap}); list() returns them oldest first as a NEW table, so changing the "
              "returned table never changes the history.")
    ref = """local History = {}
History.__index = History
function History.new(capacity: number)
	return setmetatable({ capacity = capacity, items = {} }, History)
end
function History:push(text: string)
	table.insert(self.items, text)
	if #self.items > self.capacity then
		table.remove(self.items, 1)
	end
end
function History:list(): { string }
	return table.clone(self.items)
end
return History"""
    bad = """local History = {}
History.__index = History
function History.new(capacity: number)
	return setmetatable({ capacity = capacity, items = {}, slot = 1 }, History)
end
function History:push(text: string)
	self.items[self.slot] = text
	self.slot = self.slot % self.capacity + 1
end
function History:list(): { string }
	return table.clone(self.items)
end
return History"""
    test = TEST_HEAD + _t("""local h = M.new and select(2, pcall(M.new, $cap)) or {}
local h2 = M.new and select(2, pcall(M.new, $cap)) or {}
check("an empty history lists nothing", safe(function() return #h:list() == 0 end))
pcall(function() h2:push("a") h2:push("b") end)
check("before it is full, entries come oldest first", safe(function() return deepEqual(h2:list(), { "a", "b" }) end))
pcall(function() for _, m in $msgs do h:push(m) end end)
check("after overflowing, only the newest entries remain, oldest first", safe(function() return deepEqual(h:list(), $kept) end))
check("the returned table is a copy", safe(function() local l = h:list() l[1] = "changed" return h:list()[1] == $first end))
pcall(function() h:push("late") end)
check("one more push drops exactly the oldest entry", safe(function() local l = h:list() return #l == $cap and l[#l] == "late" and l[1] == $second end))
""", cap=cap, msgs=lua_list(msgs), kept=lua_list(msgs[-cap:]), first=_q(msgs[-cap]), second=_q(msgs[-cap + 1]))
    return Variant(prompt, test, ref, _fence(bad), (_method("push"), _method("list")))


_RANK_NAMES = ("Ava", "Ben", "Cleo", "Dax", "Eli", "Faye", "Gus", "Hana", "Ivo", "Juno", "Kai", "Lux")


def _rank_data(v: int):
    names = [_RANK_NAMES[(v + 3 * i) % len(_RANK_NAMES)] for i in range(6)]
    scores = [40 + ((v * 7 + i * 13) % 5) * 10 for i in range(6)]
    scores[(v + 1) % 6] = scores[(v + 4) % 6] = max(scores)   # a tie above other scores
    rows = sorted(zip(names, scores), key=lambda r: (-r[1], r[0]))
    places, prev = [], None
    for i, (_, s) in enumerate(rows, 1):
        places.append(places[-1] if prev == s else i)
        prev = s
    return list(zip(names, scores)), [n for n, _ in rows], places


def _wl_rank(v: int, ctx: str) -> Variant:
    entries, order, places = _rank_data(v)
    prompt = (f"For {ctx}, write a ModuleScript that returns a function rank(entries) where entries is an array of "
              "{ name: string, score: number }. Return a NEW array of { name, score, place } sorted by score from "
              "high to low, with equal scores ordered by name alphabetically. place uses standard competition "
              "ranking: equal scores share a place and the next place skips (1, 2, 2, 4). Do not modify the input.")
    ref = """local function rank(entries)
	local out = {}
	for i, e in entries do
		out[i] = { name = e.name, score = e.score, place = 0 }
	end
	table.sort(out, function(a, b)
		if a.score ~= b.score then
			return a.score > b.score
		end
		return a.name < b.name
	end)
	for i, e in out do
		if i > 1 and out[i - 1].score == e.score then
			e.place = out[i - 1].place
		else
			e.place = i
		end
	end
	return out
end
return rank"""
    bad = ref.replace("""		else
			e.place = i
		end""", """		elseif i > 1 then
			e.place = out[i - 1].place + 1
		else
			e.place = 1
		end""")
    rows = ", ".join("{ name = %s, score = %d }" % (_q(n), s) for n, s in entries)
    test = _t("""local ret, env = load_answer()
local rank = resolve(ret, env, "rank")
local function safe(f)
	local ok, v = pcall(f)
	return ok and v == true
end
local input = { $rows }
local ok, out = pcall(rank, input)
if not ok or type(out) ~= "table" then out = {} end
local names, places = {}, {}
for i, e in out do names[i] = e.name places[i] = e.place end
check("sorted by score high to low, ties by name", deepEqual(names, $order))
check("equal scores share a place and the next place skips", deepEqual(places, $places))
check("the input array is not reordered", input[1].name == $first)
check("the input entries are not given a place", input[1].place == nil)
check("an empty list ranks to an empty list", safe(function() return #rank({}) == 0 end))
""", rows=rows, order=lua_list(order), places=lua_list(places), first=_q(entries[0][0]))
    return Variant(prompt, test, ref, _fence(bad), (_pattern("sorts", r"table\s*\.\s*sort\s*\(", "sorts with table.sort"),))


def _wl_waves(v: int, ctx: str) -> Variant:
    base, growth, boss = 3 + v % 4, 2 + v % 3, 4 + v % 3
    cap_wave = 5 + v % 4
    cap = base + growth * (cap_wave - 1)
    prompt = (f"For {ctx}, write a ModuleScript Waves with Waves.enemiesForWave(wave: number): number and "
              f"Waves.isBossWave(wave: number): boolean. Wave 1 has {base} enemies and every later wave adds "
              f"{growth}, never more than {cap}. Waves below 1 have 0 enemies. Every {boss}th wave (wave {boss}, "
              f"{2 * boss}, ...) is a boss wave; wave 0 and negative waves are not.")
    ref = _t("""local Waves = {}
function Waves.enemiesForWave(wave: number): number
	if wave < 1 then
		return 0
	end
	return math.min($cap, $base + $growth * (wave - 1))
end
function Waves.isBossWave(wave: number): boolean
	return wave >= 1 and wave % $boss == 0
end
return Waves""", cap=cap, base=base, growth=growth, boss=boss)
    bad = ref.replace(f"{base} + {growth} * (wave - 1)", f"{base} + {growth} * wave")
    test = TEST_HEAD + _t("""local function n(w, want) return safe(function() return M.enemiesForWave(w) == want end) end
check("wave 1 has the base count", n(1, $base))
check("wave 2 adds one step", n(2, $w2))
check("wave 0 and negative waves have no enemies", n(0, 0) and n(-2, 0))
check("the wave that reaches the cap has exactly the cap", n($capwave, $cap))
check("later waves stay at the cap", n($late, $cap))
check("boss waves are the multiples", safe(function() return M.isBossWave($boss) == true and M.isBossWave($boss2) == true end))
check("other waves and wave 0 are not boss waves", safe(function() return M.isBossWave($notboss) == false and M.isBossWave(0) == false end))
""", base=base, w2=base + growth, capwave=cap_wave, cap=cap, late=cap_wave + 7, boss=boss, boss2=2 * boss,
              notboss=boss + 1)
    return Variant(prompt, test, ref, _fence(bad), (_pattern("caps", r"math\s*\.\s*min\s*\(|math\s*\.\s*clamp\s*\(",
                                                             "caps the count"),))


def _wl_levels(v: int, ctx: str) -> Variant:
    base, cap = 50 + 25 * (v % 4), 10 + v
    prompt = (f"For {ctx}, write a ModuleScript Levels with Levels.levelFor(totalXp: number): number and "
              f"Levels.xpToNext(totalXp: number): number. Players start at level 1; going from level L to L+1 costs "
              f"{base} * L XP, so reaching level 2 needs {base} total XP and level 3 needs {3 * base}. Having exactly "
              f"the needed total counts as reaching the level. The maximum level is {cap}. xpToNext returns the XP "
              f"still needed for the next level, and 0 at the maximum level. Negative XP counts as level 1.")
    ref = _t("""local Levels = {}
local function totalFor(level: number): number
	return $base * level * (level - 1) / 2
end
function Levels.levelFor(totalXp: number): number
	local level = 1
	while level < $cap and totalFor(level + 1) <= totalXp do
		level += 1
	end
	return level
end
function Levels.xpToNext(totalXp: number): number
	local level = Levels.levelFor(totalXp)
	if level >= $cap then
		return 0
	end
	return totalFor(level + 1) - math.max(totalXp, 0)
end
return Levels""", base=base, cap=cap)
    bad = ref.replace("totalFor(level + 1) <= totalXp", "totalFor(level + 1) < totalXp")
    test = TEST_HEAD + _t("""local function lv(x, want) return safe(function() return M.levelFor(x) == want end) end
check("no XP is level 1", lv(0, 1))
check("one XP short stays at level 1", lv($b1, 1))
check("exactly the needed total reaches level 2", lv($base, 2))
check("exactly the level 3 total reaches level 3", lv($b3, 3))
check("xpToNext from zero is the first cost", safe(function() return M.xpToNext(0) == $base end))
check("xpToNext right after reaching level 2", safe(function() return M.xpToNext($base) == $base2 end))
check("huge XP stops at the maximum level with nothing to go", lv(10000000, $cap) and safe(function() return M.xpToNext(10000000) == 0 end))
check("negative XP counts as level 1", lv(-40, 1))
""", b1=base - 1, base=base, b3=3 * base, base2=2 * base, cap=cap)
    return Variant(prompt, test, ref, _fence(bad), (_method("levelFor"), _method("xpToNext")))


# =====================================================================================================================
# required feature missing: every listed method, each asserted
# =====================================================================================================================

def _feature_checks(obj: str, module: str, names) -> str:
    return "".join(f'check("required feature: {module}:{n}", safe(function() return type({obj}.{n}) == "function" end))\n'
                   for n in names)


def _drop_method(code: str, module: str, name: str) -> str:
    """The reference without one method definition (the bad answer of a required-feature task)."""
    pattern = re.compile(r"function " + module + r"[:.]" + name + r"\(.*?\nend\n", re.S)
    out, n = pattern.subn("", code, count=1)
    if n != 1:
        raise ValueError(f"cannot drop {module}:{name}")
    return out


_ITEMS = (("Apple", "Bandage", "Rope"), ("Kibble", "Bone", "Treat"), ("Ore", "Gem", "Coal"),
          ("Arrow", "Potion", "Scroll"), ("Seed", "Water", "Fertilizer"))


def _rf_inventory(v: int, ctx: str) -> Variant:
    kinds = 2 + v % 3
    a, b, c = _ITEMS[v % len(_ITEMS)]
    missing = ("remove", "has", "kinds", "clear")[v % 4]
    prompt = (f"For {ctx}, write a ModuleScript Inventory with Inventory.new(maxKinds) and these methods: "
              ":add(item: string, qty: number): boolean, :remove(item: string, qty: number): boolean, "
              ":count(item: string): number, :has(item: string, qty: number): boolean, :kinds(): number and :clear(). "
              f"add refuses (returns false) a qty of 0 or less, and a NEW kind of item when maxKinds different kinds "
              f"are already held (this game uses maxKinds = {kinds}). remove returns false and changes nothing when "
              f"fewer than qty are held; removing the last one frees the kind. Items here are things like {a}, {b} "
              f"and {c}.")
    ref = """local Inventory = {}
Inventory.__index = Inventory
local function countKinds(items): number
	local n = 0
	for _ in items do
		n += 1
	end
	return n
end
function Inventory.new(maxKinds: number)
	return setmetatable({ maxKinds = maxKinds, items = {} }, Inventory)
end
function Inventory:add(item: string, qty: number): boolean
	if qty <= 0 then
		return false
	end
	if self.items[item] == nil and countKinds(self.items) >= self.maxKinds then
		return false
	end
	self.items[item] = (self.items[item] or 0) + qty
	return true
end
function Inventory:remove(item: string, qty: number): boolean
	local have = self.items[item] or 0
	if qty <= 0 or have < qty then
		return false
	end
	if have == qty then
		self.items[item] = nil
	else
		self.items[item] = have - qty
	end
	return true
end
function Inventory:count(item: string): number
	return self.items[item] or 0
end
function Inventory:has(item: string, qty: number): boolean
	return (self.items[item] or 0) >= qty
end
function Inventory:kinds(): number
	return countKinds(self.items)
end
function Inventory:clear()
	table.clear(self.items)
end
return Inventory
"""
    names = ("add", "remove", "count", "has", "kinds", "clear")
    fill = "".join(f'inv:add("X{i}", 1) ' for i in range(kinds - 1))
    test = TEST_HEAD + _t("""local inv = M.new and select(2, pcall(M.new, $kinds)) or {}
""", kinds=kinds) + _feature_checks("inv", "Inventory", names) + _t("""check("add then count", safe(function() return inv:add($a, 3) == true and inv:count($a) == 3 end))
check("has compares with the held amount", safe(function() return inv:has($a, 3) == true and inv:has($a, 4) == false end))
check("removing more than held fails and changes nothing", safe(function() return inv:remove($a, 5) == false and inv:count($a) == 3 end))
check("qty of 0 or less is refused", safe(function() return inv:add($b, 0) == false and inv:add($b, -2) == false end))
pcall(function() $fill end)
check("a new kind beyond maxKinds is refused", safe(function() return inv:kinds() == $kinds and inv:add($c, 1) == false end))
check("removing the last one frees the kind", safe(function() return inv:remove($a, 3) == true and inv:kinds() == $k1 and inv:add($c, 1) == true end))
check("clear empties everything", safe(function() inv:clear() return inv:kinds() == 0 and inv:count($c) == 0 end))
""", a=_q(a), b=_q(b), c=_q(c), kinds=kinds, k1=kinds - 1, fill=fill)
    return Variant(prompt, test, ref.strip("\n"), _fence(_drop_method(ref, "Inventory", missing)),
                   tuple(_method(n) for n in names))


def _rf_party(v: int, ctx: str) -> Variant:
    size = 3 + v % 3
    ids = [100 + 17 * ((v + i * 5) % 11) + i for i in range(size + 1)]
    missing = ("leave", "isFull", "setLeader", "members")[v % 4]
    prompt = (f"For {ctx}, write a ModuleScript Party with Party.new(maxSize) (maxSize {size} here) and methods "
              ":join(userId: number): boolean, :leave(userId: number): boolean, :members(): {number}, "
              ":isFull(): boolean, :leader(): number? and :setLeader(userId: number): boolean. join refuses a full "
              "party or a member who already joined. The first member to join becomes leader. When the leader "
              "leaves, the member with the lowest userId becomes leader (nil when the party is empty). members() "
              "returns a new array sorted from lowest to highest userId. setLeader only accepts current members.")
    ref = """local Party = {}
Party.__index = Party
function Party.new(maxSize: number)
	return setmetatable({ maxSize = maxSize, ids = {}, size = 0, leaderId = 0 }, Party)
end
function Party:join(userId: number): boolean
	if self.ids[userId] or self.size >= self.maxSize then
		return false
	end
	self.ids[userId] = true
	self.size += 1
	if self.leaderId == 0 then
		self.leaderId = userId
	end
	return true
end
function Party:leave(userId: number): boolean
	if not self.ids[userId] then
		return false
	end
	self.ids[userId] = nil
	self.size -= 1
	if self.leaderId == userId then
		local lowest = 0
		for id in self.ids do
			if lowest == 0 or id < lowest then
				lowest = id
			end
		end
		self.leaderId = lowest
	end
	return true
end
function Party:members(): { number }
	local out = {}
	for id in self.ids do
		table.insert(out, id)
	end
	table.sort(out)
	return out
end
function Party:isFull(): boolean
	return self.size >= self.maxSize
end
function Party:leader(): number?
	if self.leaderId == 0 then
		return nil
	end
	return self.leaderId
end
function Party:setLeader(userId: number): boolean
	if not self.ids[userId] then
		return false
	end
	self.leaderId = userId
	return true
end
return Party
"""
    names = ("join", "leave", "members", "isFull", "leader", "setLeader")
    joined = ids[:size]
    rest = sorted(joined[1:])
    test = TEST_HEAD + _t("""local p = M.new and select(2, pcall(M.new, $size)) or {}
local ids = $ids
""", size=size, ids=lua_list(ids)) + _feature_checks("p", "Party", names) + _t("""check("the first member to join is leader", safe(function() return p:join(ids[1]) == true and p:leader() == ids[1] end))
check("joining twice is refused", safe(function() return p:join(ids[1]) == false end))
pcall(function() for i = 2, $size do p:join(ids[i]) end end)
check("a full party refuses new members", safe(function() return p:isFull() == true and p:join(ids[$extra]) == false end))
check("members are sorted from lowest userId", safe(function() return deepEqual(p:members(), $sorted) end))
check("when the leader leaves, the lowest userId leads", safe(function() return p:leave(ids[1]) == true and p:leader() == $lowest and p:isFull() == false end))
check("setLeader accepts members only", safe(function() return p:setLeader(ids[1]) == false and p:setLeader(ids[2]) == true and p:leader() == ids[2] end))
check("an empty party has no leader", safe(function() for _, id in p:members() do p:leave(id) end return p:leader() == nil and #p:members() == 0 end))
""", size=size, extra=size + 1, sorted=lua_list(sorted(joined)), lowest=rest[0])
    return Variant(prompt, test, ref.strip("\n"), _fence(_drop_method(ref, "Party", missing)),
                   tuple(_method(n) for n in names))


_SETTINGS = (
    (("Volume", 0.5), ("Music", True), ("Language", "en"), ("Sensitivity", 3)),
    (("Brightness", 0.8), ("Shadows", False), ("Quality", "high"), ("FieldOfView", 70)),
    (("MasterVolume", 1), ("Subtitles", True), ("Region", "eu"), ("ChatSize", 14)),
    (("CameraShake", 0.3), ("AutoSprint", False), ("Theme", "dark"), ("MouseSpeed", 5)),
    (("SfxVolume", 0.7), ("ShowFps", False), ("Crosshair", "dot"), ("UiScale", 1)),
)


def _rf_settings(v: int, ctx: str) -> Variant:
    rows = _SETTINGS[v % len(_SETTINGS)]
    (k1, v1), (k2, v2), (k3, v3), (k4, v4) = rows
    missing = ("reset", "resetAll", "changed", "get")[v % 4]
    lit = lambda x: lua_list([x])[2:-2]
    defaults = "{ " + ", ".join(f"{k} = {lit(x)}" for k, x in rows) + " }"
    new1 = (not v2) if isinstance(v2, bool) else v2
    other = "zz" if isinstance(v3, str) else v3
    prompt = (f"For {ctx}, write a ModuleScript Settings with Settings.new(defaults) and methods :get(key: string), "
              ":set(key: string, value): boolean, :reset(key: string): boolean, :resetAll() and :changed(): {string}. "
              "set refuses (returns false, no change) an unknown key or a value whose type differs from the default's "
              "type. reset restores one key's default (false for an unknown key). changed() returns the keys whose "
              "value differs from the default, sorted alphabetically. Never modify the defaults table. Example "
              f"defaults: {k1}, {k2}, {k3} and {k4}.")
    ref = """local Settings = {}
Settings.__index = Settings
function Settings.new(defaults)
	local values = {}
	for k, v in defaults do
		values[k] = v
	end
	return setmetatable({ defaults = defaults, values = values }, Settings)
end
function Settings:get(key: string)
	return self.values[key]
end
function Settings:set(key: string, value): boolean
	local default = self.defaults[key]
	if default == nil or type(value) ~= type(default) then
		return false
	end
	self.values[key] = value
	return true
end
function Settings:reset(key: string): boolean
	if self.defaults[key] == nil then
		return false
	end
	self.values[key] = self.defaults[key]
	return true
end
function Settings:resetAll()
	for k, v in self.defaults do
		self.values[k] = v
	end
end
function Settings:changed(): { string }
	local out = {}
	for k, v in self.defaults do
		if self.values[k] ~= v then
			table.insert(out, k)
		end
	end
	table.sort(out)
	return out
end
return Settings
"""
    names = ("get", "set", "reset", "resetAll", "changed")
    bad_type = "1" if not isinstance(v1, (int, float)) or isinstance(v1, bool) else '"loud"'
    test = TEST_HEAD + _t("""local defaults = $defaults
local s = M.new and select(2, pcall(M.new, defaults)) or {}
""", defaults=defaults) + _feature_checks("s", "Settings", names) + _t("""check("get returns the default at first", safe(function() return s:get("$k1") == $v1 and s:get("$k3") == $v3 end))
check("set changes a known key with the same type", safe(function() return s:set("$k4", $v4b) == true and s:get("$k4") == $v4b end))
check("set refuses a different type and unknown keys", safe(function() return s:set("$k1", $badtype) == false and s:set("NoSuchKey", 1) == false and s:get("$k1") == $v1 end))
pcall(function() s:set("$k2", $new1) s:set("$k3", $other) end)
check("changed lists differing keys alphabetically", safe(function() return deepEqual(s:changed(), $changed) end))
check("the defaults table is never modified", defaults.$k4 == $v4 and defaults.$k2 == $v2)
check("reset restores one key and refuses unknown keys", safe(function() return s:reset("$k4") == true and s:get("$k4") == $v4 and s:reset("NoSuchKey") == false end))
check("resetAll restores everything", safe(function() s:resetAll() return #s:changed() == 0 and s:get("$k2") == $v2 end))
""", k1=k1, v1=lit(v1), k2=k2, v2=lit(v2), k3=k3, v3=lit(v3), k4=k4, v4=lit(v4), v4b=lit(v4 + 1),
                         badtype=bad_type, new1=lit(new1), other=_q("zz") if isinstance(v3, str) else lit(other),
                         changed=lua_list(sorted([k2, k3, k4] if isinstance(v3, str) else [k2, k4])))
    return Variant(prompt, test, ref.strip("\n"), _fence(_drop_method(ref, "Settings", missing)),
                   tuple(_method(n) for n in names))


_GOALS = ((("Wood", 10), ("Stone", 5)), (("Coins", 50), ("Gems", 3)), (("Kills", 8), ("Assists", 4)),
          (("Fish", 6), ("Shells", 12)), (("Laps", 3), ("Boosts", 9)))


def _rf_quest(v: int, ctx: str) -> Variant:
    (g1, t1), (g2, t2) = _GOALS[v % len(_GOALS)]
    t1, t2 = t1 + v // 5, t2 + v // 5
    missing = ("remaining", "allComplete", "onComplete", "isComplete")[v % 4]
    prompt = (f"For {ctx}, write a ModuleScript Quest with Quest.new(goals) where goals maps a goal name to its "
              "target (for example { " + f"{g1} = {t1}, {g2} = {t2}" + " }), and methods :progress(name: string, "
              "amount: number): boolean, :remaining(name: string): number, :isComplete(name: string): boolean, "
              ":allComplete(): boolean and :onComplete(callback). progress returns false for an unknown goal or an "
              "amount of 0 or less; progress never goes past the target. Each callback is called with the goal name "
              "exactly once, when that goal first reaches its target.")
    ref = """local Quest = {}
Quest.__index = Quest
function Quest.new(goals)
	local done = {}
	for name in goals do
		done[name] = 0
	end
	return setmetatable({ goals = goals, done = done, listeners = {} }, Quest)
end
function Quest:onComplete(callback)
	table.insert(self.listeners, callback)
end
function Quest:progress(name: string, amount: number): boolean
	local target = self.goals[name]
	if target == nil or amount <= 0 then
		return false
	end
	local before = self.done[name]
	self.done[name] = math.min(target, before + amount)
	if before < target and self.done[name] >= target then
		for _, fn in self.listeners do
			fn(name)
		end
	end
	return true
end
function Quest:remaining(name: string): number
	local target = self.goals[name]
	if target == nil then
		return 0
	end
	return target - self.done[name]
end
function Quest:isComplete(name: string): boolean
	local target = self.goals[name]
	return target ~= nil and self.done[name] >= target
end
function Quest:allComplete(): boolean
	for name, target in self.goals do
		if self.done[name] < target then
			return false
		end
	end
	return true
end
return Quest
"""
    names = ("progress", "remaining", "isComplete", "allComplete", "onComplete")
    test = TEST_HEAD + _t("""local q = M.new and select(2, pcall(M.new, { $g1 = $t1, $g2 = $t2 })) or {}
local fired = {}
""", g1=g1, t1=t1, g2=g2, t2=t2) + _feature_checks("q", "Quest", names) + _t("""pcall(function() q:onComplete(function(name) table.insert(fired, name) end) end)
check("progress counts toward the goal", safe(function() return q:progress("$g1", $p1) == true and q:remaining("$g1") == $r1 end))
check("unknown goals and non-positive amounts are refused", safe(function() return q:progress("Nope", 1) == false and q:progress("$g1", 0) == false end))
check("progress never passes the target", safe(function() return q:progress("$g1", 1000) == true and q:remaining("$g1") == 0 and q:isComplete("$g1") == true end))
check("the callback fired once with the goal name", deepEqual(fired, { "$g1" }))
check("more progress on a finished goal does not fire again", safe(function() q:progress("$g1", 5) return #fired == 1 end))
check("allComplete waits for every goal", safe(function() return q:allComplete() == false and q:isComplete("$g2") == false end))
check("finishing the last goal completes the quest", safe(function() q:progress("$g2", $t2) return q:allComplete() == true and deepEqual(fired, { "$g1", "$g2" }) end))
""", g1=g1, p1=max(1, t1 // 2), r1=t1 - max(1, t1 // 2), g2=g2, t2=t2)
    return Variant(prompt, test, ref.strip("\n"), _fence(_drop_method(ref, "Quest", missing)),
                   tuple(_method(n) for n in names))


def _rf_timer(v: int, ctx: str) -> Variant:
    d = 60 + 15 * v
    missing = ("pause", "resume", "addTime", "isFinished")[v % 4]
    prompt = (f"For {ctx}, write a ModuleScript RoundTimer with RoundTimer.new(duration) (a {d} second round here) "
              "and methods :start(now: number), :pause(now: number), :resume(now: number), :remaining(now: number): "
              "number, :isFinished(now: number): boolean and :addTime(seconds: number). Before start, remaining is "
              "the full duration. Time only runs while started and not paused. addTime changes the time left by "
              "`seconds` (it can be negative). remaining never reports less than 0, and isFinished is true when "
              "remaining is 0.")
    ref = """local RoundTimer = {}
RoundTimer.__index = RoundTimer
function RoundTimer.new(duration: number)
	return setmetatable({ left = duration, since = -1 }, RoundTimer)
end
function RoundTimer:start(now: number)
	if self.since < 0 then
		self.since = now
	end
end
function RoundTimer:remaining(now: number): number
	local left = self.left
	if self.since >= 0 then
		left -= now - self.since
	end
	return math.max(0, left)
end
function RoundTimer:pause(now: number)
	if self.since >= 0 then
		self.left -= now - self.since
		self.since = -1
	end
end
function RoundTimer:resume(now: number)
	self:start(now)
end
function RoundTimer:isFinished(now: number): boolean
	return self:remaining(now) <= 0
end
function RoundTimer:addTime(seconds: number)
	self.left += seconds
end
return RoundTimer
"""
    names = ("start", "pause", "resume", "remaining", "isFinished", "addTime")
    test = TEST_HEAD + _t("""local t = M.new and select(2, pcall(M.new, $d)) or {}
""", d=d) + _feature_checks("t", "RoundTimer", names) + _t("""check("before start the full duration remains", safe(function() return t:remaining(500) == $d end))
check("time runs after start", safe(function() t:start(100) return t:remaining(110) == $d10 end))
check("paused time does not run", safe(function() t:pause(110) return t:remaining(150) == $d10 end))
check("resume continues from the paused value", safe(function() t:resume(160) return t:remaining(165) == $d15 end))
check("addTime extends the time left", safe(function() t:addTime(5) return t:remaining(165) == $d10 end))
check("remaining never goes below 0 and the round finishes", safe(function() return t:remaining(100000) == 0 and t:isFinished(100000) == true end))
check("an unfinished round is not finished", safe(function() return t:isFinished(166) == false end))
""", d=d, d10=d - 10, d15=d - 15)
    return Variant(prompt, test, ref.strip("\n"), _fence(_drop_method(ref, "RoundTimer", missing)),
                   tuple(_method(n) for n in names))


_SHOPS = ((("Sword", 120), ("Shield", 80), ("Potion", 25), ("Map", 25)),
          (("Hat", 40), ("Cape", 90), ("Boots", 60), ("Gloves", 60)),
          (("Rod", 75), ("Bait", 10), ("Net", 150), ("Hook", 10)),
          (("Wheel", 200), ("Paint", 45), ("Horn", 30), ("Flag", 45)),
          (("Seeds", 15), ("Hoe", 55), ("Can", 35), ("Fence", 15)))


def _rf_shop(v: int, ctx: str) -> Variant:
    items = _SHOPS[v % len(_SHOPS)]
    missing = ("canAfford", "setDiscount", "listAffordable", "buy")[v % 4]
    prices = dict(items)
    coins = sorted(prices.values())[2]
    disc = 20 + 10 * (v % 3)

    def p(name, d=0):
        return (prices[name] * (100 - d)) // 100
    affordable = sorted([n for n in prices if p(n) <= coins], key=lambda n: (p(n), n))
    cheapest = affordable[0]
    priciest = max(prices, key=lambda n: (prices[n], n))
    prompt = (f"For {ctx}, write a ModuleScript Shop with Shop.new(prices) (a map from item name to price, for "
              f"example {items[0][0]} = {items[0][1]}) and methods :price(name: string): number?, :canAfford(name: "
              "string, coins: number): boolean, :buy(name: string, coins: number): (boolean, number), "
              ":setDiscount(percent: number) and :listAffordable(coins: number): {string}. The discounted price is "
              "math.floor(price * (100 - discount) / 100); setDiscount clamps the percent to 0..90. buy returns "
              "true and the coins left, or false and the unchanged coins (unknown item or not enough coins). "
              "listAffordable returns the item names whose current price is at most coins, cheapest first, equal "
              "prices by name.")
    ref = """local Shop = {}
Shop.__index = Shop
function Shop.new(prices)
	return setmetatable({ prices = prices, discount = 0 }, Shop)
end
function Shop:price(name: string): number?
	local base = self.prices[name]
	if base == nil then
		return nil
	end
	return math.floor(base * (100 - self.discount) / 100)
end
function Shop:canAfford(name: string, coins: number): boolean
	local cost = self:price(name)
	return cost ~= nil and coins >= cost
end
function Shop:buy(name: string, coins: number): (boolean, number)
	local cost = self:price(name)
	if cost == nil or coins < cost then
		return false, coins
	end
	return true, coins - cost
end
function Shop:setDiscount(percent: number)
	self.discount = math.clamp(percent, 0, 90)
end
function Shop:listAffordable(coins: number): { string }
	local out = {}
	for name in self.prices do
		local cost = self:price(name)
		if cost ~= nil and cost <= coins then
			table.insert(out, name)
		end
	end
	table.sort(out, function(a, b)
		local pa, pb = self:price(a) :: number, self:price(b) :: number
		if pa ~= pb then
			return pa < pb
		end
		return a < b
	end)
	return out
end
return Shop
"""
    names = ("price", "canAfford", "buy", "setDiscount", "listAffordable")
    lit = "{ " + ", ".join(f"{n} = {c}" for n, c in items) + " }"
    test = TEST_HEAD + _t("""local s = M.new and select(2, pcall(M.new, $lit)) or {}
""", lit=lit) + _feature_checks("s", "Shop", names) + _t("""check("price of a known and an unknown item", safe(function() return s:price("$priciest") == $pp and s:price("Nothing") == nil end))
check("canAfford compares coins with the price", safe(function() return s:canAfford("$cheapest", $coins) == true and s:canAfford("$priciest", $pp1) == false end))
check("buy returns true and the coins left", safe(function() local ok, left = s:buy("$cheapest", $coins) return ok == true and left == $left end))
check("a failed buy keeps the coins", safe(function() local ok, left = s:buy("$priciest", 1) return ok == false and left == 1 end))
check("listAffordable is cheapest first, ties by name", safe(function() return deepEqual(s:listAffordable($coins), $aff) end))
check("a discount lowers prices with math.floor", safe(function() s:setDiscount($disc) return s:price("$priciest") == $ppd end))
check("the discount is clamped to 0..90", safe(function() s:setDiscount(150) local high = s:price("$priciest") s:setDiscount(-5) return high == $pp90 and s:price("$priciest") == $pp end))
""", priciest=priciest, pp=prices[priciest], cheapest=cheapest, coins=coins, pp1=prices[priciest] - 1,
                         left=coins - p(cheapest), aff=lua_list(affordable), disc=disc, ppd=p(priciest, disc),
                         pp90=p(priciest, 90))
    return Variant(prompt, test, ref.strip("\n"), _fence(_drop_method(ref, "Shop", missing)),
                   tuple(_method(n) for n in names))


# =====================================================================================================================
# self-check error left unrepaired: strict typing, real checker errors in the bad answer
# =====================================================================================================================

def _sc_vec(v: int, ctx: str) -> Variant:
    k = v + 1
    prompt = (f"For {ctx}, write a --!strict ModuleScript Vec2 with `export type Vec = {{ x: number, y: number }}` and "
              "typed functions Vec2.new(x: number, y: number): Vec, Vec2.add(a: Vec, b: Vec): Vec, "
              "Vec2.scale(v: Vec, k: number): Vec, Vec2.length(v: Vec): number and Vec2.normalize(v: Vec): Vec. "
              "normalize returns a vector of length 1 in the same direction, and the zero vector { x = 0, y = 0 } "
              f"for a zero-length input (never nil). Vectors are plain tables, not Vector2 (for example a scale of {k}).")
    ref = """--!strict
export type Vec = { x: number, y: number }
local Vec2 = {}
function Vec2.new(x: number, y: number): Vec
	return { x = x, y = y }
end
function Vec2.add(a: Vec, b: Vec): Vec
	return { x = a.x + b.x, y = a.y + b.y }
end
function Vec2.scale(v: Vec, k: number): Vec
	return { x = v.x * k, y = v.y * k }
end
function Vec2.length(v: Vec): number
	return math.sqrt(v.x * v.x + v.y * v.y)
end
function Vec2.normalize(v: Vec): Vec
	local len = Vec2.length(v)
	if len == 0 then
		return { x = 0, y = 0 }
	end
	return { x = v.x / len, y = v.y / len }
end
return Vec2"""
    bad = ref.replace("		return { x = 0, y = 0 }\n", "		return nil\n")
    test = TEST_HEAD + _t("""check("new and add", safe(function() local a = M.add(M.new(1, 2), M.new($k, 4)) return a.x == $k1 and a.y == 6 end))
check("scale", safe(function() local s = M.scale(M.new(3, -2), $k) return s.x == $k3 and s.y == $km2 end))
check("length of a 3-4-5 vector", safe(function() return M.length(M.new($k3, $k4)) == $k5 end))
check("normalize has length 1 and keeps direction", safe(function() local n = M.normalize(M.new(0, $k5)) return n.x == 0 and n.y == 1 end))
check("normalize of the zero vector is the zero vector", safe(function() local n = M.normalize(M.new(0, 0)) return type(n) == "table" and n.x == 0 and n.y == 0 end))
""", k=k, k1=1 + k, k3=3 * k, km2=-2 * k, k4=4 * k, k5=5 * k)
    return Variant(prompt, test, ref, _fence(bad), (_raw("strict", r"^\s*--!strict", "starts with --!strict"),),
                   strict=True, static_error=r"could not be converted|not compatible|nil")


def _sc_lookup(v: int, ctx: str) -> Variant:
    missing = (0, -1)[v % 2]
    names = ("Rook", "Pip", "Mara", "Tess", "Odin", "Wren", "Bo", "Lyra", "Sol", "Ken")
    a, b, c = names[v % 10], names[(v + 3) % 10], names[(v + 6) % 10]
    prompt = (f"For {ctx}, write a --!strict ModuleScript Scores with `export type Entry = {{ name: string, score: "
              "number }`, Scores.find(list: {Entry}, name: string): Entry?, Scores.scoreOf(list: {Entry}, name: string): "
              f"number (returns {missing} when the name is not in the list) and Scores.best(list: {{Entry}}): Entry? "
              "(the highest score, nil for an empty list). Narrow every optional value before using it.")
    ref = _t("""--!strict
export type Entry = { name: string, score: number }
local Scores = {}
function Scores.find(list: { Entry }, name: string): Entry?
	for _, e in list do
		if e.name == name then
			return e
		end
	end
	return nil
end
function Scores.scoreOf(list: { Entry }, name: string): number
	local e = Scores.find(list, name)
	if e == nil then
		return $missing
	end
	return e.score
end
function Scores.best(list: { Entry }): Entry?
	local top: Entry? = nil
	for _, e in list do
		if top == nil or e.score > top.score then
			top = e
		end
	end
	return top
end
return Scores""", missing=missing)
    bad = re.sub(r"(function Scores\.scoreOf.*?\n)(.*?)(\nend)", lambda m: m.group(1)
                 + "\treturn Scores.find(list, name).score" + m.group(3), ref, count=1, flags=re.S)
    test = TEST_HEAD + _t("""local list = { { name = "$a", score = 12 }, { name = "$b", score = 30 }, { name = "$c", score = 7 } }
check("find returns the entry", safe(function() local e = M.find(list, "$b") return e ~= nil and e.score == 30 end))
check("find returns nil for a missing name", safe(function() return M.find(list, "Nobody") == nil end))
check("scoreOf a present name", safe(function() return M.scoreOf(list, "$c") == 7 end))
check("scoreOf a missing name returns the fallback", safe(function() return M.scoreOf(list, "Nobody") == $missing end))
check("best is the highest score and nil for an empty list", safe(function() local e = M.best(list) return e ~= nil and e.name == "$b" and M.best({}) == nil end))
""", a=a, b=b, c=c, missing=missing)
    return Variant(prompt, test, ref, _fence(bad), (_raw("strict", r"^\s*--!strict", "starts with --!strict"),),
                   strict=True, static_error=r"could be nil|nil")


def _sc_queue(v: int, ctx: str) -> Variant:
    people = ["P%d" % (v * 3 + i) for i in range(4)]
    prompt = (f"For {ctx}, write a --!strict ModuleScript Queue for player names with `export type Queue = {{ items: "
              "{ [number]: string? }, head: number, tail: number }` and typed functions Queue.new(): Queue, "
              "Queue.push(q: Queue, name: string), Queue.pop(q: Queue): string? (oldest first, nil when empty) and "
              f"Queue.size(q: Queue): number. Pop must not shift the whole array (the line can hold {40 + v} players).")
    ref = """--!strict
export type Queue = { items: { [number]: string? }, head: number, tail: number }
local Queue = {}
function Queue.new(): Queue
	return { items = {}, head = 1, tail = 0 }
end
function Queue.push(q: Queue, name: string)
	q.tail += 1
	q.items[q.tail] = name
end
function Queue.pop(q: Queue): string?
	if q.head > q.tail then
		return nil
	end
	local name = q.items[q.head]
	q.items[q.head] = nil
	q.head += 1
	return name
end
function Queue.size(q: Queue): number
	return q.tail - q.head + 1
end
return Queue"""
    bad = ref.replace("	return q.tail - q.head + 1", "	return tostring(q.tail - q.head + 1)")
    test = TEST_HEAD + _t("""local q = M.new and select(2, pcall(M.new)) or {}
pcall(function() for _, n in $people do M.push(q, n) end end)
check("size counts pushed names", safe(function() return M.size(q) == 4 end))
check("pop returns the oldest first", safe(function() return M.pop(q) == "$p1" and M.pop(q) == "$p2" end))
check("size drops after pops", safe(function() return M.size(q) == 2 end))
check("pop on an empty queue returns nil", safe(function() M.pop(q) M.pop(q) return M.pop(q) == nil and M.size(q) == 0 end))
check("the queue works again after emptying", safe(function() M.push(q, "late") return M.size(q) == 1 and M.pop(q) == "late" end))
""", people=lua_list(people), p1=people[0], p2=people[1])
    return Variant(prompt, test, ref, _fence(bad), (_raw("strict", r"^\s*--!strict", "starts with --!strict"),),
                   strict=True, static_error=r"could not be converted|string|number")


def _sc_armor(v: int, ctx: str) -> Variant:
    floor_dmg = 1 + v % 3
    prompt = (f"For {ctx}, write a --!strict ModuleScript Damage with a local helper applyArmor(amount: number, armor: "
              f"number): number that subtracts armor but never returns less than {floor_dmg}, and typed functions "
              "Damage.hit(health: number, amount: number, armor: number): number (the new health, never below 0) and "
              "Damage.isDead(health: number): boolean.")
    ref = _t("""--!strict
local Damage = {}
local function applyArmor(amount: number, armor: number): number
	return math.max($floor, amount - armor)
end
function Damage.hit(health: number, amount: number, armor: number): number
	return math.max(0, health - applyArmor(amount, armor))
end
function Damage.isDead(health: number): boolean
	return health <= 0
end
return Damage""", floor=floor_dmg)
    bad = ref.replace("applyArmor(amount, armor))", "applyArmor(amount))")
    hp, amount, armor = 100 + 10 * v, 30 + 2 * v, 10 + v
    test = TEST_HEAD + _t("""check("armor reduces damage", safe(function() return M.hit($hp, $amount, $armor) == $after end))
check("heavy armor still deals the minimum", safe(function() return M.hit($hp, 5, $heavy) == $minleft end))
check("health never goes below 0", safe(function() return M.hit(10, 500, 0) == 0 end))
check("isDead at 0 and below", safe(function() return M.isDead(0) == true and M.isDead(-3) == true and M.isDead(1) == false end))
""", hp=hp, amount=amount, armor=armor, after=hp - (amount - armor), heavy=50 + v, minleft=hp - floor_dmg)
    return Variant(prompt, test, ref, _fence(bad), (_raw("strict", r"^\s*--!strict", "starts with --!strict"),
                                                    _pattern("helper", r"local\s+function\s+applyArmor\s*\(", "helper")),
                   strict=True, static_error=r"[Aa]rgument count|expects")


def _sc_stats(v: int, ctx: str) -> Variant:
    vals = [3 + v, 9 + v, 6 + v, 2 + v]
    prompt = (f"For {ctx}, write a --!strict ModuleScript Stats with `export type Summary = {{ min: number, max: number, "
              "mean: number }` and Stats.summarize(values: {number}): Summary. An empty list summarises to "
              "{ min = 0, max = 0, mean = 0 }: every field is always present.")
    ref = """--!strict
export type Summary = { min: number, max: number, mean: number }
local Stats = {}
function Stats.summarize(values: { number }): Summary
	if #values == 0 then
		return { min = 0, max = 0, mean = 0 }
	end
	local lo, hi, total = math.huge, -math.huge, 0
	for _, x in values do
		lo = math.min(lo, x)
		hi = math.max(hi, x)
		total += x
	end
	return { min = lo, max = hi, mean = total / #values }
end
return Stats"""
    bad = ref.replace("return { min = 0, max = 0, mean = 0 }", "return { min = 0, max = 0 }")
    mean = sum(vals) / len(vals)
    test = TEST_HEAD + _t("""check("min and max", safe(function() local s = M.summarize($vals) return s.min == $lo and s.max == $hi end))
check("mean", safe(function() return M.summarize($vals).mean == $mean end))
check("a single value", safe(function() local s = M.summarize({ 5 }) return s.min == 5 and s.max == 5 and s.mean == 5 end))
check("an empty list has every field at 0", safe(function() local s = M.summarize({}) return s.min == 0 and s.max == 0 and s.mean == 0 end))
""", vals=lua_list(vals), lo=min(vals), hi=max(vals), mean=_num(mean))
    return Variant(prompt, test, ref, _fence(bad), (_raw("strict", r"^\s*--!strict", "starts with --!strict"),),
                   strict=True, static_error=r"mean|not compatible|could not be converted|missing")


_ELEMENTS = (("Fire", "Water", "Grass"), ("Rock", "Paper", "Scissors"), ("Light", "Shadow", "Storm"),
             ("Frost", "Flame", "Wind"), ("Iron", "Acid", "Bolt"))


def _sc_elements(v: int, ctx: str) -> Variant:
    a, b, c = _ELEMENTS[v % len(_ELEMENTS)]
    strong, weak = (2, 1.5, 3)[v % 3], (0.5, 0.25)[v % 2]
    prompt = (f"For {ctx}, write a --!strict ModuleScript Elements with `type Element = \"{a}\" | \"{b}\" | \"{c}\"` and "
              "Elements.multiplier(attacker: Element, defender: Element): number. The same element gives 1. "
              f"{a} beats {c}, {b} beats {a} and {c} beats {b}: a winning attacker gives {_num(strong)}, a losing "
              f"attacker gives {_num(weak)}. Use an if / elseif / else chain.")
    ref = _t("""--!strict
type Element = "$a" | "$b" | "$c"
local Elements = {}
function Elements.multiplier(attacker: Element, defender: Element): number
	if attacker == defender then
		return 1
	elseif (attacker == "$a" and defender == "$c") or (attacker == "$b" and defender == "$a") or (attacker == "$c" and defender == "$b") then
		return $strong
	else
		return $weak
	end
end
return Elements""", a=a, b=b, c=c, strong=_num(strong), weak=_num(weak))
    lines = ref.split("\n")
    idx = max(i for i, line in enumerate(lines) if line == "\tend")
    bad = "\n".join(lines[:idx] + lines[idx + 1:])          # the if-chain loses its `end`: a parse error
    test = TEST_HEAD + _t("""check("same element gives 1", safe(function() return M.multiplier("$a", "$a") == 1 end))
check("winning attackers", safe(function() return M.multiplier("$a", "$c") == $strong and M.multiplier("$b", "$a") == $strong and M.multiplier("$c", "$b") == $strong end))
check("losing attackers", safe(function() return M.multiplier("$c", "$a") == $weak and M.multiplier("$a", "$b") == $weak end))
""", a=a, b=b, c=c, strong=_num(strong), weak=_num(weak))
    return Variant(prompt, test, ref, _fence(bad), (_raw("strict", r"^\s*--!strict", "starts with --!strict"),),
                   strict=True, static_error=r"[Ee]xpected|end")


# =====================================================================================================================
# answer cut off: long modules that must be finished
# =====================================================================================================================

def _truncate(code: str, share: float = 0.55) -> str:
    """A bad answer that stops mid-module: the first `share` of the lines, inside an unclosed fence."""
    lines = code.strip("\n").split("\n")
    keep = max(3, int(len(lines) * share))
    return "Here is the full module:\n\n" + FENCE + "luau\n" + "\n".join(lines[:keep]) + "\n"


def _co_text(v: int, ctx: str) -> Variant:
    sep = (",", ".", " ", "'", "_")[v % 5]
    suffix = ("...", "~", "..")[v % 3]
    pad = ("0", "*", "-")[v % 3]
    prompt = (f"For {ctx}, write a ModuleScript TextFormat with ALL of these functions: formatTime(seconds) -> \"m:ss\" "
              "(seconds rounded down; 75 -> \"1:15\", 5 -> \"0:05\"); formatThousands(n) groups an integer's digits "
              f"by three with \"{sep}\" (negative numbers keep the minus sign); abbreviate(n) -> \"999\", \"1.2K\", "
              "\"3.4M\", \"5.6B\" (one decimal rounded down, no \".0\": 1000 -> \"1K\"); pluralize(count, word) -> "
              "\"1 coin\" / \"2 coins\"; padLeft(s, width) pads on the left with \"" + pad + "\"; titleCase(s) "
              "capitalises the first letter of every space-separated word; truncate(s, maxLen) returns s unchanged "
              f"when it fits, otherwise a string of exactly maxLen characters ending in \"{suffix}\"; percent(part, "
              "whole) -> \"50%\" rounded to the nearest integer, \"0%\" when whole is 0.")
    ref = _t("""local TextFormat = {}
function TextFormat.formatTime(seconds: number): string
	local s = math.floor(seconds)
	return string.format("%d:%02d", s // 60, s % 60)
end
function TextFormat.formatThousands(n: number): string
	local sign = n < 0 and "-" or ""
	local digits = tostring(math.abs(math.floor(n)))
	local out = ""
	while #digits > 3 do
		out = "$sep" .. string.sub(digits, -3) .. out
		digits = string.sub(digits, 1, -4)
	end
	return sign .. digits .. out
end
function TextFormat.abbreviate(n: number): string
	local units = { { 1000000000, "B" }, { 1000000, "M" }, { 1000, "K" } }
	for _, u in units do
		if n >= u[1] then
			local tenths = math.floor(n * 10 / u[1])
			if tenths % 10 == 0 then
				return string.format("%d%s", tenths // 10, u[2])
			end
			return string.format("%d.%d%s", tenths // 10, tenths % 10, u[2])
		end
	end
	return tostring(math.floor(n))
end
function TextFormat.pluralize(count: number, word: string): string
	return tostring(count) .. " " .. word .. (count == 1 and "" or "s")
end
function TextFormat.padLeft(s: string, width: number): string
	return string.rep("$pad", width - #s) .. s
end
function TextFormat.titleCase(s: string): string
	return (string.gsub(s, "(%a)([%w]*)", function(first, rest)
		return string.upper(first) .. rest
	end))
end
function TextFormat.truncate(s: string, maxLen: number): string
	if #s <= maxLen then
		return s
	end
	return string.sub(s, 1, maxLen - $sl) .. "$suffix"
end
function TextFormat.percent(part: number, whole: number): string
	if whole == 0 then
		return "0%"
	end
	return tostring(math.floor(part / whole * 100 + 0.5)) .. "%"
end
return TextFormat""", sep=sep, pad=pad, suffix=suffix, sl=len(suffix))
    big = 1234567 + 1000 * v
    grouped = f"{big:,}".replace(",", sep)
    test = TEST_HEAD + _t("""local function eq(f, want) return safe(function() return f() == want end) end
check("formatTime", eq(function() return M.formatTime(75.9) end, "1:15") and eq(function() return M.formatTime(5) end, "0:05"))
check("formatThousands", eq(function() return M.formatThousands($big) end, "$grouped") and eq(function() return M.formatThousands(-1234) end, "-1${sep}234") and eq(function() return M.formatThousands(999) end, "999"))
check("abbreviate", eq(function() return M.abbreviate(999) end, "999") and eq(function() return M.abbreviate(1250) end, "1.2K") and eq(function() return M.abbreviate(1000) end, "1K") and eq(function() return M.abbreviate(2300000) end, "2.3M"))
check("pluralize", eq(function() return M.pluralize(1, "coin") end, "1 coin") and eq(function() return M.pluralize(3, "coin") end, "3 coins"))
check("padLeft", eq(function() return M.padLeft("7", 3) end, "${pad}${pad}7") and eq(function() return M.padLeft("1234", 3) end, "1234"))
check("titleCase", eq(function() return M.titleCase("hello brave world") end, "Hello Brave World"))
check("truncate", eq(function() return M.truncate("short", 10) end, "short") and eq(function() return #M.truncate("a very long title here", 10) end, 10) and safe(function() return string.sub(M.truncate("a very long title here", 10), -$sl) == "$suffix" end))
check("percent", eq(function() return M.percent(1, 2) end, "50%") and eq(function() return M.percent(2, 3) end, "67%") and eq(function() return M.percent(5, 0) end, "0%"))
""", big=big, grouped=grouped, sep=sep, pad=pad, sl=len(suffix), suffix=suffix)
    return Variant(prompt, test, ref, _truncate(ref), (_pattern("returns", r"return\s+TextFormat\s*$", "module return"),))


def _co_grid(v: int, ctx: str) -> Variant:
    w, h = 4 + v % 5, 3 + v % 4
    prompt = (f"For {ctx}, write a ModuleScript Grid for a {w} by {h} tile board (width {w}, height {h}, tiles numbered "
              "1..width*height row by row) with ALL of these functions: Grid.toIndex(x, y) (1-based column and row), "
              "Grid.fromIndex(i) -> x, y, Grid.inBounds(x, y): boolean, Grid.neighbors(i) -> the indices of the "
              "up, right, down and left tiles that exist, in that order, Grid.manhattan(i, j): number, Grid.row(i) "
              "-> the indices of i's row left to right, Grid.corners() -> { top-left, top-right, bottom-left, "
              "bottom-right } and Grid.count(): number.")
    ref = _t("""local Grid = {}
local W, H = $w, $h
function Grid.toIndex(x: number, y: number): number
	return (y - 1) * W + x
end
function Grid.fromIndex(i: number): (number, number)
	return (i - 1) % W + 1, (i - 1) // W + 1
end
function Grid.inBounds(x: number, y: number): boolean
	return x >= 1 and x <= W and y >= 1 and y <= H
end
function Grid.neighbors(i: number): { number }
	local x, y = Grid.fromIndex(i)
	local out = {}
	for _, d in { { 0, -1 }, { 1, 0 }, { 0, 1 }, { -1, 0 } } do
		local nx, ny = x + d[1], y + d[2]
		if Grid.inBounds(nx, ny) then
			table.insert(out, Grid.toIndex(nx, ny))
		end
	end
	return out
end
function Grid.manhattan(i: number, j: number): number
	local x1, y1 = Grid.fromIndex(i)
	local x2, y2 = Grid.fromIndex(j)
	return math.abs(x1 - x2) + math.abs(y1 - y2)
end
function Grid.row(i: number): { number }
	local _, y = Grid.fromIndex(i)
	local out = {}
	for x = 1, W do
		table.insert(out, Grid.toIndex(x, y))
	end
	return out
end
function Grid.corners(): { number }
	return { 1, W, (H - 1) * W + 1, W * H }
end
function Grid.count(): number
	return W * H
end
return Grid""", w=w, h=h)
    mid = w + 2                                             # (2, 2)
    test = TEST_HEAD + _t("""check("toIndex", safe(function() return M.toIndex(1, 1) == 1 and M.toIndex($w, 1) == $w and M.toIndex(2, 2) == $mid end))
check("fromIndex", safe(function() local x, y = M.fromIndex($mid) return x == 2 and y == 2 end))
check("inBounds", safe(function() return M.inBounds(1, 1) and M.inBounds($w, $h) and not M.inBounds(0, 1) and not M.inBounds(1, $h1) end))
check("neighbors of a corner", safe(function() return deepEqual(M.neighbors(1), { 2, $w1 }) end))
check("neighbors of an inner tile in order up, right, down, left", safe(function() return deepEqual(M.neighbors($mid), { 2, $mid1, $midd, $midl }) end))
check("manhattan", safe(function() return M.manhattan(1, $last) == $dist end))
check("row", safe(function() return deepEqual(M.row($mid), $row2) end))
check("corners and count", safe(function() return deepEqual(M.corners(), { 1, $w, $bl, $last }) and M.count() == $last end))
""", w=w, h=h, mid=mid, h1=h + 1, w1=w + 1, mid1=mid + 1, midd=mid + w, midl=mid - 1, last=w * h,
                         dist=(w - 1) + (h - 1), row2=lua_list(list(range(w + 1, 2 * w + 1))), bl=(h - 1) * w + 1)
    return Variant(prompt, test, ref, _truncate(ref), (_pattern("returns", r"return\s+Grid\s*$", "module return"),))


def _co_ledger(v: int, ctx: str) -> Variant:
    start = 100 + 50 * (v % 4)
    users = (("ana", "bo", "cy"), ("dee", "eli", "fox"), ("gil", "hal", "ivy"), ("jo", "kat", "lee"),
             ("max", "neo", "oli"))[v % 5]
    a, b, c = users
    prompt = (f"For {ctx}, write a ModuleScript Bank with Bank.new() and ALL of these methods: :deposit(user, amount): "
              "boolean, :withdraw(user, amount): boolean, :transfer(from, to, amount): boolean, :balance(user): number, "
              ":history(user) -> a new array of { kind = \"deposit\" | \"withdraw\" | \"transfer_in\" | \"transfer_out\", "
              "amount }, :total(): number (all balances), :richest(n) -> up to n user names by balance high to low, "
              "equal balances by name, and :undoLast(): boolean that reverts the last successful operation (false when "
              "there is nothing to undo). Amounts must be positive; a withdraw or transfer larger than the balance "
              f"fails and changes nothing (starting deposits are around {start} coins).")
    ref = """local Bank = {}
Bank.__index = Bank
function Bank.new()
	return setmetatable({ balances = {}, logs = {}, undo = {} }, Bank)
end
local function log(self, user: string, kind: string, amount: number)
	self.logs[user] = self.logs[user] or {}
	table.insert(self.logs[user], { kind = kind, amount = amount })
end
local function unlog(self, user: string)
	table.remove(self.logs[user])
end
function Bank:balance(user: string): number
	return self.balances[user] or 0
end
function Bank:deposit(user: string, amount: number): boolean
	if amount <= 0 then
		return false
	end
	self.balances[user] = self:balance(user) + amount
	log(self, user, "deposit", amount)
	table.insert(self.undo, function()
		self.balances[user] -= amount
		unlog(self, user)
	end)
	return true
end
function Bank:withdraw(user: string, amount: number): boolean
	if amount <= 0 or self:balance(user) < amount then
		return false
	end
	self.balances[user] -= amount
	log(self, user, "withdraw", amount)
	table.insert(self.undo, function()
		self.balances[user] += amount
		unlog(self, user)
	end)
	return true
end
function Bank:transfer(from: string, to: string, amount: number): boolean
	if amount <= 0 or from == to or self:balance(from) < amount then
		return false
	end
	self.balances[from] -= amount
	self.balances[to] = self:balance(to) + amount
	log(self, from, "transfer_out", amount)
	log(self, to, "transfer_in", amount)
	table.insert(self.undo, function()
		self.balances[from] += amount
		self.balances[to] -= amount
		unlog(self, from)
		unlog(self, to)
	end)
	return true
end
function Bank:history(user: string)
	return table.clone(self.logs[user] or {})
end
function Bank:total(): number
	local sum = 0
	for _, amount in self.balances do
		sum += amount
	end
	return sum
end
function Bank:richest(n: number): { string }
	local names = {}
	for name in self.balances do
		table.insert(names, name)
	end
	table.sort(names, function(x, y)
		if self.balances[x] ~= self.balances[y] then
			return self.balances[x] > self.balances[y]
		end
		return x < y
	end)
	local out = {}
	for i = 1, math.min(n, #names) do
		out[i] = names[i]
	end
	return out
end
function Bank:undoLast(): boolean
	local fn = table.remove(self.undo)
	if fn == nil then
		return false
	end
	fn()
	return true
end
return Bank"""
    t = 30 + 5 * (v % 3)
    test = TEST_HEAD + _t("""local bank = M.new and select(2, pcall(M.new)) or {}
check("deposit and balance", safe(function() return bank:deposit("$a", $start) == true and bank:balance("$a") == $start and bank:balance("$c") == 0 end))
check("non-positive amounts are refused", safe(function() return bank:deposit("$a", 0) == false and bank:withdraw("$a", -5) == false end))
check("withdraw more than the balance fails", safe(function() return bank:withdraw("$a", $over) == false and bank:balance("$a") == $start end))
check("transfer moves coins", safe(function() return bank:transfer("$a", "$b", $t) == true and bank:balance("$a") == $left and bank:balance("$b") == $t end))
check("history records the operations in order", safe(function() local h = bank:history("$a") return #h == 2 and h[1].kind == "deposit" and h[2].kind == "transfer_out" and h[2].amount == $t end))
check("total sums all balances", safe(function() return bank:total() == $start end))
check("richest orders by balance then name", safe(function() bank:deposit("$c", $t) return deepEqual(bank:richest(2), { "$a", "$firsttie" }) end))
check("undoLast reverts the last operation and stops when empty", safe(function()
	local ok = bank:undoLast() and bank:balance("$c") == 0 and bank:undoLast() and bank:balance("$a") == $start and bank:balance("$b") == 0
	bank:undoLast()
	return ok and bank:undoLast() == false
end))
""", a=a, b=b, c=c, start=start, over=start + 1, t=t, left=start - t, firsttie=min(b, c))
    return Variant(prompt, test, ref, _truncate(ref), (_pattern("returns", r"return\s+Bank\s*$", "module return"),))


def _co_match(v: int, ctx: str) -> Variant:
    team = 2 + v % 2
    n = 2 * team
    ratings = [1000 + ((v * 37 + i * 61) % 9) * 50 + i for i in range(n + 1)]
    order = sorted(range(n), key=lambda i: -ratings[i])       # the first n waiting players, by rating
    a_team, b_team = [], []
    for pos, i in enumerate(order):
        (a_team if pos % 4 in (0, 3) else b_team).append(i + 1)
    prompt = (f"For {ctx}, write a ModuleScript Matchmaker with Matchmaker.new(teamSize) ({team} players per team here) "
              "and ALL of these methods: :enqueue(playerId, rating): boolean (false if already queued), "
              ":dequeue(playerId): boolean, :size(): number, :contains(playerId): boolean, :position(playerId): "
              "number? (1 = waited longest), :averageRating(): number (0 when empty) and :nextMatch() which, when at "
              "least 2*teamSize players wait, removes the 2*teamSize who waited longest, sorts them by rating high to "
              "low and snake-drafts them (team a gets 1st, b gets 2nd and 3rd, a gets 4th and 5th, ...), returning "
              "{ a = {playerIds}, b = {playerIds} } with ids in draft order, or nil when not enough players wait.")
    ref = """local Matchmaker = {}
Matchmaker.__index = Matchmaker
function Matchmaker.new(teamSize: number)
	return setmetatable({ teamSize = teamSize, line = {}, ratings = {} }, Matchmaker)
end
function Matchmaker:contains(playerId: number): boolean
	return self.ratings[playerId] ~= nil
end
function Matchmaker:enqueue(playerId: number, rating: number): boolean
	if self:contains(playerId) then
		return false
	end
	table.insert(self.line, playerId)
	self.ratings[playerId] = rating
	return true
end
function Matchmaker:dequeue(playerId: number): boolean
	local at = table.find(self.line, playerId)
	if at == nil then
		return false
	end
	table.remove(self.line, at)
	self.ratings[playerId] = nil
	return true
end
function Matchmaker:size(): number
	return #self.line
end
function Matchmaker:position(playerId: number): number?
	return table.find(self.line, playerId)
end
function Matchmaker:averageRating(): number
	if #self.line == 0 then
		return 0
	end
	local sum = 0
	for _, id in self.line do
		sum += self.ratings[id]
	end
	return sum / #self.line
end
function Matchmaker:nextMatch()
	local need = 2 * self.teamSize
	if #self.line < need then
		return nil
	end
	local picked, rating = {}, {}
	for i = 1, need do
		picked[i] = self.line[i]
		rating[picked[i]] = self.ratings[picked[i]]
	end
	for _, id in picked do
		self:dequeue(id)
	end
	table.sort(picked, function(x, y)
		return rating[x] > rating[y]
	end)
	local match = { a = {}, b = {} }
	for pos, id in picked do
		local slot = (pos - 1) % 4
		if slot == 0 or slot == 3 then
			table.insert(match.a, id)
		else
			table.insert(match.b, id)
		end
	end
	return match
end
return Matchmaker"""
    avg = sum(ratings[:n]) / n
    test = TEST_HEAD + _t("""local mm = M.new and select(2, pcall(M.new, $team)) or {}
local ratings = $ratings
check("enqueue and refuse duplicates", safe(function()
	for i = 1, $n do mm:enqueue(i, ratings[i]) end
	return mm:enqueue(1, 5) == false and mm:size() == $n
end))
check("contains and position", safe(function() return mm:contains(2) == true and mm:position(1) == 1 and mm:position($n) == $n and mm:contains(99) == false end))
check("averageRating", safe(function() return math.abs(mm:averageRating() - $avg) < 0.0001 end))
check("nextMatch snake-drafts the longest waiting players by rating", safe(function()
	mm:enqueue($n1, ratings[$n1])
	local m = mm:nextMatch()
	return m ~= nil and deepEqual(m.a, $ateam) and deepEqual(m.b, $bteam)
end))
check("matched players leave the queue", safe(function() return mm:size() == 1 and mm:position($n1) == 1 and mm:contains(1) == false end))
check("not enough players gives nil", safe(function() return mm:nextMatch() == nil end))
check("dequeue removes and refuses unknown ids", safe(function() return mm:dequeue($n1) == true and mm:dequeue($n1) == false and mm:size() == 0 end))
check("an empty queue averages 0", safe(function() return mm:averageRating() == 0 end))
""", team=team, ratings=lua_list(ratings), n=n, n1=n + 1, avg=repr(avg), ateam=lua_list(a_team),
                         bteam=lua_list(b_team))
    return Variant(prompt, test, ref, _truncate(ref), (_pattern("returns", r"return\s+Matchmaker\s*$", "module return"),))


# =====================================================================================================================
# invented API name: real built-ins only; the bad answer calls a helper module that does not exist
# =====================================================================================================================

_INVENTED = re.compile(r"\b(?:StringUtil|TableUtil|MathUtil|StringExtras|TimeFormat|Bitwise)\s*\.")


def _ia_forbid():
    return (_pattern("no_invented_helper", _INVENTED.pattern, "no helper module that does not exist"),)


def _ia_command(v: int, ctx: str) -> Variant:
    prefix = ("/", "!", ";", ":", ">")[v % 5]
    cmd = ("give", "kick", "tp", "heal", "mute")[v % 5]
    prompt = (f"For {ctx}, write a ModuleScript Commands with Commands.parse(text: string) and "
              "Commands.numberArg(text: string, index: number): number?. parse returns nil unless text starts with "
              f"\"{prefix}\"; otherwise it returns {{ command = <lowercased first word without the prefix>, args = "
              "{the remaining words} }, splitting on spaces and dropping empty pieces (string.split, string.sub, "
              "string.lower). numberArg returns tonumber of the index-th argument, or nil.")
    ref = _t("""local Commands = {}
local PREFIX = "$prefix"
function Commands.parse(text: string)
	if string.sub(text, 1, #PREFIX) ~= PREFIX then
		return nil
	end
	local words = {}
	for _, piece in string.split(string.sub(text, #PREFIX + 1), " ") do
		if piece ~= "" then
			table.insert(words, piece)
		end
	end
	if #words == 0 then
		return nil
	end
	local command = string.lower(table.remove(words, 1) :: string)
	return { command = command, args = words }
end
function Commands.numberArg(text: string, index: number): number?
	local parsed = Commands.parse(text)
	if parsed == nil then
		return nil
	end
	local arg = parsed.args[index]
	return if arg then tonumber(arg) else nil
end
return Commands""", prefix=prefix)
    bad = ref.replace('string.split(string.sub(text, #PREFIX + 1), " ")', 'StringUtil.split(string.sub(text, #PREFIX + 1), " ")')
    test = TEST_HEAD + _t("""check("a command with arguments", safe(function() local p = M.parse("${prefix}${CMD} Alice $amt") return p ~= nil and p.command == "$cmd" and deepEqual(p.args, { "Alice", "$amt" }) end))
check("text without the prefix is not a command", safe(function() return M.parse("hello there") == nil end))
check("extra spaces are dropped", safe(function() local p = M.parse("${prefix}$cmd   Bob   7 ") return p ~= nil and deepEqual(p.args, { "Bob", "7" }) end))
check("numberArg converts an argument", safe(function() return M.numberArg("${prefix}$cmd Alice $amt", 2) == $amt end))
check("numberArg returns nil for words and missing arguments", safe(function() return M.numberArg("${prefix}$cmd Alice", 1) == nil and M.numberArg("${prefix}$cmd Alice", 3) == nil end))
""", prefix=prefix, cmd=cmd, CMD=cmd.upper(), amt=50 + 7 * v)
    return Variant(prompt, test, ref, _fence(bad), (_pattern("split", r"string\s*\.\s*split\s*\(|:\s*split\s*\(", "splits with string.split"),),
                   _ia_forbid(), static_error=r"Unknown global 'StringUtil'")


def _ia_tables(v: int, ctx: str) -> Variant:
    sep = (", ", " | ", " / ", "; ", " + ")[v % 5]
    words = ["red", "blue", "red", "green", "blue", "gold"][: 5 + v % 2]
    dedup = list(dict.fromkeys(words))
    prompt = (f"For {ctx}, write a ModuleScript ListTools with ListTools.contains(list, value): boolean, "
              "ListTools.indexOf(list, value): number (0 when absent), ListTools.dedupe(list) -> a new array keeping "
              f"the first occurrence of each value in order, and ListTools.join(list) joining with \"{sep}\". Use "
              "table.find, table.insert and table.concat.")
    ref = _t("""local ListTools = {}
function ListTools.contains(list, value): boolean
	return table.find(list, value) ~= nil
end
function ListTools.indexOf(list, value): number
	return table.find(list, value) or 0
end
function ListTools.dedupe(list)
	local out = {}
	for _, v in list do
		if not table.find(out, v) then
			table.insert(out, v)
		end
	end
	return out
end
function ListTools.join(list): string
	return table.concat(list, "$sep")
end
return ListTools""", sep=sep)
    bad = ref.replace("return table.find(list, value) ~= nil", "return TableUtil.contains(list, value)")
    test = TEST_HEAD + _t("""local words = $words
check("contains", safe(function() return M.contains(words, "green") == true and M.contains(words, "pink") == false end))
check("indexOf", safe(function() return M.indexOf(words, "blue") == 2 and M.indexOf(words, "pink") == 0 end))
check("dedupe keeps first occurrences in order", safe(function() return deepEqual(M.dedupe(words), $dedup) end))
check("dedupe returns a new table", safe(function() return M.dedupe(words) ~= words and #words == $n end))
check("join", safe(function() return M.join({ "a", "b", "c" }) == "a${sep}b${sep}c" end))
""", words=lua_list(words), dedup=lua_list(dedup), n=len(words), sep=sep)
    return Variant(prompt, test, ref, _fence(bad), (_pattern("find", r"table\s*\.\s*find\s*\(", "uses table.find"),),
                   _ia_forbid(), static_error=r"Unknown global 'TableUtil'")


def _ia_math(v: int, ctx: str) -> Variant:
    step = (5, 10, 0.5, 2, 25)[v % 5]
    prompt = (f"For {ctx}, write a ModuleScript Numbers with Numbers.lerp(a, b, t) (t clamped to 0..1 with math.clamp), "
              f"Numbers.snap(n) rounding n to the nearest multiple of {_num(step)} with math.round, Numbers.sign(n) "
              "(-1, 0 or 1, math.sign) and Numbers.roundTo(n, decimals) rounding half away from zero to that many "
              "decimals (math.round).")
    ref = _t("""local Numbers = {}
function Numbers.lerp(a: number, b: number, t: number): number
	return a + (b - a) * math.clamp(t, 0, 1)
end
function Numbers.snap(n: number): number
	return math.round(n / $step) * $step
end
function Numbers.sign(n: number): number
	return math.sign(n)
end
function Numbers.roundTo(n: number, decimals: number): number
	local f = 10 ^ decimals
	return math.round(n * f) / f
end
return Numbers""", step=_num(step))
    bad = ref.replace("return a + (b - a) * math.clamp(t, 0, 1)", "return MathUtil.lerp(a, b, math.clamp(t, 0, 1))")
    s = Fraction(str(step))
    x = s * 3 + s * Fraction(2, 5)                            # rounds down to 3 steps
    test = TEST_HEAD + _t("""check("lerp inside the range", safe(function() return M.lerp($a, $b, 0.5) == $mid end))
check("lerp clamps t", safe(function() return M.lerp($a, $b, 2) == $b and M.lerp($a, $b, -1) == $a end))
check("snap to the nearest step", safe(function() return M.snap($x) == $s3 end))
check("sign", safe(function() return M.sign(-4) == -1 and M.sign(0) == 0 and M.sign(9) == 1 end))
check("roundTo", safe(function() return M.roundTo(2.5, 0) == 3 and M.roundTo(-2.5, 0) == -3 and M.roundTo(1.25, 1) == 1.3 end))
""", x=_num(float(x)), s3=_num(float(s * 3)), a=10 * (v + 1), b=10 * (v + 1) + 20, mid=10 * (v + 1) + 10)
    return Variant(prompt, test, ref, _fence(bad), (_pattern("clamp", r"math\s*\.\s*clamp\s*\(", "uses math.clamp"),),
                   _ia_forbid(), static_error=r"Unknown global 'MathUtil'")


def _ia_text(v: int, ctx: str) -> Variant:
    prefix = ("[VIP]", "#", "@", "!!", "::")[v % 5]
    prompt = (f"For {ctx}, write a ModuleScript Text with Text.trim(s) (remove leading and trailing whitespace, "
              "string.match), Text.words(s) -> the non-empty space-separated words, Text.startsWith(s, prefix): "
              f"boolean (string.sub; for example the tag \"{prefix}\") and Text.capitalize(s) (first letter upper case, "
              "the rest unchanged, string.upper).")
    ref = """local Text = {}
function Text.trim(s: string): string
	return string.match(s, "^%s*(.-)%s*$") or s
end
function Text.words(s: string): { string }
	local out = {}
	for word in string.gmatch(s, "%S+") do
		table.insert(out, word)
	end
	return out
end
function Text.startsWith(s: string, prefix: string): boolean
	return string.sub(s, 1, #prefix) == prefix
end
function Text.capitalize(s: string): string
	return string.upper(string.sub(s, 1, 1)) .. string.sub(s, 2)
end
return Text"""
    bad = ref.replace("return string.sub(s, 1, #prefix) == prefix", "return StringExtras.startsWith(s, prefix)")
    test = TEST_HEAD + _t("""check("trim", safe(function() return M.trim("  hi there \\t") == "hi there" and M.trim("") == "" end))
check("words", safe(function() return deepEqual(M.words("  one two   three "), { "one", "two", "three" }) end))
check("startsWith", safe(function() return M.startsWith("${prefix}Sam", "$prefix") == true and M.startsWith("Sam", "$prefix") == false end))
check("capitalize", safe(function() return M.capitalize("orbit") == "Orbit" and M.capitalize("x") == "X" end))
""", prefix=prefix)
    return Variant(prompt, test, ref, _fence(bad), (_pattern("sub", r"string\s*\.\s*sub\s*\(|:\s*sub\s*\(", "uses string.sub"),),
                   _ia_forbid(), static_error=r"Unknown global 'StringExtras'")


def _ia_clock(v: int, ctx: str) -> Variant:
    sep = (":", ".", "-")[v % 3]
    secs = 3723 + 61 * v
    hh, mm, ss = secs // 3600, secs % 3600 // 60, secs % 60
    prompt = (f"For {ctx}, write a ModuleScript Clock with Clock.format(seconds) -> \"hh{sep}mm{sep}ss\" (two digits each, "
              "seconds rounded down, string.format with %02d) and Clock.parse(text) -> the number of seconds, or nil "
              f"when text is not exactly three numeric parts separated by \"{sep}\" (string.split, tonumber).")
    ref = _t("""local Clock = {}
local SEP = "$sep"
function Clock.format(seconds: number): string
	local s = math.floor(seconds)
	return string.format("%02d" .. SEP .. "%02d" .. SEP .. "%02d", s // 3600, s % 3600 // 60, s % 60)
end
function Clock.parse(text: string): number?
	local parts = string.split(text, SEP)
	if #parts ~= 3 then
		return nil
	end
	local h, m, s = tonumber(parts[1]), tonumber(parts[2]), tonumber(parts[3])
	if h == nil or m == nil or s == nil then
		return nil
	end
	return h * 3600 + m * 60 + s
end
return Clock""", sep=sep)
    bad = ref.replace('return string.format("%02d" .. SEP .. "%02d" .. SEP .. "%02d", s // 3600, s % 3600 // 60, s % 60)',
                      "return TimeFormat.format(s, SEP)")
    text = f"{hh:02d}{sep}{mm:02d}{sep}{ss:02d}"
    test = TEST_HEAD + _t("""check("format pads to two digits", safe(function() return M.format($secs) == "$text" end))
check("format rounds seconds down", safe(function() return M.format(59.9) == "00${sep}00${sep}59" end))
check("parse reads three parts", safe(function() return M.parse("$text") == $secs end))
check("parse refuses malformed text", safe(function() return M.parse("12${sep}30") == nil and M.parse("aa${sep}bb${sep}cc") == nil end))
""", secs=secs, text=text, sep=sep)
    return Variant(prompt, test, ref, _fence(bad), (_pattern("format", r"string\s*\.\s*format\s*\(", "uses string.format"),),
                   _ia_forbid(), static_error=r"Unknown global 'TimeFormat'")


_FLAGS = (("Chat", "Build", "Kick", "Ban"), ("Fly", "Noclip", "Spawn", "Admin"), ("Trade", "Gift", "Sell", "Auction"),
          ("Voice", "Emote", "Paint", "Host"), ("Read", "Write", "Invite", "Owner"))


def _ia_flags(v: int, ctx: str) -> Variant:
    f1, f2, f3, f4 = _FLAGS[v % len(_FLAGS)]
    prompt = (f"For {ctx}, write a ModuleScript Perms with Perms.FLAGS = {{ {f1} = 1, {f2} = 2, {f3} = 4, {f4} = 8 }} and "
              "functions Perms.has(mask, flag): boolean, Perms.grant(mask, flag): number, Perms.revoke(mask, flag): "
              "number and Perms.list(mask) -> the names of the set flags sorted alphabetically. Use bit32.band, "
              "bit32.bor and bit32.bnot.")
    ref = _t("""local Perms = {}
Perms.FLAGS = { $f1 = 1, $f2 = 2, $f3 = 4, $f4 = 8 }
function Perms.has(mask: number, flag: number): boolean
	return bit32.band(mask, flag) ~= 0
end
function Perms.grant(mask: number, flag: number): number
	return bit32.bor(mask, flag)
end
function Perms.revoke(mask: number, flag: number): number
	return bit32.band(mask, bit32.bnot(flag))
end
function Perms.list(mask: number): { string }
	local out = {}
	for name, bit in Perms.FLAGS do
		if bit32.band(mask, bit) ~= 0 then
			table.insert(out, name)
		end
	end
	table.sort(out)
	return out
end
return Perms""", f1=f1, f2=f2, f3=f3, f4=f4)
    bad = ref.replace("return bit32.bor(mask, flag)", "return Bitwise.bor(mask, flag)")
    test = TEST_HEAD + _t("""local F = M.FLAGS or {}
check("has", safe(function() return M.has(5, F.$f1) == true and M.has(5, F.$f2) == false end))
check("grant sets a bit once", safe(function() return M.grant(1, F.$f3) == 5 and M.grant(5, F.$f3) == 5 end))
check("revoke clears only that bit", safe(function() return M.revoke(13, F.$f3) == 9 and M.revoke(9, F.$f2) == 9 end))
check("list is sorted by name", safe(function() return deepEqual(M.list(13), $names) end))
""", f1=f1, f2=f2, f3=f3, names=lua_list(sorted([f1, f3, f4])))
    return Variant(prompt, test, ref, _fence(bad), (_pattern("bit32", r"bit32\s*\.\s*band\s*\(", "uses bit32.band"),),
                   _ia_forbid(), static_error=r"Unknown global 'Bitwise'")


# =====================================================================================================================
# the catalogue
# =====================================================================================================================

def _ctx(*items):
    return tuple(items)


SPECS = (
    Spec("COOLDOWN", WL, "Cooldown with an exact ready boundary", _ctx(
        "a sword swing", "a dash ability", "a healing potion", "an emote wheel", "a grappling hook",
        "a trade request button", "a vote-kick prompt", "a teleport pad", "a daily reward chest", "a fireball spell"),
        _wl_cooldown),
    Spec("FALLOFF", WL, "Explosion damage falloff with clamped ends", _ctx(
        "a rocket launcher", "a grenade", "a lightning strike", "a sniper's damage drop", "a shockwave",
        "a landmine", "a mortar shell", "a poison cloud", "a meteor impact", "a firework blast"), _wl_falloff),
    Spec("HISTORY", WL, "Fixed-size recent history, oldest first", _ctx(
        "a chat log", "a kill feed", "an undo list in a building tool", "recent trades", "recent damage numbers",
        "a notification tray", "recent purchases", "a lap-time board", "an admin action log", "recent emotes"),
        _wl_history),
    Spec("RANK", WL, "Leaderboard ranking with ties", _ctx(
        "an obby speedrun board", "a round's kill leaderboard", "a fishing tournament", "a racing results screen",
        "a trivia game", "a tycoon richest-players list", "a parkour contest", "a building contest vote",
        "a tower defense high-score table", "a team scrimmage"), _wl_rank),
    Spec("WAVES", WL, "Wave sizes with a cap and boss waves", _ctx(
        "a zombie survival game", "a tower defense map", "an alien invasion mode", "a dungeon crawler",
        "a castle siege", "a pirate raid", "a space shooter", "a monster arena", "a farm defense minigame",
        "a robot uprising mode"), _wl_waves),
    Spec("LEVELS", WL, "Level from total XP with exact thresholds", _ctx(
        "a simulator game", "a pet training system", "a fishing skill", "a mining skill", "a battle pass",
        "a sword mastery track", "a farming profession", "a racing licence", "a cooking skill", "a clan level"),
        _wl_levels),
    Spec("INVENTORY", RF, "Inventory with every listed method", _ctx(
        "a survival backpack", "a pet food bag", "a mining cart", "an adventurer's satchel", "a garden shed",
        "a ship's cargo hold", "a crafting bench", "a lunch box minigame", "a toolbelt", "a treasure chest"),
        _rf_inventory),
    Spec("PARTY", RF, "Party roster with leader handover", _ctx(
        "a dungeon party", "a squad lobby", "a racing crew", "a raid group", "a trading guild", "a heist crew",
        "a fishing boat crew", "a band in a music game", "a rescue team", "a camping group"), _rf_party),
    Spec("SETTINGS", RF, "Typed settings store with defaults", _ctx(
        "a game's options menu", "a client graphics menu", "an accessibility panel", "a controls menu",
        "a HUD settings page", "an audio mixer", "a camera settings page", "a chat settings page",
        "a mobile settings drawer", "a spectator settings page"), _rf_settings),
    Spec("QUEST", RF, "Quest tracker with completion callbacks", _ctx(
        "a lumberjack quest", "a daily challenge", "a combat bounty", "a beach cleanup quest", "a racing challenge",
        "a tutorial checklist", "a seasonal event", "a mining contract", "a gathering mission", "a clan task"),
        _rf_quest),
    Spec("TIMER", RF, "Pausable round timer", _ctx(
        "a deathmatch round", "a hide-and-seek round", "a cooking contest", "a build battle", "a trivia round",
        "a capture-the-flag match", "an escape room", "a boss fight phase", "a parkour time trial",
        "a sword duel"), _rf_timer),
    Spec("SHOP", RF, "Shop catalogue with discounts", _ctx(
        "a weapon shop", "a cosmetics shop", "a fishing supply store", "a car parts garage", "a farm store",
        "a pet shop", "a potion stall", "a furniture store", "a gear vending machine", "a space station shop"),
        _rf_shop),
    Spec("VEC2", SC, "Strictly typed 2D vector maths", _ctx(
        "aiming a projectile", "steering an NPC", "a 2D minimap", "a joystick input", "knockback direction",
        "a top-down shooter", "a radar screen", "a drag gesture", "a homing missile", "a boids flock"), _sc_vec),
    Spec("LOOKUP", SC, "Narrowing optional lookups under strict mode", _ctx(
        "a scoreboard", "a guild roster", "a race result list", "a duel ladder", "a quiz score sheet",
        "a party finder", "an arena season table", "a clan donation list", "a trade history", "a bounty board"),
        _sc_lookup),
    Spec("QUEUE", SC, "Strictly typed queue without shifting", _ctx(
        "a matchmaking line", "a ride queue in a theme park game", "a server join queue", "a turn order",
        "a chat moderation queue", "a build request queue", "a support ticket desk", "a spawn queue",
        "a boss arena queue", "a karaoke stage list"), _sc_queue),
    Spec("ARMOR", SC, "Typed damage helper called correctly", _ctx(
        "a sword fighting game", "a tank battle", "a mech arena", "a medieval siege", "a zombie shooter",
        "a boxing game", "a dragon fight", "a robot combat game", "a pirate duel", "a space marine mode"),
        _sc_armor),
    Spec("STATS", SC, "Typed summary that always has every field", _ctx(
        "lap times", "damage dealt per round", "fish weights", "jump heights", "coin pickups per minute",
        "ping samples", "build scores", "survival times", "accuracy samples", "crop yields"), _sc_stats),
    Spec("ELEMENTS", SC, "Element multiplier with a well-formed if-chain", _ctx(
        "a pet battle game", "a wizard duel", "a card game", "a monster trainer", "an elemental arena",
        "a tower defense with damage types", "a fighting game", "a puzzle battler", "a dungeon spell system",
        "a creature collector"), _sc_elements),
    Spec("TEXTFORMAT", CO, "Long text-formatting module, finished", _ctx(
        "a game HUD", "a shop UI", "a leaderboard display", "a round summary screen", "a trading window",
        "an inventory tooltip", "a stats panel", "a donation board", "a tycoon earnings display", "a quest log",
        "a race timer display", "a battle pass page", "a profile card", "a mail inbox", "a bank screen"),
        _co_text, variants=15),
    Spec("GRID", CO, "Long tile-grid helper module, finished", _ctx(
        "a match-three board", "a minesweeper clone", "a farming plot grid", "a dungeon map", "a chess-like board",
        "a city builder", "a puzzle room", "a snake game", "a battleship board", "a sokoban level",
        "a tower defense grid", "a seating chart", "a garden planner", "a sudoku helper", "a tic-tac-toe variant"),
        _co_grid, variants=15),
    Spec("BANK", CO, "Long bank ledger module with undo, finished", _ctx(
        "a tycoon economy", "a roleplay town bank", "a trading game", "a pirate treasury", "a clan vault",
        "a simulator's coin wallet", "a casino-free arcade token system", "a school roleplay", "a space colony",
        "a farming co-op", "a racing team budget", "a festival ticket system", "a mall shop till",
        "a heist payout", "a kingdom treasury"), _co_ledger, variants=15),
    Spec("MATCH", CO, "Long matchmaking module with snake draft, finished", _ctx(
        "a 2v2 arena", "a 3v3 basketball game", "a team deathmatch lobby", "a capture-the-flag lobby",
        "a dodgeball game", "a soccer game", "a paintball-free laser tag game", "a racing team event",
        "a tug-of-war minigame", "a volleyball game", "a hockey game", "a battle royale squads lobby",
        "a quiz team game", "a relay race", "a king-of-the-hill mode"), _co_match, variants=15),
    Spec("COMMANDS", IA, "Chat command parser with real string functions", _ctx(
        "an admin panel", "a private server", "a moderator tool", "a debug console", "a roleplay server",
        "a racing lobby", "a minigame host", "a building server", "a classroom game", "a test place"), _ia_command),
    Spec("LISTTOOLS", IA, "List helpers with table.find and table.concat", _ctx(
        "a team colour picker", "a tag system", "a recently-played list", "a badge list", "a party chat",
        "a loot table", "a playlist", "an emote list", "a map vote", "a crafting recipe book"), _ia_tables),
    Spec("NUMBERS", IA, "Number helpers with real math functions", _ctx(
        "a camera smoothing script", "a health bar", "a building grid snap", "a speedometer", "a volume slider",
        "a damage popup", "a price display", "a stamina bar", "a day-night cycle", "a fishing reel"), _ia_math),
    Spec("TEXT", IA, "Text helpers with real string functions", _ctx(
        "a chat filter preview", "a name tag", "a sign editor", "a pet naming screen", "a team chat",
        "a mailbox", "a quest dialogue box", "a guild name form", "a billboard", "a lobby title"), _ia_text),
    Spec("CLOCK", IA, "Clock formatting and parsing with real string functions", _ctx(
        "a speedrun timer", "a server uptime label", "a cooking timer", "a round timer label", "a parkour split",
        "a race stopwatch", "an event countdown", "a session timer", "a boss respawn label", "a shift clock"),
        _ia_clock),
    Spec("PERMS", IA, "Permission flags with bit32", _ctx(
        "an admin rank system", "a private server's permissions", "a building permission system",
        "a trading permission system", "a voice chat role system", "a club roles system", "a moderator panel",
        "a classroom roles system", "a creator tools menu", "a guild ranks system"), _ia_flags),
)


def specs_for(cause: str) -> list[Spec]:
    return [s for s in SPECS if s.cause == cause]


@dataclass(frozen=True)
class Generated:
    task: dict
    test_body: str
    reference_answer: str     # never written to a practice pool
    bad_answer: str           # never written to a practice pool
    spec: str
    static_error: str = ""


def task_id(spec: Spec, variant: int) -> str:
    return f"LG-{CAUSE_CODES[spec.cause]}-{spec.key}-{variant + 1:02d}"


def build(spec: Spec, variant: int, *, source: str = "") -> Generated:
    """One task of one spec. `variant` picks the numbers, names and context."""
    if not 0 <= variant < spec.variants:
        raise ValueError(f"{spec.key} has variants 0..{spec.variants - 1}")
    ctx = spec.contexts[variant % len(spec.contexts)]
    made = spec.build(variant, ctx)
    tid = task_id(spec, variant)
    checks = count_checks(made.test)
    task = {
        "id": tid,
        "category": "ledger-" + CAUSE_SLUGS[spec.cause],
        "difficulty": 2,
        "run_mode": "automated",
        "goal": spec.goal + f" ({ctx})",
        "prompt": made.prompt + " " + CAUSE_TAILS[spec.cause],
        "source": "failure-ledger-v2",
        "targets_cause": spec.cause,
        "spec": spec.key,
        "split": "practice",
        "required_evidence": ["one complete fenced Luau module"],
        "pass_conditions": ["Luau static checking succeeds" + (" in strict mode" if made.strict else ""),
                            f"all {checks} runtime unit-test assertions pass in the Luau VM",
                            "required patterns present and forbidden patterns absent"],
        "budget": {"model_calls": 3, "tool_calls": 6, "output_tokens": 1600 if spec.cause == CO else 1200,
                   "wall_seconds": 720},
        "hard_fail": ["A runtime unit-test assertion fails", "Luau static check reports an error"],
        "auto": {
            "compile_mode": "exact",
            "strict": made.strict,
            "unit_test": {"file": f"tests/{tid}.luau", "checks": checks},
            "require": [dict(p) for p in made.require],
            "forbid": [dict(p) for p in made.forbid],
        },
    }
    if source:
        task["targets_failure"] = source
    return Generated(task, made.test, _fence(made.reference), made.bad, spec.key, made.static_error)


def build_all() -> list[Generated]:
    return [build(spec, v) for spec in SPECS for v in range(spec.variants)]


def pool(total: int | None = None, causes=None) -> list[Generated]:
    """Up to `total` tasks spread evenly over the causes (round-robin over specs, then variants)."""
    wanted = [c for c in (causes or (WL, RF, SC, CO, IA))]
    queues = {c: [(s, v) for v in range(max(s.variants for s in specs_for(c)))
                  for s in specs_for(c) if v < s.variants] for c in wanted}
    out, i = [], 0
    limit = total if total is not None else sum(len(q) for q in queues.values())
    while len(out) < limit and any(queues.values()):
        cause = wanted[i % len(wanted)]
        if queues[cause]:
            spec, v = queues[cause].pop(0)
            out.append(build(spec, v))
        i += 1
    return out
