# STAR Native Roblox UI — composition, interaction and visual fidelity

Use when creating HUDs, inventories, shops, combat interfaces, menus, wardrobes, settings, dialogs and creator dashboards. The user must receive real editable Roblox GUI objects rather than a picture of a screen.

## Before production: design analysis contract

Ask for or infer only safe noncritical defaults; preserve user-provided colors, shapes, icons and placement. A real reference image is a specification, not a generic "inspired by" moodboard.

Create an explicit visual inventory for each screen:
- Layout: screenshot width/height, safe-area margins, anchor points, parent-child groups, component bounding boxes, white space and scroll behavior.
- Typography: font family available in Roblox, weights, hierarchy, actual sizes, text wrapping and localization expansion plan.
- Palette: background, card, border, icon, regular/secondary text, accent, warnings and states. Avoid random unrelated gradients.
- Component language: radius vocabulary, strokes, drop shadows if any, icons from one family, image style and texture choice.
- Interaction: what every button does, action prerequisites, loading/error/success state, mouse hover, keyboard/gamepad focus, touch selection and motion reduction.
- Forbidden artifacts: disordered alignment, neon/oversaturation contradicting the reference, decoration without function, distorted icons, circular placeholders for detailed art, overlapped labels, fake frames with unreadable baked-in text.

If the supplied reference is not legible enough to measure, label uncertain values as estimates and request a clearer image before claiming exact reproduction.

## Hierarchy and composition before decoration

1. Sketch a content hierarchy by importance: gameplay actions > health/goal/feedback > optional shops > low-salience status. Avoid making everything the same size.
2. For each panel, define one base grid (often 4/8px rhythm as a practical convention, not an engine requirement); measure horizontal and vertical alignment as independent constraints.
3. Use real Roblox ScreenGui / Frame / TextLabel / TextButton / ImageLabel / ImageButton components; use UIListLayout, UIGridLayout, UIPageLayout, UIPadding and constraint objects as appropriate.
4. Prefer parent-relative scale for proportional placement; use pixel offsets where fixed-size touch targets and deliberate spacing matter. Avoid unbounded TextScaled with no size constraints.
5. Use safe area and screen insets so the notch, Roblox top bar and touch controls do not obstruct key interactions. Test all targeted input types.
6. Use a theme source-of-truth. Roblox now offers built-in Style Editor with token sheets, rules and themes https://create.roblox.com/docs/ui/styling/editor . If the environment cannot use it, maintain an explicit Lua tokens table consistently.
7. Use reusable native components: ButtonPrimary, IconButton, Tab, Card, ItemGridCell, Modal, CurrencyLabel and Notification. Provide normal, hover, press, focus, disabled, loading and success/error states.
8. Use TweenService carefully for microinteractions. Limit translation/scale/opacity changes, use interruptible/cancellable transitions and avoid perpetual float/pulse effects everywhere.
9. Follow Roblox reduced-motion preference from GuiService.ReducedMotionEnabled and adapt text to PreferredTextSize where supported. Accessibility official: https://create.roblox.com/docs/production/publishing/accessibility .

## Responsive / functional quality matrix

| View | Required inspection |
| --- | --- |
| Desktop 16:9 | Main actions and crosshair fit; no central gameplay occlusion |
| Phone landscape | Touch targets, safe inset, UI density and bottom thumb reach |
| Phone portrait (if supported) | Reflow or explicitly unsupported layout behavior; no tiny squeezed text |
| Narrow/split viewport | Labels wrap or truncate intentionally; component remains functional |
| Console/gamepad | Selection focus visible; explicit left/right/back mappings; no hover-only actions |
| Localization | Longer translated text; RTL when relevant; dynamic data values; no icon collisions |
| Accessibility | Contrast, preferred text size, reduced motion, meanings not encoded only by color |
| Loading/error | No dead-end controls or skeleton loaders that never resolve |

Official Roblox layout resources: https://create.roblox.com/docs/ui/list-flex-layouts ; https://create.roblox.com/docs/ui/size-modifiers ; https://create.roblox.com/docs/production/publishing/adaptive-design .

