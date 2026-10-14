Verse functions can return null, so the fix is to check the result. Wrap the call in a try/catch block or check if Char is null before calling Damage:

```verse
Char := Agent.GetFortCharacter()
```
