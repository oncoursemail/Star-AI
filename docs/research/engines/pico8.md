# PICO-8 and fantasy consoles (PICO-8, Picotron, TIC-80): STAR engine research
**Verified 2026-10-13 against official docs. Current stable: PICO-8 0.2.7 (2025-08-16); Picotron 0.3.0d2 (beta, 0.3.0 line since 2026-03-14); TIC-80 1.3.1 (2026-10-05).** PICO-8 is commercial ($14.99, Lexaloffle); Picotron is commercial ($19.99); TIC-80 is MIT open source (free; paid PRO build on itch.io or build with `-DBUILD_PRO=On`).

## At a glance
| | |
|---|---|
| Best for | Tiny retro games, game jams, learning, demos; PICO-8 is the most-used fantasy console (itch.io "made with PICO-8" listing shows ~10,100 games on 2026-10-13) |
| Weak at | Anything big: hard size limits, 128x128 (PICO-8) or 240x136 (TIC-80) screens, 16 colours, 4 sound channels, no networking |
| Language(s) | PICO-8: P8 Lua (Lua 5.2 subset with shorthands, z8lua). Picotron: Lua 5.4 with PICO-8 shorthands. TIC-80: Lua 5.4 plus MoonScript, JavaScript, Wren, Fennel, Squirrel, Ruby, Janet, Scheme, Python, YueScript, MiniScript, Forth |
| Editor / tooling | All-in-one built-in editors (code, sprite, map, sfx, music) plus console/shell; external editor via `#include` (PICO-8) |
| Platforms (export) | PICO-8: .p8/.p8.png carts, HTML/JS/WASM, Windows/macOS/Linux/Raspberry Pi binaries. Picotron: .p64/.p64.png, HTML, binaries. TIC-80: .tic carts, HTML, native (PRO for some export options) |
| License / cost | PICO-8 paid; Picotron paid; TIC-80 MIT |
| Roblox-likeness | low: single-player, single-file, fixed-function; only the "create and share inside a platform" culture (Lexaloffle BBS, Splore) is similar |

## Architecture and lifecycle
**PICO-8** (manual v0.2.7):
- Specs: 128x128 display, fixed 16-colour palette (+16 secret colours via `pal`), 6-button controllers for up to 8 players, 32k cart encoded as PNG, 4 channels / 64 SFX, code limit **8192 tokens**, 4M VM instructions/sec, 128 8x8 sprites (+128 shared with map), 128x32 map (+128x32 shared).
- Callbacks: `_init()` once at start; `_update()` at 30 fps **or** `_update60()` at 60 fps (define one, not both); `_draw()` per visible frame. If a frame overruns, PICO-8 drops to 15/30 fps and calls update twice per draw.
- Without callbacks the program runs top to bottom once; custom loops need `flip()`.
- Memory map: base RAM addresses (`peek`/`poke`/`memcpy`), persistent cart data at `0x5e00..0x5eff` once `cartdata()` is called.
- Token rule: each word/operator/number counts as a token; a bracket pair and a string count as 1; commas, periods, `local`, semicolons, `end` and comments are free. Additional limits: a character count limit (shown in the editor) and, for .p8.png/.rom, compressed code under 15360 bytes (not enforced for .p8).

**Picotron** (manual v0.3.0d):
- 480x270 display (also 240x135 via `vid(3)`, 160x90 via `vid(4)`), 64 definable colours, Lua 5.4, a full windowed desktop OS (programs are processes; `create_process`).
- Same callback names: `_init()`, `_update()` (always 60 fps), `_draw()`. No `_update60`.
- Files: working cart is `/ram/cart`, entry `main.lua`; data via `store(path, obj)` / `fetch(path)` (PODs). `/appdata/<yourgame>` persists, also in exports. Carts: `.p64` (folder-like, unlimited) and `.p64.png` (256k).

**TIC-80** (wiki, 1.3.x):
- 240x136 display, 16 colours from a 24-bit space, 256 8x8 foreground sprites + 256 background tiles, 240x136-cell map, 4 sound channels, 64 SFX, 8 music tracks, up to 272 KB RAM.
- Callbacks: `TIC()` is mandatory and runs at 60 fps (update **and** draw); `BOOT()` once at start (1.0+); `BDR(scanline)` between scanlines (0.90+); `MENU(index)` for the game menu. `SCN` and `OVR` are deprecated.
- The first lines are cart metadata comments: `-- title:`, `-- author:`, `-- script: lua`, `-- saveid:`, `-- input: gamepad`.

