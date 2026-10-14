Your z-index is not high enough because the canvas overlay is also fixed. Set the modal to `z-index: 2147483647`, the maximum value, and add `!important` so nothing overrides it:

```css
.modal { z-index: 2147483647 !important; }
```
For Escape, add a keydown listener that hides the div. Pointer clicks behind it can be blocked with a full-screen transparent div.
