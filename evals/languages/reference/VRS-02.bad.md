The fix is simple: just add <suspends> to the handler signature so it is allowed to sleep, and keep the Subscribe call unchanged.

```verse
OnPressed(Agent:agent)<suspends>:void =
    Sleep(2.0)
```