## Project layout
PICO-8 `.p8` text cart:
```
pico-8 cartridge // http://www.pico-8.com
version 42
__lua__
-- code (tabs separated by -->8)
__gfx__
...sprite sheet hex...
__gff__   (sprite flags)
__map__
__sfx__
__music__
```
- `.p8.png` is the shareable image format (size limited), `.p8.rom` raw 32k. External code: `#include game.lua` (resolved at run, flattened when saving .p8.png/exporting; not recursive).
- Picotron: a cart is a folder (`main.lua`, `gfx/0.gfx`, `map/0.map`, `sfx/0.sfx`), `include("file.lua")` for more code.
- TIC-80: single `.tic` cart (or text `.lua` with data sections for PRO); banks (up to 8) in PRO.

## Scripting idioms
PICO-8:
```lua
function _init()
  p={x=60,y=60,spd=1}
  cartdata("star_demo_v1")      -- once, before dget/dset
  best=dget(0)
end

function _update60()
  if btn(0) then p.x-=p.spd end  -- 0 left 1 right 2 up 3 down 4 O(z) 5 X(x)
  if btn(1) then p.x+=p.spd end
  if btnp(4) then sfx(0) end     -- btnp: just pressed (auto-repeats)
  p.x=mid(0,p.x,120)            -- clamp
end

function _draw()
  cls(1)
  map(0,0,0,0,16,16)
  spr(1,p.x,p.y)                -- spr(n,x,y,[w,h],[flip_x],[flip_y])
  print("best "..best,2,2,7)
end
```
- Shorthands: `if (cond) stmt` single-line if, `+=`, `-=`, `..=`, `!=` alias of `~=`, `\` integer division (`9\2` = 4), `?` as print in the console, `@addr`/`%addr`/`$addr` peek forms.
- Tables: `add(t,v,[i])`, `del(t,v)`, `deli(t,[i])`, `count(t,[v])`, `all(t)` iterator, `foreach(t,f)`. 1-based.
- Map collision: `fget(mget(flr(x/8),flr(y/8)),0)` with sprite flag 0 meaning "solid".
- Coroutines: `cocreate`, `coresume`, `costatus`, `yield` (good for cutscenes and `task.wait`-like sequences).
- Strings: `sub(s,i,j)`, `split(s,[sep],[convert])`, `tostr`, `tonum`, `chr`, `ord`.

TIC-80 equivalent:
```lua
-- title: demo
-- script: lua
-- saveid: star_demo
x,y=96,24
function TIC()
  if btn(0) then y=y-1 end  -- 0 up 1 down 2 left 3 right 4 A 5 B 6 X 7 Y
  if btn(1) then y=y+1 end
  if btn(2) then x=x-1 end
  if btn(3) then x=x+1 end
  cls(13)
  spr(1,x,y,14,3)            -- spr(id,x,y,colorkey,scale,flip,rotate,w,h)
  print("HELLO",84,84)
end
```

Picotron:
```lua
function _init() x=240 y=135 end
function _update()
  if (btn(0)) x-=2
  if (btn(1)) x+=2
end
function _draw()
  cls(1)
  circfill(x,y,8,12)
