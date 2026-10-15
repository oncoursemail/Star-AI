`Sleep` has the `<suspends>` effect, so it can only be called from a function that is itself `<suspends>`. A `Subscribe` handler is an immediate (non-suspending) function: the event calls it synchronously and it cannot be `<suspends>`.

Keep the handler immediate and start the timed part as a new task with `spawn`. The spawned body must be a call to a `<suspends>` function:

```verse
OnPressed(Agent:agent):void =
    spawn{ OpenAfterDelay(Agent) }

OpenAfterDelay(Agent:agent)<suspends>:void =
    Sleep(2.0)
    Door.Open(Agent)
```

If presses can overlap, keep the returned `task` and cancel it, or guard with a `var` flag.
