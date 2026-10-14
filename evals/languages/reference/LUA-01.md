Three parts of that loop are **Luau-only syntax**, and LuaJIT (Lua 5.1 semantics) rejects all three:

1. `continue` is a Luau keyword. In LuaJIT (and Lua 5.2+) use `goto continue` with a `::continue::` label placed just before the loop's `end`.
2. `total += e.hp` is compound assignment, which only Luau has. Write `total = total + e.hp`.
3. The backtick string interpolation is Luau-only. Use `string.format` (or the `..` operator) instead.

```lua
local total = 0
for _, e in ipairs(enemies) do
  if e.dead then goto continue end
  total = total + e.hp
  print(string.format("enemy %s has %d", e.name, e.hp))
  ::continue::
end
```

Note that `%d` needs an integer-valued number. Use `%s` or `tostring` if `hp` can be fractional.