## Example: native component layering (not a screenshot export)

~~~text
StarterGui
  HUD (ScreenGui)
    SafeArea (Frame)
      TopBar (Frame)
        UIListLayout
        HealthBar (Frame)
        LevelLabel (TextLabel)
        ResourceCounter (Frame)
      Actions (Frame)
        UIListLayout
        InventoryButton (ImageButton)
        SettingsButton (ImageButton)
    InventoryModal (Frame, initially hidden)
      Heading (TextLabel)
      Close (TextButton)
      Grid (ScrollingFrame)
        UIGridLayout
      DetailPanel (Frame)
~~~

An approved SVG icon cannot always be treated as a native Roblox vector element: process/export supported image formats and import as source-backed assets. See Studio supported file types https://create.roblox.com/docs/studio/importer . Keep icon-license notices where necessary.

## Good game UI is not generic web UI

- HUD: minimal occlusion, glanceable hierarchy, information at the point of gameplay; avoid large menus occupying a firefight.
- Shop: price and value obvious, clear purchase confirmation, show ownership states; visual rarity should not replace text for colorblind accessibility.
- Inventory: category tabs, scalable cell hierarchy, readable item names, focus and scrolling; useful ViewportFrame for an actual 3D item when appropriate https://create.roblox.com/docs/ui/viewport-frames .
- Horror: constrained atmosphere, restrained motion and readability under dark lighting; never sacrifice critical controls for aesthetics.
- Cartoon: chunky buttons, consistent outline weights and intentional hand-designed icons; avoid arbitrary circles and mismatched corner radii.
- OLED: dark neutral surfaces, restrained accents, fine separations, accessible typography; only bloom/glow where it communicates interaction.
- Anime battle HUD: clear health/ability/cooldown priority, powerful hit feedback, visual separation from battlefield particles.

## Free/open UI design resources

- Penpot https://penpot.app/ — open-source layouts, prototypes, design systems and inspectable components.
- Figma https://www.figma.com/ — free tier for design and prototyping, with restrictions; Figma design file is NOT a Roblox Lua file. Adapt to Roblox native hierarchy.
- Inkscape https://inkscape.org/ — consistent icon set strokes, silhouettes, editable paths; export suitable raster images for Roblox.
- Krita https://krita.org/ — painted UI textures and hand-authored details.
- Kenney UI assets https://kenney.nl/assets (UI, input prompts, crosshairs) and CC0 usage https://kenney.nl/support .
- Lucide https://lucide.dev/ — consistent icon language (ISC license and Feather MIT notices in LICENSE); review source https://github.com/lucide-icons/lucide/blob/main/LICENSE .
- Apple Human Interface Guidelines https://developer.apple.com/design/human-interface-guidelines/layout and Roblox-specific UX guide https://create.roblox.com/docs/production/game-design/ui-ux-design . External HIG are *design heuristics*, not instructions to copy iOS chrome into Roblox.

## Visual audit checklist (screenshot + hierarchy + behavior)

- Every sibling control aligned within design tolerance explicitly chosen for this screen; no unexplained drift.
- No text clipping at tested viewport sizes; no text layered over icons; no label needing user zoom to read.
- Stroke and corner thickness consistent; no broken nine-slice stretching or raster blur.
- Every visible interactive element has an action and focus/disabled state.
- Main contrast remains readable in worst-background scene; avoid tiny pale text on semitransparent white.
- Hover and press styles are reversible; reduced-motion behavior works; updates don't flicker or continuously allocate.
- Compare approved reference style/spacing/component count, not screenshot pixel-perfect equivalence if font metrics or localization differ.
- Confirm GUI hierarchy is editable and responsive. Image-only replicas fail acceptance even if visually attractive.

Visual QA should include the screenshot, viewport and device settings, a component tree dump, an inventory of interactions clicked, known deviations and user-approved design decisions. Never say a generated Figma shot was tested as a native Roblox interface.
