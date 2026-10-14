# Ren'Py: STAR engine research
**Verified 2026-10-13 against official docs. Current stable: 8.5.3 "We Can Go to the Moon" (15 May 2026). Docs/changelog already list 8.5.4 (in development, not on the release page).** Free and open source (MIT-licensed engine; some bundled libraries under LGPL); no royalties.

## At a glance
| | |
|---|---|
| Best for | Visual novels, dating sims, kinetic novels, story-heavy games with choices, light minigames via screens |
| Weak at | Real-time action, physics, 3D (only basic GLTF models since 8.4), multiplayer, large non-VN game logic |
| Language(s) | Ren'Py script language (.rpy) + embedded Python 3 (Python 3.12 since 8.4); screen language; ATL (Animation and Transformation Language) |
| Editor / tooling | Ren'Py Launcher (create/launch/build/lint); any editor, official Visual Studio Code extension maintained by the Ren'Py project; Shift+R reload, Shift+D developer menu, Shift+O console |
| Platforms (export) | Windows, macOS, Linux (x86_64 and 64-bit ARM), Android (RAPT), iOS (renios), Web (Beta, WebAssembly) |
| License / cost | Free, MIT (engine) |
| Roblox-likeness | low: linear script interpreter with saves/rollback, not an instance tree or networked world |

## Architecture and lifecycle
- **Startup:** all `.rpy` files in `game/` are compiled to `.rpyc`, then the **init phase** runs every `init` block (`init python`, `define`, `image`, `transform`, `screen`, `style`) in priority order (`init -10 python:` runs earlier; `init offset = N` shifts a file). `python early` runs before that, at parse time. Then `default` statements set variables not already set, then splashscreen, main menu, and on Start the `start` label.
- **Script execution:** statements run one by one: say statements (`e "Hello"`), `show`/`scene`/`hide`, `with`, `menu`, `jump`, `call`/`return`, `$ python`, `pause`, `play`/`stop`. Each user interaction is a checkpoint.
- **Store:** game variables live in the `store` namespace. Everything changed after init is saved and rolls back; `define`d values are constants.
- **Rollback:** the player can scroll back; Ren'Py restores the store, shown images and screens. Saves happen at the start of the current statement in the outermost context.
- **Screens:** declarative UI described in screen language; re-evaluated (and predicted) many times, so they must be side-effect free. `show screen` (non-blocking) vs `call screen` (waits, result in `_return`).
- **Layers:** master, transient, screens, overlay; images have tags and attributes (`show eileen happy` replaces `eileen` with attribute `happy`).

## Project layout
```
MyVN/
  game/
    script.rpy        start label and story
    options.rpy       config.* / build.* settings (config.name, config.version, build.name)
    gui.rpy           gui.* variables (define/default)
    screens.rpy       say, choice, main_menu, preferences, save/load screens
    images/           auto-defined images by file name (eileen happy.png -> "eileen happy")
    audio/  gui/  tl/<language>/  libs/ (8.4+, third-party)  mods/ (8.4+)
    saves/            saves during development (also copied to the per-user save dir)
    cache/            generated (bytecode, screens)
  progressive_download.txt   (created on first web build)
  android.json / .android.json, android.keystore, bundle.keystore (after Android setup; keep secret)
```
`.rpyc` files must ship (or be kept) to keep save compatibility; do not delete them between releases.

