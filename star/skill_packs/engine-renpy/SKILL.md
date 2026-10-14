---
name: engine-renpy
description: Ren'Py 8.5 (Python 3) visual novel engine: script labels/menus, define vs default, screens, ATL, saves/rollback, Android/web builds. Use for any Ren'Py question.
---
# engine-renpy
## Scope
Ren'Py 8.5.3 (May 2026), Python 3.12 inside. Check the project's version first (Launcher or renpy.version_string); 7.x and older are Python 2 and differ.
## Core model
All .rpy files compile at start; the init phase runs define, image, transform, screen, style and init python blocks; default sets variables for each new game; then the start label runs statement by statement. Game state lives in the store and is saved and rolled back; saves record the current statement. Screens are declarative UI that may be re-run at any time.
## Idioms
- `define e = Character("Eileen")` for constants, characters, config.*; `default points = 0` for anything that changes.
- Flow: `label start:`, say lines `e "Hi"`, `menu:` with choice blocks (optional `if` guards), `jump label`, `call label` plus `return`.
- Python: `$ points += 1` one-liners; `python:` blocks; functions and classes in `init python:`; named stores `init python in mystore:`.
- Images: `scene bg room`, `show eileen happy at center`, `with dissolve`, `hide eileen`.
- Screens: `screen name():` with frame, vbox, text, textbutton ... action ...; `show screen` (stays) vs `call screen` (waits; value in `_return` via `Return(v)`).
- Screen actions instead of code: SetVariable, IncrementVariable, Function, Jump, Hide, ShowMenu; screen-local `default` plus SetScreenVariable.
- ATL: `transform bob:` with `ease 0.5 yoffset -10`, `pause`, `repeat`, `parallel:`, `on show:`; apply with `show x at bob`.
- Interpolation `[points]`; text tags `{b}` `{w}` `{nw}`.
- Cross-playthrough data: `default persistent.seen = set()`, `persistent.x`, `renpy.save_persistent()`.
## Pitfalls
1. `define` for changing state: define values are constants and are not saved; use `default`.
2. Game state set in `init python` is not saved, does not roll back and leaks into new games.
3. Python 2 syntax (`print "x"`, `unicode`, `iteritems`, `xrange`) fails in Ren'Py 8.
4. Legacy `ui.textbutton`, `ui.vbox`, `ui.interact` APIs: write screen language instead.
5. 8.5: a screen statement must have a block; gui.* variables must use define or default.
6. Changing state inside screen code (`$ x += 1` in a screen) runs repeatedly due to prediction; use actions.
7. Python while-loops that show dialogue restart on load; write loops in Ren'Py script with labels.
8. Lambdas, generators, file handles or sockets stored in the store break saving.
9. Objects from imported Python modules (collections.defaultdict) do not roll back; use script literals or Ren'Py revertable types.
10. 8.4: `show expression "bg x"` now matches `show bg x`; 8.3: window show/hide no longer turn off window auto.
11. Deleting .rpyc files or renaming labels breaks existing saves.
12. Undefined persistent fields are None; give them a `default persistent.x`.
## Roblox to Ren'Py
Workspace -> layers with tagged images (scene/show/hide); Part -> displayable; Model -> LayeredImage
Script/LocalScript -> labels in .rpy files; ModuleScript -> init python functions or named stores
RemoteEvent -> none; DataStore -> save slots plus persistent; Players -> none (single reader)
Humanoid -> Character object; Heartbeat -> screen timer with repeat or a custom displayable render
TweenService -> ATL ease/linear; CollectionService -> image tags and attributes; Attributes -> store variables
ScreenGui -> screen language; UserInputService -> key statement, keymap, buttons
task.wait -> pause 1.0; Studio playtest -> Launcher Launch Project and Shift+R; release -> Build Distributions
## Skeleton
```renpy
define e = Character("Eileen")
default score = 0

screen hud():
    frame:
        xalign 0.98 yalign 0.02
        text "Score: [score]"

screen pick():
    vbox:
        align (0.5, 0.5)
        textbutton "Left" action Return("left")
        textbutton "Right" action Return("right")

label start:
    show screen hud
    e "Pick a door."
    call screen pick
    if _return == "left":
        $ score += 1
    menu:
        "Again":
            jump start
        "Stop":
            pass
    e "Score: [score]."
    return
```
## Verification
Run Launcher > Check Script (Lint) for undefined labels/images, then Launch Project; test save, load and rollback (mouse wheel) after a choice. Use Shift+R to reload and Shift+O for the console. Say "not run" unless the game was actually launched.
