# Solar2D (ex-Corona SDK): STAR engine research
**Verified 2026-10-13 against official docs. Current stable: 2026.3736 (2026-10-12).** Free, open source (MIT), no fees or royalties.

## At a glance
| | |
|---|---|
| Best for | 2D mobile games and apps (casual, puzzle, arcade), fast iteration in the Simulator, simple physics games |
| Weak at | 3D (none), large desktop/console games, cutting-edge rendering; ecosystem is smaller and older than in its Corona days |
| Language(s) | Lua 5.1 (scripts); native C/C++/Obj-C/Java via Solar2D Native |
| Editor / tooling | No scene editor. Solar2D Simulator (live reload) + any text editor; Live Builds to devices |
| Platforms (export) | iOS, tvOS, Android, Android TV, macOS, Windows, Linux, HTML5 (per solar2d.com) |
| License / cost | MIT, completely free, no tracking |
| Roblox-likeness | low-medium: there is a display-object hierarchy (groups) and event listeners similar to signals, but no editor, no server, no replication |

## Architecture and lifecycle
- Entry point `main.lua` runs once at launch. There is no explicit game loop callback: you register listeners.
- **Display objects** (`display.newRect`, `newCircle`, `newImageRect`, `newText`, `newSprite`, `newGroup`) live in a scene graph rooted at the stage. Groups (`display.newGroup()`) nest objects; `group:insert(obj)`.
- **Events**: Runtime events (`enterFrame`, `key`, `system`, `resize`, `orientation`, global `collision`) via `Runtime:addEventListener("enterFrame", fn)`; object events (`touch`, `tap`, `collision`, `finalize`) via `obj:addEventListener("touch", fn)`. Remove with `removeEventListener`.
- Frame rate is fixed per app in `config.lua` (`fps = 30` default or `60`). `enterFrame` event gives `event.time` (ms since start); compute dt yourself.
- **Composer** library is the scene manager: `composer.gotoScene("game", { effect = "fade", time = 400 })`, scenes have `create`, `show` (phases "will"/"did"), `hide` ("will"/"did"), `destroy`. Overlays: `composer.showOverlay`.
- Libraries are globals or `require`d: `display`, `transition`, `timer`, `physics` (`require("physics")`), `composer` (`require("composer")`), `widget` (`require("widget")`), `audio`, `media`, `network`, `system`, `json` (`require("json")`), `native`, `graphics`.

## Project layout
```
MyGame/
  main.lua          -- entry point
  config.lua        -- content area (width/height/scale), fps, imageSuffix
  build.settings    -- orientation, plugins, iOS/Android settings, excludeFiles
  scenes/menu.lua   -- composer scenes: composer.gotoScene("scenes.menu")
  scenes/game.lua
  images/...  audio/...  fonts/...
  Icon*.png, LaunchScreen etc.
```
- `config.lua`:
```lua
application = {
    content = {
        width = 320,
        height = 480,
        scale = "letterbox",
        fps = 60,
    },
}
```
- Content coordinates: `display.contentWidth/Height`, `display.contentCenterX/Y`, `display.safeScreenOriginX`, `display.actualContentWidth`.
- Module paths in `require` and `composer.gotoScene` use dots.

## Scripting idioms
- Objects are Lua tables with display properties: `obj.x`, `obj.y`, `obj.rotation`, `obj.alpha`, `obj.xScale`, `obj.isVisible`, `obj.anchorX/anchorY` (0..1, default 0.5).
- Custom fields on display objects are fine (`enemy.hp = 3`).
- Listener styles: function listener `obj:addEventListener("touch", onTouch)` or table listener (`obj.touch = function(self, event) ... end; obj:addEventListener("touch")`).
- Return `true` from touch/tap handlers to stop propagation to objects underneath.
- Touch dragging with focus:
```lua
local function onDrag(event)
    local t = event.target
    if event.phase == "began" then
        display.getCurrentStage():setFocus(t)
        t.isFocus = true
        t.x0, t.y0 = event.x - t.x, event.y - t.y
    elseif t.isFocus then
        if event.phase == "moved" then
            t.x, t.y = event.x - t.x0, event.y - t.y0
        elseif event.phase == "ended" or event.phase == "cancelled" then
            display.getCurrentStage():setFocus(nil)
            t.isFocus = false
        end
    end
    return true
end
box:addEventListener("touch", onDrag)
```
- Tweens: `transition.to(obj, { time = 500, x = 200, alpha = 0.5, transition = easing.outQuad, onComplete = fn })`; `transition.cancel(handle or tag)`; `transition.pause/resume`.
- Delays: `timer.performWithDelay(ms, fn, iterations)`; cancel with `timer.cancel(handle)`.
- Remove objects with `display.remove(obj)` (nil-safe) or `obj:removeSelf()`, then `obj = nil` to release the Lua reference.
- Composer scene file template:
```lua
local composer = require("composer")
local scene = composer.newScene()

function scene:create(event)
    local sceneGroup = self.view
    local bg = display.newRect(sceneGroup, display.contentCenterX, display.contentCenterY,
        display.actualContentWidth, display.actualContentHeight)
    bg:setFillColor(0.1, 0.1, 0.2)
end

function scene:show(event)
    if event.phase == "did" then
        -- start timers, physics, Runtime listeners
    end
end

function scene:hide(event)
    if event.phase == "will" then
        -- stop timers, remove Runtime listeners
    end
end

function scene:destroy(event) end

scene:addEventListener("create", scene)
scene:addEventListener("show", scene)
scene:addEventListener("hide", scene)
scene:addEventListener("destroy", scene)
return scene
```

