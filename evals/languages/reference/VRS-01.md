`GetFortCharacter` is a failable function: it has the `<decides>` effect, because an agent may have no character (for example while eliminated). In Verse a failable function is called with square brackets, as in `Agent.GetFortCharacter[]`, and only inside a failure context: an `if` condition, a `for` filter, the left side of `or`, or a function that is itself `<decides>`. A plain `:void` function body is not a failure context, so the compiler rejects the call.

Bind it in an `if` condition. The body runs only when the call succeeds:

```verse
OnInteract(Agent:agent):void =
    if (Char := Agent.GetFortCharacter[]):
        Char.Damage(10.0)
```