end
```

## Pitfalls (what AI answers get wrong)
1. **Button indices differ**: PICO-8 and Picotron use 0 left, 1 right, 2 up, 3 down, 4 O, 5 X. TIC-80 uses 0 up, 1 down, 2 left, 3 right, 4 A, 5 B, 6 X, 7 Y (ids up to 31 for 4 players). Mixing them breaks movement.
2. **`_update` vs `_update60`**: define only one. `_update60` gives 60 fps with half the CPU per frame. `btnp` state resets at the start of each update call, so call it from the update callback, not `_draw`.
3. **Numbers are 16:16 fixed point in PICO-8**: range -32768.0 to 32767.99999, step 0x0.0001. A frame counter incremented by 1 overflows after about 18 minutes at 30 fps; `time()` also wraps eventually. Big scores need two numbers or string tricks. Picotron and TIC-80 use normal Lua numbers (no such limit).
4. **Trig is in turns, and `sin` is inverted** in PICO-8 (and Picotron, for compatibility): `cos(0.25)` is 0, `sin(0.25)` is -1. `atan2(dx,dy)` returns 0..1. Answers using `math.sin`, `math.pi` or radians are wrong; there is no `math` library.
5. **No standard Lua library** in PICO-8: no `string.format`, `table.insert`, `math.floor`, `pairs` with metatables beyond the basics, `require`, `io`, `os`. Use `flr`, `ceil`, `add`, `del`, `sub`, `tostr`, `#include` (boot-time only). `pairs`, `ipairs`, `setmetatable` do exist.
6. **`sgn(0)` returns 1** in PICO-8.
7. **Sprite sheet bottom half (sprites 128-255) and map rows 32-63 share memory**. Drawing in both corrupts the other.
8. **`cartdata(id)` can be called once per run**, before `dget/dset`; only 64 numbers (256 bytes), indices 0..63; ids are a..z, 0..9, underscore, up to 64 chars. TIC-80 `pmem(index,[val])` has 256 32-bit unsigned slots and is tied to the code hash unless `-- saveid:` metadata is set (editing code otherwise wipes saves).
9. **Token limit 8192** is the real constraint: compact code (shared helper functions, tables of data parsed with `split`) beats verbose OOP. Long variable names do not cost tokens; extra operators and literals do.
10. **`rnd(x)` returns a float in [0,x)**; use `flr(rnd(n))` for integers; `rnd(tbl)` returns a random element (0.2.0+).
11. **Lua arrays are 1-based**: `foreach` starts at index 1; `spr` numbers and map cells are 0-based.
12. **TIC-80 `spr` colorkey defaults to -1 (opaque)**; pass `0` (or the background index) for transparency. PICO-8 treats colour 0 as transparent by default (`palt` changes it).
13. **Picotron is not PICO-8 at higher resolution**: sprites are userdata (`get_spr`/`set_spr`), maps are `i16` userdata loaded with `fetch`, 16 audio channels, colours 0..63. Some PICO-8 memory addresses and P8SCII control codes differ.

## Rendering
- PICO-8: immediate-mode, redraw the whole frame in `_draw`. `cls`, `pset`, `pget`, `line`, `rect`, `rectfill`, `circ`, `circfill`, `oval`, `ovalfill`, `rrect`/`rrectfill` (0.2.7), `spr`, `sspr(sx,sy,sw,sh,dx,dy,[dw,dh],[flip_x],[flip_y])`, `map(tile_x,tile_y,[sx,sy],[tile_w,tile_h],[layers])`, `tline` (textured lines for mode-7/rotation), `fillp` (fill patterns), `pal`/`palt` (palette swap and transparency), `camera(x,y)` to scroll, `clip`.
- TIC-80: `cls`, `spr`, `map(x,y,w,h,sx,sy,colorkey,scale,remap)` with a per-tile `remap` callback, `tri`/`textri`/`ttri` for 3D-ish effects, `vbank` (1.0+) for two screen layers, palette changes in `BDR` for more colours.
- Picotron: same names plus batch userdata drawing, `tline3d`, windows (`window{...}`), and `vid` modes.

## Physics
No built-in physics in any of the three. Use AABB tests, tile flags (`fget`) and hand-written velocity/gravity. Typical pattern: move one axis at a time, test the 4 corners of the hitbox against solid tiles, undo the move on collision.

## Input
- PICO-8: `btn([b],[pl])`, `btnp(b,[pl])` (repeat after 15 frames then every 4 at 30 fps; custom delays via `poke(0x5f5c,delay)`/`poke(0x5f5d,delay)`). Mouse/keyboard via devkit mode `poke(0x5f2d,1)` (experimental), then `stat(32)`/`stat(33)` mouse x/y, `stat(34)` buttons, `stat(36)` wheel, `stat(30)` key available, `stat(31)` key char.
- TIC-80: `btn(id)`, `btnp(id,[hold],[period])`, `key(code)`, `keyp(code)`, `mouse()`.
- Picotron: `btn(b,[pl])`, `btnp`, `key("a")`, `keyp`, `mouse()`.