## Pitfalls (what AI answers get wrong)
1. **Storyboard is gone; use Composer.** `require("storyboard")`, `storyboard.gotoScene`, `scene:createScene`/`enterScene` are the pre-2014 Corona API; the storyboard docs no longer exist. Use `composer.newScene()` and `create/show/hide/destroy`.
2. **Graphics 2.0 (2013) removed reference points.** `obj:setReferencePoint(display.TopLeftReferencePoint)` no longer exists; use `obj.anchorX = 0; obj.anchorY = 0`. Default anchor is 0.5 (center) for objects; groups are anchored at their origin unless `anchorChildren = true`.
3. **Colors are 0-1** since Graphics 2.0: `obj:setFillColor(1, 0, 0)`, not `(255, 0, 0)`.
4. **Never modify physics bodies inside a collision event** (`physics.addBody`, `physics.removeBody`, changing `x/y`, `bodyType`, joints): Box2D can crash. Defer with `timer.performWithDelay(1, fn)` or a flag. `display.remove()` of the object is allowed in the same step.
5. **Physics must be started first**: `local physics = require("physics"); physics.start()` before `physics.addBody`. Pause on scene hide (`physics.pause()`).
6. **Runtime listeners and timers leak across scenes**: anything added to `Runtime` or started in a scene must be removed/cancelled in `hide` "will" or `destroy`, otherwise the next scene still runs them and errors on removed objects (`attempt to index a nil value`).
7. **Objects not inserted into `sceneGroup`** are not removed when Composer removes the scene and stay on screen. Pass the group as first arg (`display.newRect(sceneGroup, ...)`) or `sceneGroup:insert(obj)`.
8. **Writing files**: you cannot write to `system.ResourceDirectory`; use `system.pathForFile("save.json", system.DocumentsDirectory)`.
9. **Global collision events**: `event.object1`/`event.object2` are not ordered; check both. Local collisions use `self` and `event.other`.
10. **`display.newImage` vs `newImageRect`**: use `newImageRect(parent, "img.png", w, h)` so dynamic image suffixes (@2x/@4x from `config.lua imageSuffix`) work.
11. Old Corona-era services (Corona Cloud, Corona Labs build servers, account login, `Runtime:hideErrorAlerts` era advice) are obsolete; Solar2D builds locally without an account. Old `sprite` library (`require("sprite")`) was replaced by `display.newSprite` + `graphics.newImageSheet`.
12. **Shape polygons for physics** must be convex, max 8 vertices, clockwise; use `outline = graphics.newOutline(...)` for concave images.

## Rendering
- Retained-mode display list; draw order = insertion order within a group; `obj:toFront()`/`toBack()`.
- Images: `display.newImageRect`, sprite sheets: `graphics.newImageSheet(file, options)` + `display.newSprite(sheet, sequenceData)` + `sprite:play()`.
- Fills/strokes: `setFillColor`, `setStrokeColor`, `strokeWidth`; gradient fills and paint tables (`obj.fill = { type = "image", filename = "..." }`).
- Effects: `obj.fill.effect = "filter.blur"` (shader effects), custom effects via `graphics.defineEffect`.
- Snapshots (`display.newSnapshot`) and containers (`display.newContainer`) for clipping.
- Text: `display.newText({ text = "Score", x = 10, y = 10, font = native.systemFont, fontSize = 20 })`, bitmap fonts via community libs.

## Physics
- Box2D integration:
```lua
local physics = require("physics")
physics.start()
physics.setGravity(0, 9.8)
physics.addBody(ground, "static", { friction = 0.5, bounce = 0.1 })
physics.addBody(ball, "dynamic", { density = 1.0, radius = 16, bounce = 0.3 })
physics.addBody(coin, "static", { isSensor = true, radius = 10 })
-- physics.setDrawMode("hybrid")  -- debug overlay
```
- Body types: "static", "dynamic", "kinematic"; shapes via `radius`, `box = { halfWidth, halfHeight }`, `shape` (convex vertices), `chain`, `outline`. Filters: `filter = { categoryBits = 1, maskBits = 6 }`.
- Velocity/forces: `obj:setLinearVelocity(vx, vy)`, `obj:applyLinearImpulse(ix, iy, obj.x, obj.y)`, `obj:applyForce`. `obj.isFixedRotation = true` for characters.
- Events: `collision` (phases "began"/"ended"), `preCollision`, `postCollision`. Raycast: `physics.rayCast(x1, y1, x2, y2, "closest")`.
- Scale: `physics.setScale(30)` px per meter (default 30).

