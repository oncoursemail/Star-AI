---
name: engine-love2d
description: LÖVE (love2d) 11.5 Lua 2D framework (12.0 still unreleased): callbacks, 0-1 colors, love.filesystem saves, love.physics. Use for any LÖVE/love2d game code question.
---
# engine-love2d
## Scope
LÖVE 11.5 (stable since 2023-12-03); 12.0 "Bestest Friend" exists only as nightly builds. Check the project's version first (`t.version` in conf.lua or `love.getVersion()`) before choosing 11.x or 12.0 names.

## Core model
- Framework, not editor: `main.lua` defines callbacks on the `love` table; optional `conf.lua` with `love.conf(t)` runs first.
- Loop: `love.load()` once, then each frame events -> `love.update(dt)` -> `love.draw()`. Variable dt, no fixed step.
- No scene graph: your game state is Lua tables you update and draw yourself.
- Lua 5.1 via LuaJIT; modules with `require("folder.module")`.

## Idioms
- Load images/fonts/sounds once in `love.load`; never create them in `love.draw`.
- Held keys: `love.keyboard.isDown("left", "a")`; one-shot: `love.keypressed(key, scancode, isrepeat)`.
- Colors 0-1: `love.graphics.setColor(1, 0.5, 0)`; bytes via `love.math.colorFromBytes(255, 128, 0)`.
- Reset global state after drawing (`setColor(1, 1, 1)`), or `love.graphics.push("all")` / `pop()`.
- Camera: `push()`, `translate(-camX, -camY)`, draw world, `pop()`, then HUD.
- Saves: `love.filesystem.write(name, data)` / `read(name)`, existence via `love.filesystem.getInfo(name)`; set `t.identity`.
- Physics: `love.physics.setMeter(64)` before `newWorld`; body + shape + fixture; `world:update(dt)`.
- Pixel art: `love.graphics.setDefaultFilter("nearest", "nearest")` before loading images.

## Pitfalls
1. Colors are 0-1 since 11.0; `setColor(255, 0, 0)` is the 0.10 style and renders wrong.
2. `love.filesystem.isFile/isDirectory/getSize/getLastModified` deprecated in 11, removed in 12: use `getInfo`.
3. Writes only go to the save directory; you cannot write into the game folder or a `.love` archive.
4. 12.0 renames (nightly only): `newText` -> `newTextBatch`, `stencil`/`setStencilTest` -> `setStencilMode`, `newFile` -> `openFile`, `love.math.noise` -> `perlinNoise`/`simplexNoise`, window `display` -> `displayindex`. Do not mix with 11.5.
5. 11.0 removed `Shader:sendFloat/sendInt/...` (use `Shader:send`), `newScreenshot` (use `captureScreenshot`), `love.window.isCreated` (use `isOpen`).
6. `World:getBodyList` / `Body:getFixtureList` style getters are deprecated; use `getBodies` / `getFixtures`.
7. Never destroy bodies inside physics callbacks; queue and destroy after `world:update`.
8. `love.graphics.setMode` does not exist; it is `love.window.setMode`.
9. `require("lib/foo")` with slashes is deprecated in 12; use dots.
10. Error handler is `love.errorhandler` (11.x), not `love.errhand`.
11. No built-in UI, tween or scene manager; libraries for those are community.

## Roblox to LÖVE
- Workspace/Instance tree -> your own entity tables
- Part -> table drawn with `love.graphics.rectangle` (+ optional love.physics body)
- Script/LocalScript -> `main.lua` callbacks; ModuleScript -> `require` module
- RunService.Heartbeat -> `love.update(dt)`; RenderStepped -> `love.draw()`
- UserInputService -> `love.keyboard`, `love.mouse`, `love.keypressed`
- DataStore -> `love.filesystem` save directory (local only)
- RemoteEvent -> lua-enet packets you design
- TweenService -> manual lerp; task.wait -> dt accumulator or coroutine
- ScreenGui -> draw HUD after camera `pop()`
- Studio playtest -> run `love .`; shipping -> `.love` zip or fused exe

## Skeleton
```lua
-- main.lua (LÖVE 11.5)
local player = { x = 100, y = 100, w = 32, h = 32, speed = 200 }
local score = 0

function love.load()
    if love.filesystem.getInfo("best.txt") then
        print("best " .. love.filesystem.read("best.txt"))
    end
end

function love.update(dt)
    dt = math.min(dt, 1 / 30)
    local dx, dy = 0, 0
    if love.keyboard.isDown("left") then dx = dx - 1 end
    if love.keyboard.isDown("right") then dx = dx + 1 end
    if love.keyboard.isDown("up") then dy = dy - 1 end
    if love.keyboard.isDown("down") then dy = dy + 1 end
    player.x = player.x + dx * player.speed * dt
    player.y = player.y + dy * player.speed * dt
end

function love.quit()
    love.filesystem.write("best.txt", tostring(score))
end

function love.draw()
    love.graphics.setColor(0.2, 0.7, 1)
    love.graphics.rectangle("fill", player.x, player.y, player.w, player.h)
    love.graphics.setColor(1, 1, 1)
    love.graphics.print("Score: " .. score, 10, 10)
end
```

## Verification
Run `love .` in the folder with main.lua (or `love game.love`) and watch the console for errors; `love --version` shows the installed version. Without that run, say the code is untested.