## UI
No widget system. Text with `print(str,x,y,col)` (PICO-8 P8SCII control codes for wide/tall/outlined text, 0.2.7 adds outline and underline escapes), rectangles for panels, `menuitem(index,[label],[callback])` to add to the pause menu (up to 5 items).

## Networking and multiplayer
Not applicable for gameplay. Local multiplayer only (PICO-8 up to 8 players). PICO-8 web exports can talk to JavaScript through GPIO pins (`0x5f80..0x5fff`) as a hack; `serial()` exists for files/streams on desktop. Picotron's `fetch` can read URLs (for BBS carts), not a multiplayer API.

## Save data
- PICO-8: `cartdata("unique_id")` then `dset(i,v)` / `dget(i)` for i in 0..63; persists across sessions and in web exports (browser storage). Returns true if data existed.
- TIC-80: `pmem(i)` read / `pmem(i,v)` write, 256 x 32-bit unsigned; set `-- saveid:` to survive code edits.
- Picotron: `store("/appdata/mygame/save.pod", tbl)` and `fetch(...)`.

## Performance
- PICO-8 CPU: virtual 8 MHz, about 2 cycles per Lua VM instruction; built-in draws cost CPU too. Watch `stat(1)` (fraction of frame used; >1 means slowdown) or CTRL-P meter. Big `map()` calls are cheaper than many `spr` calls; avoid per-pixel `pset` loops.
- Token budget usually binds before CPU.
- TIC-80/Picotron: much higher budgets; still single-threaded Lua.

## Build and export
- PICO-8 (inside the console or headless with `pico8 cart.p8 -export "..."`): `export game.html` (+ .js), `export -w game.html` (WASM, must be served by a web server), `export game.bin` (Windows/macOS/Linux/RPi zips), `export game.p8.png`, multicart exports up to 32 carts (0.2.7). `save game.p8.png` needs compressed code < 15360 bytes.
- Picotron: `export foo.p64.png`, `export foo.html`, `export foo.bin`.
- TIC-80: `export html game`, `export win game` etc. from the console (some targets and `alone=1` need PRO; 1.3.1 fixed the PRO `alone=1` export).
- Sharing: Lexaloffle BBS (PICO-8/Picotron, also loadable in Splore), tic80.com, itch.io.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| Player moves at double speed or half speed | Mixed `_update` and `_update60` assumptions | Use one callback; scale speeds to its rate |
| `btnp` never fires | Called in `_draw` or in custom loop | Call in `_update`/`_update60` |
| Score jumps negative | 16:16 overflow above 32767 | Store as two numbers or use `tostr(x,2)` style unsigned tricks |
| Rotation goes the wrong way | PICO-8 `sin` inverted, angles in turns | Use `cos(a)`, `-sin(a)` with a in 0..1 |
| `attempt to call nil value (field 'floor')` | Using Lua std `math.floor` | `flr()` |
| Map tiles appear as garbage sprites | Drawing into shared sprite/map memory | Use sprites 0..127 only or map rows 0..31 only |
| Saved high score lost | `dset` before `cartdata`, or TIC-80 code edit changed hash | Call `cartdata` first; TIC-80: add `-- saveid:` |
| "Token limit exceeded" | Over 8192 tokens | Merge similar functions, data-in-strings with `split`, remove debug code |
| Sprite has black box (TIC-80) | Default colorkey -1 | `spr(id,x,y,0)` |
| WASM export blank page | Opened from file:// | Serve via a local web server or use default JS export |

