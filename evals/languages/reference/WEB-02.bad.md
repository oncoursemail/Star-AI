`light-dark()` is not supported yet in most browsers, it is still experimental. Use a media query instead:

```css
@media (prefers-color-scheme: dark) { :root { --bg: #0b0d10; } }
```
That is the only reliable way to follow the OS dark mode.