## Input
- Touch/mouse: `touch` (phases "began", "moved", "ended", "cancelled") and `tap` (`event.numTaps`). Multitouch: `system.activate("multitouch")`.
- Keyboard/gamepad: `Runtime:addEventListener("key", onKey)`, `event.keyName` ("left", "space", "buttonA"), `event.phase` ("down"/"up"). Return `true` to override default behaviour (e.g. Android back key).
- Mouse (desktop): `Runtime:addEventListener("mouse", fn)`.
- Axis (gamepads): `axis` event; device info via `system.getInputDevices()`.
- Accelerometer: `accelerometer` Runtime event.

## UI
- `widget` library: `widget.newButton`, `newSlider`, `newScrollView`, `newTableView`, `newSwitch`, `newTabBar`. Many games just use display objects + touch.
- Native UI: `native.newTextField`, `native.showAlert`, `native.newWebView` (rendered above OpenGL content, cannot be inside groups visually).
- Layout: anchor to `display.safeScreenOriginX/Y` and `display.safeActualContentWidth/Height` for notches.

## Networking and multiplayer
- `network.request(url, "GET"|"POST", listener, params)` (async, listener gets `event.isError`, `event.response`), `network.download`.
- LuaSocket (`require("socket")`) for TCP/UDP. WebSockets/Photon/Nakama via plugins (third-party).
- No built-in multiplayer or replication.

## Save data
```lua
local json = require("json")
local function save(t)
    local path = system.pathForFile("save.json", system.DocumentsDirectory)
    local f, err = io.open(path, "w")
    if not f then print("save error: " .. tostring(err)); return end
    f:write(json.encode(t))
    io.close(f)
end
local function load()
    local path = system.pathForFile("save.json", system.DocumentsDirectory)
    local f = io.open(path, "r")
    if not f then return { best = 0 } end
    local t = json.decode(f:read("*a"))
    io.close(f)
    return t or { best = 0 }
end
```
- Other dirs: `system.TemporaryDirectory`, `system.CachesDirectory`, `system.ApplicationSupportDirectory`. SQLite via `require("sqlite3")`.

## Performance
- Use image sheets (one texture) and avoid many separate textures; keep display object counts reasonable; remove off-screen objects.
- Cancel timers/transitions and remove listeners on scene exit to avoid leaks and CPU waste.
- Prefer `local` references to frequently used globals (`local mRand = math.random`).
- Texture memory: `system.getInfo("textureMemoryUsed")`; Lua memory: `collectgarbage("count")`.
- `fps = 60` doubles work vs 30; pick per game.

## Build and export
- Simulator: File > Open project (main.lua folder); auto-relaunch on file save.
- File > Build > iOS / Android / macOS / Windows / Linux / HTML5 / tvOS. Builds happen locally (Xcode needed for Apple targets on macOS; Android builds need no Android Studio for basic builds, Java required).
- `build.settings` configures orientation, plugins (`plugins = { ["plugin.xyz"] = { publisherId = "..." } }`), Android permissions, iOS plist keys, `excludeFiles`.
- Live Builds: install a live build on device; code/assets update over the local network.
- Recent releases (2026.3732-3736, Oct 2026) are mostly Android fixes (edge-to-edge opt-in, nav bar build fix); check release notes when targeting new Android SDKs.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| `attempt to call field 'setReferencePoint'` | Graphics 1.0 code | Use `anchorX/anchorY` |
| `module 'storyboard' not found` | Removed library | Rewrite with Composer |
| Crash or "physics.addBody cannot be called" during collision | Modifying world inside collision | `timer.performWithDelay(1, fn)` |
| Objects remain after scene change | Not in `sceneGroup` | Insert into `self.view` |
| Errors after leaving a scene | Runtime listener/timer still active | Remove in `hide`/`destroy` |
| White objects instead of colors | 0-255 values | Use 0-1 |
| Save file not written | Writing to ResourceDirectory | Use `system.DocumentsDirectory` |
| Touch fires on objects behind | Handler doesn't return true | `return true` |
| Blurry/wrong-size images on devices | `newImage` without imageSuffix | `newImageRect` + `imageSuffix` in config |
| Physics bodies offset from images | Wrong anchor/shape | Check `physics.setDrawMode("hybrid")` |