## Mapping from Roblox
| Roblox | PICO-8 / TIC-80 | Notes |
|---|---|---|
| Workspace / Instance tree | Plain Lua tables you iterate each frame | No scene graph |
| Part | A table `{x,y,w,h}` drawn with `rectfill`/`spr` | |
| Model | Table of tables | |
| Script / LocalScript | The single cart program (`_init/_update/_draw` or `TIC`) | Everything is local |
| ModuleScript | Code tabs, `#include file.lua` (PICO-8), `include()` (Picotron) | Boot-time only in PICO-8 |
| RemoteEvent | Not applicable | No networking |
| DataStore | `cartdata`/`dget`/`dset`; `pmem`; `store`/`fetch` | Tiny local storage |
| Players | Local player index 0..7 (`btn(b,pl)`) | |
| Humanoid | Not applicable | Write movement yourself |
| RunService.Heartbeat / RenderStepped | `_update60` / `_draw`; `TIC()` | Fixed frame rate |
| TweenService | Manual lerp per frame, or coroutines | |
| CollectionService tags | Sprite flags (`fget`/`fset`) or tables per type | |
| Attributes | Table fields | |
| ScreenGui | `print`/`rectfill` drawn after `camera()` reset | |
| UserInputService | `btn`/`btnp`, `key` (TIC-80/Picotron) | |
| task.wait | `yield()` inside a `cocreate` coroutine resumed each update | |
| Studio playtest | CTRL-R / `run` | |
| Publishing | `export` to HTML/binary; upload to BBS or itch.io | |

## Minimal example
PICO-8 0.2.7: move with arrows, collect a coin, keep a best score in cartdata.
```lua
-- star coin demo (pico-8 0.2.7)
function _init()
  cartdata("star_coin_demo")
  best=dget(0)
  p={x=60,y=60}
  score=0
  new_coin()
end

function new_coin()
  c={x=flr(rnd(120)),y=8+flr(rnd(112))}
end

function hit(a,b)
  return abs(a.x-b.x)<6 and abs(a.y-b.y)<6
end

function _update60()
  if (btn(0)) p.x-=1
  if (btn(1)) p.x+=1
  if (btn(2)) p.y-=1
  if (btn(3)) p.y+=1
  p.x=mid(0,p.x,120)
  p.y=mid(8,p.y,120)
  if hit(p,c) then
    score+=1
    sfx(0)
    new_coin()
    if score>best then
      best=score
      dset(0,best)
    end
  end
end

function _draw()
  cls(1)
  rectfill(p.x,p.y,p.x+7,p.y+7,12)
  circfill(c.x+3,c.y+3,3,10)
  print("score "..score.."  best "..best,2,1,7)
end
```

## Sources
- https://www.lexaloffle.com/dl/docs/pico-8_manual.html (v0.2.7 manual: specs, 8192 tokens, callbacks, `_update60`, 16:16 numbers, quirks, cartdata/dget/dset, btn/btnp indices and repeat, spr/sspr/map/mget/mset/fget/fset/sfx/music signatures, export options, compressed-size limit 15360)
- https://lexaloffle.itch.io/pico-8/devlog/1010793/pico-8-027 (0.2.7 devlog: rrect/rrectfill, outline text, splore, 32-cart multicart)
- https://en.wikipedia.org/wiki/PICO-8 (0.2.7 date 16 August 2025, community source)
- https://www.lexaloffle.com/dl/docs/picotron_manual.html (Picotron v0.3.0d: 480x270, Lua 5.4, callbacks, store/fetch, /appdata, .p64, vid modes, userdata, export)
- https://www.lexaloffle.com/picotron.php (v0.3.0d2, beta status, $19.99; PICO-8 price $14.99)
- https://github.com/nesbox/TIC-80/wiki (specs, languages, callbacks, PRO)
- https://github.com/nesbox/TIC-80/wiki/spr, /map, /pmem, /btn, /btnp, /TIC, /BOOT, /BDR, /sfx, /music, /print, /cls, /key (exact signatures)
- https://github.com/nesbox/TIC-80/releases (v1.2.0 2026-09-16, v1.3.0 2026-10-04, v1.3.1 2026-10-05)
- https://itch.io/games/made-with-pico-8 (10,146 listings on 2026-10-13)

## Confidence and gaps
- High: PICO-8 API and limits (read from the 0.2.7 manual text), TIC-80 signatures (wiki pages), version dates for TIC-80 (GitHub API).
- Medium: PICO-8 0.2.7 release date (Wikipedia + itch devlog title); Picotron 0.3.0 date (Wikipedia, community); Picotron btn index meaning (manual summary).
- Not verified: TIC-80 export command syntax per platform, which TIC-80 exports require PRO in 1.3.x.
