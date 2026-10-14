---
name: engine-solar2d
description: Solar2D 2026.x (ex-Corona SDK, Lua): display objects, Composer scenes, Box2D physics, transitions, Runtime events. Use for Solar2D or Corona SDK game code questions.
---
# engine-solar2d
## Scope
Solar2D daily/public builds 2026.37xx (latest 2026.3736, 2026-10-12). Check the project's build number first (Simulator Help > About, or `system.getInfo("build")`). Corona SDK answers older than 2014 are usually wrong.

## Core model
- `main.lua` runs once; no update callback. You register listeners: `Runtime:addEventListener("enterFrame", fn)` and per-object `touch`, `tap`, `collision`.
- Display objects (`display.newRect`, `newImageRect`, `newText`, `newSprite`) live in groups (`display.newGroup`) under the stage.
- Composer scenes: `composer.newScene()` with `create`, `show`/`hide` (phases "will"/"did"), `destroy`; switch with `composer.gotoScene`.
- Fixed fps from `config.lua`; content scaling via `content = { width, height, scale = "letterbox" }`.

## Idioms
- Create objects inside a scene with the scene group as parent: `display.newRect(sceneGroup, x, y, w, h)`.
- Colors 0-1: `obj:setFillColor(1, 0.5, 0)`; anchors `obj.anchorX = 0` (0..1, default 0.5).
- Tween: `transition.to(obj, { time = 400, x = 200, transition = easing.outQuad, onComplete = fn })`.
- Delay: `timer.performWithDelay(500, fn)`; cancel with `timer.cancel(handle)`.
- Physics: `local physics = require("physics"); physics.start()` then `physics.addBody(obj, "dynamic", { density = 1, bounce = 0.2 })`.
- Local collision: `obj.collision = function(self, event) ... end; obj:addEventListener("collision")`, check `event.phase == "began"` and `event.other`.
- Remove with `display.remove(obj); obj = nil`.
- Save JSON with `system.pathForFile("save.json", system.DocumentsDirectory)` + `io.open` + `json.encode`.

## Pitfalls
1. Storyboard (`require("storyboard")`, `createScene`/`enterScene`) is removed; use Composer.
2. `setReferencePoint` and `display.TopLeftReferencePoint` are Graphics 1.0 and gone; use `anchorX`/`anchorY`.
3. Colors are 0-1, not 0-255.
4. Never add/remove bodies or change body position inside a collision event; defer with `timer.performWithDelay(1, fn)`.
5. Call `physics.start()` before `physics.addBody`; pause physics when the scene hides.
6. Remove Runtime listeners and cancel timers/transitions in `scene:hide` ("will") or they keep running in the next scene.
7. Objects not inserted into `self.view` survive scene changes.
8. You cannot write to `system.ResourceDirectory`; use `system.DocumentsDirectory`.
9. Global collision events: `event.object1`/`object2` are unordered; check both.
10. Physics polygon `shape` must be convex, clockwise, max 8 vertices; use `outline` for concave.
11. Old `sprite` library is gone; use `graphics.newImageSheet` + `display.newSprite`.

## Roblox to Solar2D
- Workspace/Instance tree -> stage and display groups
- Part -> `display.newRect` + `physics.addBody`
- Model -> `display.newGroup()`
- Script/LocalScript -> `main.lua` and Composer scene modules; ModuleScript -> `require`
- RunService.Heartbeat/RenderStepped -> `enterFrame` Runtime event
- TweenService -> `transition.to` + `easing`
- UserInputService -> `touch`, `tap`, `key` events
- DataStore -> JSON file in `system.DocumentsDirectory`
- RemoteEvent -> `network.request` or socket plugins (no replication)
- ScreenGui -> top display group or `widget` library
- task.wait -> `timer.performWithDelay`
- Studio playtest -> Solar2D Simulator; shipping -> File > Build per platform

## Skeleton
```lua
-- main.lua
local physics = require("physics")
physics.start()
physics.setGravity(0, 0)

local score = 0
local label = display.newText({ text = "Score: 0", x = 80, y = 30, fontSize = 20 })

local player = display.newRect(160, 240, 32, 32)
player:setFillColor(0.2, 0.7, 1)
physics.addBody(player, "dynamic", { isSensor = true })

local coin = display.newCircle(60, 120, 10)
physics.addBody(coin, "static", { radius = 10, isSensor = true })
coin.name = "coin"

local function moveCoin()
    coin.x, coin.y = math.random(20, 300), math.random(60, 460)
end

function player:collision(event)
    if event.phase == "began" and event.other.name == "coin" then
        score = score + 1
        label.text = "Score: " .. score
        timer.performWithDelay(1, moveCoin)
    end
end
player:addEventListener("collision")

local function onTouch(event)
    transition.to(player, { time = 300, x = event.x, y = event.y })
    return true
end
Runtime:addEventListener("tap", onTouch)
```

## Verification
Open the folder in the Solar2D Simulator and watch its console (it relaunches on save). If no Simulator run happened, say the code is unverified.
