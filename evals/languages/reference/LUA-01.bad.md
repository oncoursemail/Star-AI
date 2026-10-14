The problem is only that LÖVE does not enable Luau mode by default. LuaJIT supports continue and += just like Luau, so the syntax error comes from the print line. Change the backticks to double quotes:

```lua
print("enemy {e.name} has {e.hp}")
```
