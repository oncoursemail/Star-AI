# LÖVE (love2d): STAR engine research
**Verified 2026-10-13 against official docs. Current stable: 11.5 "Mysterious Mysteries" (2023-12-03).** zlib license, free for any use; 12.0 "Bestest Friend" is still unreleased (nightly builds only).

## At a glance
| | |
|---|---|
| Best for | Small/medium 2D games, jams, prototypes, pixel-art games, programmers who want a framework not an editor |
| Weak at | No editor, no scene graph, no built-in UI/tweening/ECS/networking-replication, mobile/web export is manual, no 3D |
| Language(s) | Lua 5.1 via LuaJIT 2.1 (C/C++ engine) |
| Editor / tooling | None official. Any text editor (VS Code + Lua language server), `love` CLI to run a folder or `.love` file |
| Platforms (export) | Windows, macOS, Linux (official binaries); Android and iOS (build from source projects / LÖVE Loader); Web only via community ports (love.js, unofficial) |
| License / cost | zlib/libpng license, free, no royalties, closed-source games allowed |
| Roblox-likeness | low: no instance tree, no editor, no replication; you write the game loop callbacks and own all state in Lua tables |

## Architecture and lifecycle
- LÖVE is a framework: the runtime opens a window, loads `conf.lua` (optional) then `main.lua`, and calls global callback functions on the `love` table.
- Default `love.run` loop (11.x): `love.load(arg, unfilteredArg)` once -> each frame: pump events (dispatches `love.keypressed`, `love.mousepressed`, `love.resize`, `love.quit`, ...), `love.timer.step()` -> `love.update(dt)` -> `love.graphics.origin()`, `love.graphics.clear()`, `love.draw()`, `love.graphics.present()`.
- There is no fixed timestep by default; `dt` is variable. Implement an accumulator yourself if physics determinism matters.
- You can override `love.run` completely (custom loop) - it must return a function in 11.x (the main loop is a coroutine-like function returned from `love.run`).
- Modules: `love.graphics`, `love.audio`, `love.keyboard`, `love.mouse`, `love.joystick`, `love.touch`, `love.physics` (Box2D), `love.filesystem` (PhysFS), `love.timer`, `love.window`, `love.math`, `love.data`, `love.thread`, `love.event`, `love.system`, `love.image`, `love.sound`, `love.font`, `love.video`. Modules can be disabled in `conf.lua` (`t.modules.physics = false`).
- Error handling: `love.errorhandler(msg)` (11.x name; `love.errhand` is the deprecated 0.10 name) draws the blue error screen.
- State/scenes: no built-in scene system. Idiom: a table of state objects with `enter/update/draw` and a `current` variable, or a library (hump.gamestate, community).

## Project layout
```
mygame/
  conf.lua        -- optional, runs before modules load: function love.conf(t) ... end
  main.lua        -- required entry point with love.load/update/draw
  player.lua      -- modules via require("player") (dots, not slashes, as separators)
  assets/sprites/*.png
  assets/sfx/*.ogg
  lib/            -- vendored libraries (bump.lua, anim8, hump: community)
```
- Run: `love path/to/mygame` (folder containing main.lua) or `love mygame.love`.
- `conf.lua` sample (11.5):
```lua
function love.conf(t)
    t.identity = "mygame"          -- save directory name
    t.version = "11.5"             -- LÖVE version this game targets (warning if mismatched)
    t.console = false              -- Windows only: attach console
    t.window.title = "My Game"
    t.window.width = 800
    t.window.height = 600
    t.window.vsync = 1
    t.window.resizable = false
    t.modules.joystick = true
end
```
- Asset paths are relative to the game root (the folder or `.love` archive), always forward slashes, case-sensitive inside `.love` files and on Linux/macOS even if Windows lets it slide.

