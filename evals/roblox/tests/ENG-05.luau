local ret, env = load_answer()
local chunk = resolve(ret, env, "chunk")
local function shape(t)
	local out = {}
	for i, bucket in t do
		out[i] = {}
		for j, v in bucket do out[i][j] = v end
	end
	return out
end
check("five items in twos: 2, 2, 1", deepEqual(shape(chunk({ 1, 2, 3, 4, 5 }, 2)), { { 1, 2 }, { 3, 4 }, { 5 } }))
check("an empty list gives an empty list", deepEqual(shape(chunk({}, 3)), {}))
check("a size larger than the list gives one bucket", deepEqual(shape(chunk({ 1, 2 }, 5)), { { 1, 2 } }))
check("size 1 gives single-item buckets", deepEqual(shape(chunk({ "a", "b", "c" }, 1)), { { "a" }, { "b" }, { "c" } }))
check("size 0 and a negative size raise errors", throws(chunk, { 1 }, 0) and throws(chunk, { 1 }, -2))
check("a fractional size raises an error", throws(chunk, { 1, 2, 3 }, 2.5))
check("a non-number size raises an error", throws(chunk, { 1 }, "2"))
local input = { 1, 2, 3, 4 }
chunk(input, 3)
check("the input list is left alone", deepEqual(input, { 1, 2, 3, 4 }))