## Scripting idioms
**Characters, variables, labels, menus:**
```renpy
define e = Character("Eileen", color="#c8ffc8")   # constant: never changed after init
define config.rollback_enabled = True             # config is always set with define

default affection = 0                              # game state: saved, rolls back
default persistent.endings_seen = set()            # persistent default

label start:
    scene bg room
    show eileen happy at center
    with dissolve
    e "Want to visit the library?"
    menu:
        "Sure!":
            $ affection += 1
            jump library
        "Maybe later." if affection < 5:
            e "Okay."
    call chapter2          # returns here after `return`
    return                 # ends the game (back to main menu)

label library:
    e "You have [affection] affection."   # [var] interpolation
    return
```
- `menu` choices can have `if` conditions; a menu can have a label (`menu choose_path:`) and a caption say line.
- `jump` transfers permanently; `call label` pushes a return point (`call ... from _call_x` helps save compatibility; Lint can add them).
- Local labels: `label .part1:` under a global label (8.5 relaxes rules so `chapter_1.part_1` can be declared under any global label).
- Python: `$ one_line()`, `python:` block (runs at that point, in store), `init python:` (runs at init; for functions/classes), `python early:`; named stores `init python in mystore:`, accessed as `mystore.x`.
- Text interpolation: `[name]`, `[value!t]` (translate), `{b}`, `{color=#f00}`, `{w}`, `{p}`, `{nw}` text tags. Since 8.2 bracket contents are evaluated as Python expressions.

**Screens:**
```renpy
screen stats():
    frame:
        xalign 0.98 yalign 0.02
        vbox:
            text "Affection: [affection]"
            textbutton "Close" action Hide("stats")

screen choose_gift():
    modal True
    vbox:
        align (0.5, 0.5)
        textbutton "Flowers" action Return("flowers")
        textbutton "Book" action Return("book")

label give:
    call screen choose_gift
    $ gift = _return
```
Actions: `Return(v)`, `Jump("label")`, `Call("label")`, `Show("screen")`, `Hide("screen")`, `ToggleScreen`, `SetVariable("x", v)`, `IncrementVariable`, `SetScreenVariable`, `Function(callable, *args)`, `ShowMenu("save")`, `Preference(...)`, `NullAction()`. Screen-local state: `default club = None` inside the screen.

**ATL transforms:**
```renpy
transform bob(dy=10):
    yoffset 0
    ease 0.6 yoffset dy
    ease 0.6 yoffset 0
    repeat

show eileen happy at center, bob(dy=6)
```
Statements: property set, `linear`/`ease`/`easein`/`easeout` warpers, `pause`, `repeat` (last in block), `block:`, `parallel:`, `choice:`, `on show:/on hide:/on hover:`, `function fn` (callback `fn(trans, st, at)` returns seconds or None), `contains:`.