## Scripting idioms
- Keep state in locals/tables at file scope; avoid globals (they leak between modules). Return a table from each module.
```lua
-- player.lua
local Player = {}
Player.__index = Player

function Player.new(x, y)
    return setmetatable({ x = x, y = y, speed = 200, w = 32, h = 32 }, Player)
end

function Player:update(dt)
    local dx, dy = 0, 0
    if love.keyboard.isDown("left", "a") then dx = dx - 1 end
    if love.keyboard.isDown("right", "d") then dx = dx + 1 end
    if love.keyboard.isDown("up", "w") then dy = dy - 1 end
    if love.keyboard.isDown("down", "s") then dy = dy + 1 end
    self.x = self.x + dx * self.speed * dt
    self.y = self.y + dy * self.speed * dt
end

function Player:draw()
    love.graphics.setColor(0.2, 0.8, 1)       -- 0..1 since 11.0
    love.graphics.rectangle("fill", self.x, self.y, self.w, self.h)
    love.graphics.setColor(1, 1, 1)           -- reset, color state is global
end

return Player
```
- Polling vs events: `love.keyboard.isDown(key)` in `update` for held keys; `love.keypressed(key, scancode, isrepeat)` callback for one-shot presses.
- Load images/fonts/sounds once in `love.load`, never inside `love.draw` (creating objects per frame leaks GPU memory until GC).
- Use `love.graphics.push()`/`pop()` + `translate/scale` for cameras.
- Timers: no `task.wait`. Accumulate `dt` or use coroutines resumed from `update`.
```lua
local timers = {}
local function after(seconds, fn) timers[#timers+1] = { t = seconds, fn = fn } end
function love.update(dt)
    for i = #timers, 1, -1 do
        local tm = timers[i]
        tm.t = tm.t - dt
        if tm.t <= 0 then table.remove(timers, i); tm.fn() end
    end
end
```
- Pixel art: `love.graphics.setDefaultFilter("nearest", "nearest")` before loading images.
- Hot reload: not built in (community libs like lurker exist).

## Pitfalls (what AI answers get wrong)
1. **Color range is 0-1 since 11.0** (was 0-255 in 0.10.x and earlier). `love.graphics.setColor(255, 0, 0)` in 11.x clamps to white-ish/red full intensity and silently looks wrong for anything not 0/255. Use `setColor(1, 0, 0)`; convert bytes with `love.math.colorFromBytes(r, g, b, a)` (added 11.3). Same applies to `love.graphics.clear`, `setBackgroundColor`, ImageData `getPixel/setPixel`, shader colors.
```lua
-- WRONG (0.10 style)
love.graphics.setColor(255, 128, 0, 255)
-- RIGHT (11.x)
love.graphics.setColor(1, 0.5, 0, 1)
love.graphics.setColor(love.math.colorFromBytes(255, 128, 0))
```
2. **Filesystem query functions**: `love.filesystem.isFile`, `isDirectory`, `isSymlink`, `getLastModified`, `getSize` were deprecated in 11.0 and are **removed in 12.0**. Use `love.filesystem.getInfo(path [, filtertype])` which returns a table or nil. `love.filesystem.exists` was deprecated in 11 but is un-deprecated in 12.
3. **Writes only go to the save directory.** `love.filesystem.write("save.txt", data)` writes to `%APPDATA%/LOVE/<identity>` (Windows), `~/Library/Application Support/LOVE/<identity>` (macOS), `~/.local/share/love/<identity>` (Linux); fused games drop the `LOVE/` part. You cannot write into the game folder. Plain `io.open` works on desktop but bypasses this and breaks inside `.love` archives/mobile.
4. **Version-specific renames for 12.0 (not yet stable)**: `love.graphics.newText` -> `newTextBatch`; `love.graphics.stencil`/`setStencilTest` -> `setStencilMode`/`setStencilState`; `love.filesystem.newFile` -> `openFile`; `love.math.noise` -> `perlinNoise`/`simplexNoise`; `t.window.highdpi` -> `t.highdpi`; window `display` field -> `displayindex`; `love.graphics.getImageFormats`/`getCanvasFormats` -> `getTextureFormats`. Do not emit 12.0 names for an 11.5 project or vice versa; check `love.getVersion()` / `t.version`.
5. **Removed 11.0 APIs** that old tutorials use: `Shader:sendInt/sendFloat/sendTexture...` (use `Shader:send`), `love.graphics.newScreenshot` (use `love.graphics.captureScreenshot`), `love.window.isCreated` (use `isOpen`), shader entry `effects` (use `effect`).
6. **Physics list getters**: `World:getBodyList`, `Body:getFixtureList` etc. were deprecated in 11 and removed in 12; use `World:getBodies()`, `Body:getFixtures()`, `World:getContacts()`.
7. **Physics units**: Box2D works in meters; LÖVE scales by `love.physics.setMeter(px)` (default 30 px = 1 m). Call `setMeter` before creating the world. Do not destroy bodies inside `beginContact`/world callbacks - queue and destroy after `world:update(dt)`.
8. **`require` with slashes** (`require("lib/foo")`) is deprecated in 12.0; use dots `require("lib.foo")`.
9. **Global color/transform state**: `setColor`, `setFont`, `setLineWidth`, `setCanvas`, `setShader` persist until changed. Reset or `push("all")`/`pop()`.
10. **dt spikes**: when the window is dragged on Windows, `dt` can be huge; clamp (`dt = math.min(dt, 1/30)`) before physics.
11. `love.graphics.setMode` does not exist; it is `love.window.setMode` (moved in 0.9.0).
12. `love.load` gets `arg` as a parameter in 11.x; the global `arg` still exists but is the raw command line.