## Mapping from Roblox
| Roblox | Solar2D | Notes |
|---|---|---|
| Workspace / Instance tree | Stage + display groups | `display.getCurrentStage()` |
| Part | `display.newRect` + `physics.addBody` | 2D only |
| Model | `display.newGroup()` | |
| Script / LocalScript | `main.lua` + scene modules | Client only |
| ModuleScript | `require("folder.module")` | Lua 5.1 |
| RemoteEvent | `network.request` / sockets / plugins | No replication |
| DataStore | `io` + `json` in `system.DocumentsDirectory` | Local |
| Players | Not applicable | |
| Humanoid | Not applicable | Write controller with physics or manual movement |
| RunService.Heartbeat | `Runtime:addEventListener("enterFrame", fn)` | Fixed fps from config |
| RunService.RenderStepped | `enterFrame` | Same event |
| TweenService | `transition.to` + `easing.*` | |
| CollectionService tags | Custom fields, groups, physics filters | |
| Attributes | Custom fields on display objects | |
| ScreenGui | A top display group / widget library | |
| UserInputService | `touch`, `tap`, `key`, `mouse`, `axis` events | |
| task.wait | `timer.performWithDelay` | |
| Studio playtest | Solar2D Simulator | Auto relaunch |
| Publishing | File > Build per platform | Store upload yourself |

## Minimal example
```lua
-- main.lua (Solar2D 2026.x)
local physics = require("physics")
physics.start()
physics.setGravity(0, 0)

local score = 0
local scoreText = display.newText({ text = "Score: 0", x = 70, y = 30, fontSize = 20 })

local player = display.newRect(display.contentCenterX, display.contentCenterY, 32, 32)
player:setFillColor(0.2, 0.7, 1)
physics.addBody(player, "dynamic", { isSensor = true })
player.isFixedRotation = true
player.name = "player"

local coin = display.newCircle(60, 120, 10)
coin:setFillColor(1, 0.85, 0)
physics.addBody(coin, "static", { radius = 10, isSensor = true })
coin.name = "coin"

local keys = {}
local function onKey(event)
    keys[event.keyName] = (event.phase == "down")
    return false
end
Runtime:addEventListener("key", onKey)

local speed = 200
local last = system.getTimer()
local function onFrame(event)
    local dt = (event.time - last) / 1000
    last = event.time
    local dx, dy = 0, 0
    if keys["left"] then dx = dx - 1 end
    if keys["right"] then dx = dx + 1 end
    if keys["up"] then dy = dy - 1 end
    if keys["down"] then dy = dy + 1 end
    player.x = player.x + dx * speed * dt
    player.y = player.y + dy * speed * dt
end
Runtime:addEventListener("enterFrame", onFrame)

local function moveCoin()
    coin.x = math.random(20, display.contentWidth - 20)
    coin.y = math.random(60, display.contentHeight - 20)
end

local function onCollision(self, event)
    if event.phase == "began" and event.other.name == "coin" then
        score = score + 1
        scoreText.text = "Score: " .. score
        timer.performWithDelay(1, moveCoin)   -- never move bodies inside the collision event
    end
end
player.collision = onCollision
player:addEventListener("collision")
```

## Sources
- https://github.com/coronalabs/corona/releases (2026.3736 on 2026-10-12, earlier 2026.37xx builds and notes; confirmed by GitHub API releases/latest = 3736)
- https://solar2d.com/ (platforms list, MIT license, free, no tracking, Live Builds, Solar2D Native)
- https://docs.coronalabs.com/api/library/composer/index.html (composer functions, scene events/phases, template)
- https://docs.coronalabs.com/guide/physics/physicsSetup/index.html (physics.start, setGravity defaults)
- https://docs.coronalabs.com/api/library/physics/addBody.html (addBody signature, params, body types, shape limits)
- https://docs.coronalabs.com/guide/physics/collisionDetection/index.html (local/global collision listeners, do not modify bodies inside collisions)
- https://docs.coronalabs.com/api/library/transition/to.html (transition.to params; docs revision 2026.3728)
- https://docs.coronalabs.com/api/type/DisplayObject/anchorX.html (anchors 0..1, default 0.5)
- https://docs.coronalabs.com/guide/data/readWriteFiles/index.html (system.pathForFile + DocumentsDirectory, cannot write ResourceDirectory)
- https://docs.coronalabs.com/api/library/storyboard/index.html and .../DisplayObject/setReferencePoint.html (both return 404: legacy APIs no longer documented)

## Confidence and gaps
- High: version/date, composer, physics, collision rules, anchors, file I/O.
- Medium: Simulator menu wording, build prerequisites per platform, `system.activate("multitouch")`, axis/mouse event details (from long-standing docs, not re-fetched).
- Not verified this session: HTML5 export maturity, current plugin directory state, Linux build target details.