## Pitfalls (what AI answers get wrong)
1. **`define` vs `default` (critical).** `define x = 0` is a constant: not saved, not part of rollback (unless changed, and changing it is a bug). `default x = 0` is for anything that changes. Using `define points = 0` then `$ points += 1` loses progress on load or behaves inconsistently. Likewise setting game state in `init python:` "leaks" between new games and is not saved.
2. **Mutable state in `init python`.** Variables set in `init python` are not saved and do not roll back. Put functions/classes there, state in `default`.
3. **Python 2 code.** Ren'Py 8 is Python 3 (3.12 since 8.4): `print "x"`, `unicode()`, `dict.iteritems()`, `xrange` fail. Ren'Py 7.x was the last Python 2 line.
4. **Legacy `ui.` functions.** `ui.textbutton`, `ui.vbox`, `ui.close`, `ui.interact` are the pre-screen-language API. Write `screen` statements. (`ui.ChoiceReturn`/`ui.ChoiceJump` remain documented only for fixed-rollback choice screens.)
5. **`screen` statement needs a block in 8.5.** `screen name():` with no body is now an error; parentheses are recommended even without parameters.
6. **Side effects inside screens.** Screens run during prediction and on every redraw; `$ x += 1` or `python:` that mutates state inside a screen fires repeatedly. Use actions (`SetVariable`, `Function`).
7. **Python loops for interaction.** A `while` loop in Python that calls `renpy.say`/`renpy.pause` restarts from the beginning on load (saves are per statement). Use Ren'Py script loops (`while` statement in script, labels) instead.
8. **Unpicklable objects in the store.** Lambdas, inner functions, file handles, sockets, generators, iterators assigned to store variables break saving. Keep them in function locals or `python hide`.
9. **Non-revertable containers.** Objects created inside imported Python modules (e.g. `collections.defaultdict`) do not roll back; use Ren'Py's revertable types (literal lists/dicts/sets in script, Ren'Py `defaultdict`).
10. **`show expression` change (8.4).** `show expression "bg washington"` now behaves like `show bg washington`; old behaviour via `define config.old_show_expression = True`.
11. **`window show/hide` no longer disable `window auto` (8.3).** Restore with `define config.window_functions_set_auto = True`.
12. **gui variables (8.5).** `gui.*` must be set with `define` or `default`; `default`ed gui variables now behave as documented. 8.5 also removed `pygame_sdl2` (use `renpy.pygame`) and replaced `config.images_directory` with `config.image_directories`.
13. **Persistent defaults.** Undefined `persistent.x` is `None`; use `default persistent.x = ...`. Persistent data loads before `init python`, so store only native types (or picklable classes from `python early`).
14. **Renaming/deleting labels and `.rpyc` files** breaks existing saves (saves point at statements). Keep old labels, ship `.rpyc`.

## Rendering
Model-based OpenGL renderer (GL2; ANGLE on Windows; GLES on mobile/web). Displayables: images, `Solid`, `Frame`, `Text`, `Movie`, `LayeredImage`, `Composite`, `Live2D` (web support in 8.5; 8.5.3 needs Live2D 5.3), `GLTFModel` (8.4, mesh+texture only). Shaders: `Transform(shader=...)`, `matrixcolor`, text shaders (8.3, `{shader}` tag, `renpy.register_text_shader`), custom shader parts with `renpy.register_shader`. Transitions: `dissolve`, `fade`, `Dissolve(0.5)`, `ImageDissolve`, `moveinright`. 8.4 added optional mipmaps (`config.mipmap = "auto"`) and automatic oversampling.

## Physics
No built-in support. Motion is ATL (tween-like) or Python in a Creator-Defined Displayable (`renpy.Displayable` with `render`/`event`) for minigames.

## Input
Keymap-driven: `config.keymap` binds events (`"dismiss"`, `"rollback"`, `"game_menu"`, `"skip"`), screen `key "K_SPACE" action ...`, buttons/bars/imagemaps for mouse/touch, gamepad support built in. `renpy.input("Name?")` for text entry (limited on Android for non-Western IMEs). Custom displayables receive pygame-style events via `renpy.pygame` (8.5+ name).

## UI
Screen language (vbox, hbox, grid, frame, window, fixed, side, viewport, vpgrid, text, textbutton, imagebutton, button, bar, vbar, input, key, timer, use, transclude, for/if) plus styles (`style name is default:` / `style_prefix`). The generated `screens.rpy`/`gui.rpy` contain say, choice, nvl, main_menu, game_menu, save/load, preferences, history, confirm, notify screens: edit those rather than writing from scratch. Variants (`variant "touch"`, `"small"`, `"mobile"`) adapt UI per device. Accessibility menu (Shift+A), self-voicing.

## Networking and multiplayer
No multiplayer. Desktop/mobile builds can use Python networking (`renpy.fetch()` is the documented HTTP helper, see the fetch page). Web builds cannot use sockets or `requests` (browser sandbox).

## Save data
- **What is saved:** current statement and call stack return points, shown images/screens, music, and store variables changed after init (all `default`ed vars) plus anything reachable from them (pickled).
- **Not saved:** `define`d constants (unless changed), config, styles, image definitions, control flow inside Python.
- **When:** auto at the start of each statement in the outermost context; quick save/auto save via config. APIs: `renpy.save(slot)`, `renpy.load(slot)`, `renpy.can_load`, `renpy.list_slots`, `renpy.newest_slot`, `renpy.unlink_save`, `renpy.slot_json`, `renpy.get_save_data()` (8.4).
- **Rollback control:** `renpy.block_rollback()`, `renpy.fix_rollback()`, `renpy.retain_after_load()`, `renpy.checkpoint()`, `config.rollback_enabled`, classes inheriting `NoRollback`.
- **Persistent:** `persistent.*` for cross-playthrough data (gallery unlocks, endings), saved on quit or `renpy.save_persistent()`, merged field-by-field (`renpy.register_persistent(field, func)`); `MultiPersistent("name")` shares across games.
- Saves may not be compatible across Ren'Py versions; 8.5 adds `config.before_load_callbacks` and a `before_load` label for migrations; `after_load` label for fix-ups.
- Locations: `game/saves` and a per-user directory (`%APPDATA%/RenPy/<save_directory>` on Windows); web saves are in browser storage (import/export via the web hamburger menu).

## Performance
Pre-size images to the game resolution, use `config.image_cache_size_mb` sensibly, avoid huge PNG sequences (use Movie/WebM or ATL), keep screens light (avoid heavy Python in screen expressions; precompute), use `nopredict` sparingly, `renpy.free_memory()` rarely. Lint (Launcher > Check Script) catches undefined images/labels. On web: no threads (no background image preload), files over 50 MB are not cached, OGG not on Safari.

## Build and export
Launcher > Build Distributions: PC (Windows+Linux), Mac, Linux, Windows, Markets (Steam/itch layout). Configure with `build.name`, `build.classify("game/**.psd", None)`, `build.archive("images", "all")`, `build.directory_name`, `build.itch_project` / `build.itch_channels` (dict since 8.2). Android: install JDK 21, Launcher > Android: Install SDK, Generate Keys, Configure, Build (Play Bundle AAB for Google Play, Universal APK for sideload/other stores; up to 2 GB; Android 5.0+; keep `android.keystore`/`bundle.keystore` private and backed up). iOS: renios + Xcode on a Mac. Web (Beta): Build Web Application / Build and Open in Browser; output in the project `-dists` folder, needs a web server; `progressive_download.txt` controls on-demand download. Automated testing framework (8.5): Launcher or `renpy.exe <project> test`.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| Points reset or wrong after loading a save | Variable created with `define` or `init python` | Use `default var = value` |
| Old game's values appear in a new game | State set in `init python` / module-level | `default` it so each new game starts fresh |
| `NameError` for a variable in a screen | Not defaulted, or only set later in script | `default` it at top level |
| `PicklingError` / "Could not pickle" on save | Lambda, generator, file or module object in store | Keep in locals / `python hide`; store plain data |
| Counter in a screen increments many times | Mutating state in screen code | Use `action IncrementVariable("x")` or `Function` |
| Loading a save lands on the wrong line or errors after an update | Label/statements changed, `.rpyc` deleted | Keep `.rpyc`, keep labels, add `after_load` migration |
| `SyntaxError: Missing parentheses in call to 'print'` | Python 2 code in Ren'Py 8 | Python 3 syntax |
| `screen x:` error "expects a block" | 8.5 requires a block | Add body or remove empty screen |
| Image "not found" | Name/attribute mismatch with file names in `images/` | Lowercase, space-separated names; `image` statement |
| Choice changes after rollback | Rollback allowed changing decisions | `renpy.fix_rollback()` after the menu |
| Web build silently no audio | Browser autoplay rules (needs a click) or OGG on Safari | Start audio after interaction; provide MP3/Opus variants |

## Mapping from Roblox
| Roblox | Ren'Py | Notes |
|---|---|---|
| Workspace / Instance tree | Layers with tagged images (`scene`, `show`, `hide`) | No 3D world |
| Part | Displayable (image, `Solid`, `Frame`) | |
| Model | `LayeredImage` / `Composite` | Character sprites with attributes |
| Script | `.rpy` labels (story flow) | Interpreted statement by statement |
| LocalScript | Same (single-player) | |
| ModuleScript | `init python` functions/classes, named stores (`init python in utils:`) | |
| RemoteEvent | Not applicable | No networking |
| DataStore | Save slots (`default` vars) + `persistent` | Local files |
| Players | Not applicable (single reader) | |
| Humanoid | `Character("Name")` object for dialogue | |
| RunService.Heartbeat | `timer 0.016 repeat True action ...` in a screen, or CDD `render` + `renpy.redraw` | Event-driven engine |
| RunService.RenderStepped | Creator-Defined Displayable `render()` | |
| TweenService | ATL (`ease 0.5 xalign 1.0`) | |
| CollectionService tags | Image tags and attributes | |
| Attributes | Store variables / object fields | |
| ScreenGui | Screen language (`screen`, `vbox`, `textbutton`) | |
| UserInputService | `key` statement, keymap, buttons | |
| task.wait | `pause 1.0` / `renpy.pause(1.0)` | |
| Studio playtest | Launcher > Launch Project, Shift+R reload | Lint for checks |
| Publishing | Launcher > Build Distributions / Android / Web | itch.io upload built in |

## Minimal example
A tiny choice game with a saved score, a HUD screen, a moving sprite and a "catch" minigame screen. Assumes images `bg park` and `eileen happy` exist in `game/images/`.
```renpy
define e = Character("Eileen")

default score = 0
default persistent.best_score = 0

transform hop:
    yoffset 0
    ease 0.25 yoffset -20
    ease 0.25 yoffset 0

screen hud():
    frame:
        xalign 0.98 yalign 0.02
        text "Score: [score]"

screen catch_star():
    modal True
    timer 3.0 action Return(False)
    imagebutton:
        idle Solid("#ffd700", xysize=(80, 80))
        xalign 0.7 yalign 0.4
        action Return(True)

label start:
    show screen hud
    scene bg park
    show eileen happy at center, hop
    e "Catch the star before it vanishes!"

    call screen catch_star
    if _return:
        $ score += 10
        e "Nice catch!"
    else:
        e "Too slow."

    menu:
        "Play again":
            jump start
        "Quit":
            pass

    if score > persistent.best_score:
        $ persistent.best_score = score
    e "Final score: [score]. Best ever: [persistent.best_score]."
    hide screen hud
    return
```

## Sources
- https://www.renpy.org/latest.html (latest release 8.5.3, 15 May 2026)
- https://www.renpy.org/release/8.5.3 (release name, platforms: SDK, RAPT, renios, renpyweb, Live2D 5.3)
- https://www.renpy.org/doc/html/changelog.html (8.3/8.4/8.5 features; Python 3.12 in 8.4; 8.5.4 entry in development docs)
- https://www.renpy.org/doc/html/incompatible.html (version-by-version incompatible changes and compat config variables)
- https://www.renpy.org/doc/html/python.html (define vs default, init python not saved, named stores, $ one-liners)
- https://www.renpy.org/doc/html/save_load_rollback.html (what is saved, unpicklable objects, rollback APIs, retain_after_load, ui.ChoiceReturn note)
- https://www.renpy.org/doc/html/persistent.html (persistent defaults, merging, MultiPersistent)
- https://www.renpy.org/doc/html/screens.html (screen syntax, show/call screen, Return, screen variables, side-effects warning)
- https://www.renpy.org/doc/html/transforms.html (ATL statements and examples)
- https://www.renpy.org/doc/html/android.html (RAPT steps, JDK 21, AAB vs APK, keystores)
- https://www.renpy.org/doc/html/web.html (Web Beta, limits, progressive download)

## Confidence and gaps
- High: define/default/persistent/save/rollback semantics, screen and ATL syntax, Android/web build steps, incompatible changes (all from official docs pages fetched today).
- Medium: `renpy.fetch()` and `config.image_cache_size_mb` confirmed only via the docs index; Windows save path from memory.
- Not verified: 8.5.4 release date (only appears in the development changelog); iOS build details.