## Rendering
- Immediate-mode 2D: `love.graphics.draw(drawable, x, y, r, sx, sy, ox, oy)`, `rectangle`, `circle`, `line`, `polygon`, `print/printf`.
- Batching: `SpriteBatch` (via `love.graphics.newSpriteBatch(image, max)`), `Mesh`, `ParticleSystem`. LÖVE 11 auto-batches consecutive draws of the same texture.
- Off-screen: `love.graphics.newCanvas(w, h)` + `setCanvas(canvas)` / `setCanvas()`; useful for pixel-perfect scaling.
- Shaders: GLSL-like via `love.graphics.newShader(code)`, entry `vec4 effect(vec4 color, Image tex, vec2 texture_coords, vec2 screen_coords)`; uniforms via `shader:send(name, value)`.
- Quads for sprite sheets: `love.graphics.newQuad(x, y, w, h, sw, sh)`.
- HiDPI: in 11.x `t.window.highdpi = true` + `love.graphics.getDPIScale()`; 12.0 moves to `t.highdpi`.
- 12.0 (nightly) adds a new graphics backend layer (Vulkan/Metal), 3D-capable meshes/depth, `love.graphics.newTextBatch`, buffers - only use with nightly.

## Physics
- `love.physics` wraps Box2D (2.3 in 11.x; 12.0 updates to 2.4.1).
```lua
love.physics.setMeter(64)
world = love.physics.newWorld(0, 9.81 * 64, true)  -- gx, gy, allowSleep
local body = love.physics.newBody(world, 400, 100, "dynamic")
local shape = love.physics.newRectangleShape(32, 32)
local fixture = love.physics.newFixture(body, shape, 1)  -- density
fixture:setUserData("player")
world:setCallbacks(beginContact, endContact, preSolve, postSolve)
-- in love.update: world:update(dt)
```
- Body types: "static", "dynamic", "kinematic". Sensors: `fixture:setSensor(true)`.
- Many 2D games skip Box2D and use AABB checks or the community `bump.lua` library for tile collision.
- AABB helper:
```lua
local function overlaps(a, b)
    return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h
end
```

## Input
- Keyboard: `love.keyboard.isDown("space")`, `love.keypressed(key, scancode, isrepeat)`, `love.keyreleased`. Keys are strings ("left", "a", "space", "escape", "return").
- Text: `love.textinput(text)` + `love.keyboard.setKeyRepeat(true)`.
- Mouse: `love.mouse.getPosition()`, `love.mousepressed(x, y, button, istouch, presses)` (buttons 1=left, 2=right, 3=middle since 0.10).
- Touch: `love.touchpressed(id, x, y, dx, dy, pressure)`, `love.touch.getTouches()`.
- Gamepad: `love.joystick.getJoysticks()`, `joystick:isGamepadDown("a")`, `love.gamepadpressed(joystick, button)`, `joystick:getGamepadAxis("leftx")`.

## UI
- No built-in UI widgets. Draw with `love.graphics.print/printf` and rectangles, or use community libraries (SUIT, Slab, nuklear bindings - all unofficial).
- Fonts: `love.graphics.newFont("font.ttf", size)` then `setFont`. Use `printf(text, x, y, limit, align)` for wrapping.
- HUD over a camera: draw world inside `push/translate/pop`, then HUD after `pop`.

