In Lua 5.4 the `/` operator performs integer division when both numbers are integers, so 7/2 is 3 and that part is fine. The error is a bug in string.format with large numbers. Use tostring instead:

```lua
print(tostring(total / count) .. " avg")
```
