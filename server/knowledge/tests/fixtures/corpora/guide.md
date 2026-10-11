# Authored lifecycle fixture

Keep the early constraint: cancel the previous animation before replacement.

```lua
local activeAnimation = nil
local function cancelPrevious()
    activeAnimation = nil
end
```

## Cleanup

Disconnect the signal when the fixture's component is destroyed.
This document was authored for tests and is not a fetched upstream page.
