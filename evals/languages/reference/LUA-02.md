In Lua 5.3+ numbers have integer and float subtypes, and `/` always returns a float. So `7 / 2` is `3.5` and `8 / 2` is `4.0`. The `%d` format accepts a float only when it has an exact integer value. `4.0` converts to `4`, but `3.5` has a fractional part, so it has no integer representation and `string.format` raises that error.

Fix it in one of these ways:
- Use floor division `//` when you want an integer: `total // count` gives `3`.
- Use `math.floor(total / count)`, or `math.tointeger(x)` when you only want to accept exact values.
- Print the real average with a float format such as `%.2f`.

```lua
print(string.format("%d avg", total // count))   -- 3
print(string.format("%.2f avg", total / count))  -- 3.50
```