## Networking and multiplayer
- Bundled: `lua-enet` (`require "enet"`) for UDP reliable/unreliable channels and LuaSocket (`require "socket"`, `socket.http`).
- 12.0 adds `love.data`/https improvements and an `https` module (12.0 changelog; not in 11.5).
- No replication or authority model: you serialize state yourself (e.g., with `love.data.pack` or a JSON lib). Run blocking network code in `love.thread` threads with `Channel`s.

## Save data
```lua
local SAVE = "save.lua"
local function saveScore(n)
    local ok, err = love.filesystem.write(SAVE, "return " .. tostring(n))
    if not ok then print("save failed: " .. tostring(err)) end
end
local function loadScore()
    if love.filesystem.getInfo(SAVE) then
        local chunk = love.filesystem.load(SAVE)
        return chunk()
    end
    return 0
end
```
- Set `t.identity` in `conf.lua` (or `love.filesystem.setIdentity`) so the folder is stable. `love.filesystem.getSaveDirectory()` shows the path.
- Executing a saved Lua chunk is convenient but unsafe if users share saves; prefer a JSON/serializer lib (community) for untrusted data.

## Performance
- LuaJIT is fast but allocation-heavy code still triggers GC stalls: reuse tables, avoid creating closures/tables per frame.
- Batch draws: same texture + SpriteBatch; minimize `setCanvas`/`setShader` switches. `love.graphics.getStats()` gives draw calls, texture memory.
- Never create `Image`/`Font`/`Canvas` in `love.draw`.
- JIT is disabled by default on macOS arm64 in 11.5 (changelog) - CPU-heavy code may be slower there.
- Profile with `love.timer.getTime()` deltas or community profilers.

## Build and export
- `.love` file: zip the contents of the game folder (main.lua at zip root, not inside a subfolder), rename to `.love`.
- Fused Windows exe: `copy /b love.exe+game.love game.exe`, ship alongside LÖVE DLLs and license.txt. macOS: put `game.love` into `love.app/Contents/Resources/` and edit Info.plist. Linux: AppImage (official wiki instructions).
- Android: love-android project (Gradle) or LÖVE Loader app for testing; iOS: Xcode project from the source distribution.
- Web: not official (love.js community port).
- Community tooling (unofficial): makelove, love-release, boon.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| Everything drawn white / colors wrong | 0-255 color values in 11.x | Use 0-1 floats or `love.math.colorFromBytes` |
| `attempt to call field 'isFile' (a nil value)` on 12.0 nightly | Removed API | `love.filesystem.getInfo(path, "file")` |
| Save file not found next to game | Writes go to save dir | Check `love.filesystem.getSaveDirectory()` |
| "No code to run" screen | `main.lua` not at archive root | Zip the folder contents, not the folder |
| Blurry pixel art | Linear filtering | `love.graphics.setDefaultFilter("nearest", "nearest")` before loading |
| Crash/assert in physics callback | Destroying body inside contact callback | Queue removals, destroy after `world:update` |
| Objects tunnel through walls after window drag | Huge `dt` | Clamp `dt`, or fixed-step accumulator |
| Memory grows every frame | `newImage`/`newFont` in `love.draw` | Create once in `love.load` |
| Text in other color after HUD | Color state persisted | `setColor(1,1,1)` after drawing |
| Module not found | `require` path with slashes or `.lua` extension | `require("folder.module")` |

