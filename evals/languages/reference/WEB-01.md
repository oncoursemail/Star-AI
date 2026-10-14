The modal is trapped in a **stacking context**. Your header has `transform: translateZ(0)` and `z-index: 1`, so it creates its own stacking context: every z-index inside it, including the modal's 9999, only competes with other elements inside the header. From the outside, the whole header (modal included) is just a layer at z-index 1, which is below the canvas overlay at 10. Raising the number further cannot help.

The modern fix is a real `<dialog>` opened with `showModal()` (or a button with `command="show-modal" commandfor="settings"`). A modal dialog is rendered in the **top layer**, above everything regardless of z-index, transforms or overflow on its ancestors. It also makes the rest of the page **inert** (not clickable), moves focus into the dialog, and closes on **Escape**.

```html
<button command="show-modal" commandfor="settings">Settings</button>
<dialog id="settings">
  <form method="dialog"><button>Close</button></form>
</dialog>
```
```css
dialog::backdrop { background: rgb(0 0 0 / .5); }
```
Remove the old `z-index: 9999`; style the overlay with `::backdrop`. I have not run this in your page; check it by opening the menu and pressing Escape.
