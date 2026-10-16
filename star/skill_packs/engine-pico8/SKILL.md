---
name: engine-pico8
description: PICO-8 0.2.7 (plus Picotron 0.3 and TIC-80 1.3) fantasy console Lua idioms, limits and traps. Use for PICO-8, Picotron or TIC-80 carts.
---
# engine-pico8
## Scope
PICO-8 0.2.7 (P8 Lua), Picotron 0.3.0 beta (Lua 5.4), TIC-80 1.3.1 (Lua and other languages). Check the project's version first: the `version` line in a .p8 file, the Picotron version, or TIC-80 cart metadata.

## Core model
- PICO-8: 128x128, 16 colours, 8192-token code limit, 32k cart. Callbacks `_init()`, `_update()` (30 fps) or `_update60()` (60 fps), `_draw()`.
- Numbers are 16:16 fixed point: -32768 to 32767.99999.
- Picotron: 480x270, Lua 5.4, `_init/_update/_draw` at 60 fps, files via `store`/`fetch`.
- TIC-80: 240x136, one mandatory `TIC()` at 60 fps for update and draw, `BOOT()` for setup, metadata comments at the top.
- Immediate mode: clear and redraw everything each frame. No physics, no networking.

## Idioms
- PICO-8 input: `btn(b,[pl])` held, `btnp(b,[pl])` just pressed; b 0 left 1 right 2 up 3 down 4 O 5 X.
- Draw: `cls(c)`, `spr(n,x,y,[w,h],[fx],[fy])`, `map(tx,ty,[sx,sy],[tw,th])`, `rectfill`, `circfill`, `print(s,x,y,c)`.
- Tile collision: `fget(mget(flr(x/8),flr(y/8)),0)` with flag 0 = solid.
- Clamp with `mid(lo,v,hi)`; random int `flr(rnd(n))`; tables with `add`, `del`, `all`, `foreach`.
- Shorthands: `if (c) stmt`, `+=`, `!=`, `\` integer divide.
- Scroll with `camera(x,y)`, reset with `camera()` before HUD.
- Save: `cartdata("unique_id")` once, then `dset(i,v)` / `dget(i)` for i 0..63.
- Sequences: `cocreate`, `coresume`, `yield` as a wait.
- TIC-80: `spr(id,x,y,colorkey,scale,flip,rotate,w,h)`, `map(x,y,w,h,sx,sy,colorkey,scale,remap)`, `pmem(i,[v])`.

## Pitfalls
1. Define either `_update` or `_update60`, not both; speeds differ by 2x between them.
2. Call `btnp` in the update callback; its state resets at the start of each update.
3. Fixed-point overflow: values above 32767 wrap negative; a +1 per frame counter overflows in minutes.
4. Trig uses turns (0..1) and `sin` is inverted; there is no `math` library (`math.sin`, `math.floor` do not exist). Use `flr`, `ceil`, `sin`, `cos`, `atan2`.
5. No standard library: no `string.format`, `table.insert`, `require`, `io`, `os`. Use `sub`, `tostr`, `tonum`, `split`, `add`, `#include` (boot-time only).
6. `sgn(0)` is 1. Lua tables are 1-based; sprite numbers and map cells are 0-based.
7. Sprites 128-255 and map rows 32-63 share memory; using both corrupts graphics.
8. `cartdata` can be called once per run and must come before `dget/dset`; only 64 numbers.
9. TIC-80 buttons differ: 0 up 1 down 2 left 3 right 4 A 5 B 6 X 7 Y.
10. TIC-80 `spr` colorkey defaults to -1 (opaque); pass 0 for transparency. `pmem` saves are lost when code changes unless `-- saveid:` is set.
11. Picotron is not PICO-8 with more pixels: sprites and maps are userdata (`get_spr`, `fetch`), 64 colours, `_update` always 60 fps, no `_update60`.
12. .p8.png saves need compressed code under 15360 bytes; the 8192-token limit is usually hit first.

## Roblox to PICO-8
- Workspace/Instance tree -> plain Lua tables iterated every frame
- Part -> table {x,y,w,h} drawn with `rectfill` or `spr`
- Script/LocalScript -> the single cart program
- ModuleScript -> code tabs or `#include file.lua`
- RunService.Heartbeat -> `_update60()`; RenderStepped -> `_draw()`
- UserInputService -> `btn`/`btnp`
- DataStore -> `cartdata`/`dget`/`dset`
- CollectionService tags -> sprite flags (`fget`) or per-type tables
- TweenService -> manual lerp each frame
- task.wait -> `yield()` inside a coroutine resumed each update
- ScreenGui -> `print`/`rectfill` after `camera()`
- RemoteEvent, Players, Humanoid -> not available
- Studio playtest -> CTRL-R; shipping -> `export game.html` or `export game.bin`

## Skeleton
```lua
function _init()
  cartdata("star_demo_v1")
  best=dget(0)
  p={x=60,y=60}
  score=0
end

function _update60()
  if (btn(0)) p.x-=1
  if (btn(1)) p.x+=1
  if (btn(2)) p.y-=1
  if (btn(3)) p.y+=1
  p.x=mid(0,p.x,120)
  p.y=mid(0,p.y,120)
  if btnp(4) then
    score+=1
    sfx(0)
    if score>best then best=score dset(0,best) end
  end
end

function _draw()
  cls(1)
  rectfill(p.x,p.y,p.x+7,p.y+7,12)
  print("score "..score.." best "..best,2,2,7)
end
```

## Verification
Paste into the PICO-8 code editor or save as a .p8 file, then `load` and `run` (CTRL-R). Check the token counter in the code editor's bottom right and `stat(1)` for CPU. For headless conversion, use `pico8 game.p8 -export game.html`. Do not claim it ran unless you saw it run.