## Mapping from Roblox
| Roblox | LÖVE | Notes |
|---|---|---|
| Workspace / Instance tree | Your own Lua tables (entities list) | No scene graph; you iterate and draw |
| Part | Table with x,y,w,h drawn with `love.graphics.rectangle` | Physics part -> `love.physics` body+shape+fixture |
| Model | Table of child tables | Manual transform via push/translate |
| Script / LocalScript | `main.lua` callbacks | Single process, no client/server split |
| ModuleScript | Lua module returned by `require("name")` | Same Lua idiom, but Lua 5.1 not Luau (no types, no `continue`) |
| RemoteEvent | lua-enet packets | Hand-rolled protocol |
| DataStore | `love.filesystem.write/read` in save dir | Local only |
| Players | Not applicable | You define a player table |
| Humanoid | Not applicable | Write your own controller |
| RunService.Heartbeat | `love.update(dt)` | Variable dt |
| RunService.RenderStepped | `love.draw()` | Draw only, no logic ideally |
| TweenService | No built-in support | Lerp manually or community tween libs (flux, tween.lua) |
| CollectionService tags | Fields on tables / separate lists | e.g. `entity.tags.enemy = true` |
| Attributes | Plain table fields | |
| ScreenGui | Draw after camera `pop()` | No widgets |
| UserInputService | `love.keyboard`, `love.mouse`, `love.joystick`, callbacks | |
| task.wait | dt accumulators or coroutines | No scheduler |
| Studio playtest | `love .` from terminal | |
| Publishing | `.love` / fused exe / platform builds | Manual packaging |

## Minimal example
```lua
-- main.lua (LÖVE 11.5)
local player = { x = 100, y = 100, w = 32, h = 32, speed = 220 }
local coin = { x = 400, y = 300, w = 16, h = 16 }
local score = 0
local font

local function overlaps(a, b)
    return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h
end

local function respawnCoin()
    coin.x = love.math.random(0, love.graphics.getWidth() - coin.w)
    coin.y = love.math.random(0, love.graphics.getHeight() - coin.h)
end

function love.load()
    font = love.graphics.newFont(20)
    if love.filesystem.getInfo("best.txt") then
        print("best: " .. love.filesystem.read("best.txt"))
    end
end

function love.update(dt)
    dt = math.min(dt, 1 / 30)
    local dx, dy = 0, 0
    if love.keyboard.isDown("left", "a") then dx = dx - 1 end
    if love.keyboard.isDown("right", "d") then dx = dx + 1 end
    if love.keyboard.isDown("up", "w") then dy = dy - 1 end
    if love.keyboard.isDown("down", "s") then dy = dy + 1 end
    player.x = player.x + dx * player.speed * dt
    player.y = player.y + dy * player.speed * dt
    if overlaps(player, coin) then
        score = score + 1
        respawnCoin()
    end
end

function love.keypressed(key)
    if key == "escape" then love.event.quit() end
end

function love.quit()
    love.filesystem.write("best.txt", tostring(score))
end

function love.draw()
    love.graphics.setColor(1, 0.85, 0)
    love.graphics.rectangle("fill", coin.x, coin.y, coin.w, coin.h)
    love.graphics.setColor(0.2, 0.7, 1)
    love.graphics.rectangle("fill", player.x, player.y, player.w, player.h)
    love.graphics.setColor(1, 1, 1)
    love.graphics.setFont(font)
    love.graphics.print("Score: " .. score, 10, 10)
end
```

## Sources
- https://github.com/love2d/love/releases (11.5 marked Latest, 2023-12-03; no 12.0 release; also confirmed via GitHub API releases/latest = 11.5 on 2026-10-13)
- https://raw.githubusercontent.com/love2d/love/11.5/changes.txt (11.0 0-1 color change, 11.0 deprecations/removals, colorFromBytes in 11.3, 11.5 notes)
- https://raw.githubusercontent.com/love2d/love/main/changes.txt (12.0 section: release date N/A, removals, deprecations, renames, Box2D 2.4.1)
- https://raw.githubusercontent.com/love2d/love/11.5/src/modules/love/boot.lua (conf defaults: identity, version, window fields, setIdentity)
- https://love2d.org/wiki/12.0 (12.0 "Bestest Friend" not released; page returned 403 to the fetcher, status confirmed via search snippet)
- https://www.love2d.org/forums/viewtopic.php?p=262394 (dev comment on 12.0 timeline, nightly builds via GitHub Actions; forum, community-level)

## Confidence and gaps
- High: 11.5 is current stable; 0-1 colors; filesystem getInfo; 12.0 rename list (from main-branch changes.txt, which can still change before release).
- Medium: save-directory paths per OS and fused-game behavior (from memory of wiki; love2d.org wiki blocked the fetcher with 403 this session).
- Not verified this session: exact love.js/web status, Android/iOS packaging steps, community library names (marked community).
