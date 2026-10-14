`light-dark()` picks its first or second colour based on the element's used **color-scheme**, not directly on the OS setting. By default the color scheme is `normal`, which behaves as light only, so you always get `#ffffff`.

Fix: declare that your page supports both schemes:

```css
:root {
  color-scheme: light dark;
  --bg: light-dark(#ffffff, #0b0d10);
}
body { background: var(--bg); }
```
With `color-scheme: light dark` on `:root`, the browser follows the OS preference, and `light-dark()` returns the dark value in dark mode. It also makes form controls and scrollbars dark. `light-dark()` is Baseline (newly available since 2024), so this works in current Chrome, Firefox and Safari.
