# raylib: STAR engine research
**Verified 2026-10-13 against official docs. Current stable: raylib 6.0 (2026-04-23).** zlib/libpng license, free; raygui 5.0 is the companion immediate-mode GUI (same license). raylib 6.2 is in development (changelog dated "xx Oct 2026", not released as of this check).

## At a glance
| | |
|---|---|
| Best for | Learning, game jams, small 2D/3D games and tools in plain C (or via bindings); single-file style programs; web builds via Emscripten |
| Weak at | Large projects (no scene system, ECS, editor, asset pipeline), physics, networking, advanced rendering; you manage all memory/resources by hand |
| Language(s) | C99 core (C++ compatible); 70+ community bindings (C#, Python, Rust, Go, Zig, Odin, Nim, Lua...) |
| Editor / tooling | None; any C toolchain. Ships Makefile, CMake, build.zig, and project templates. Small official tools (rGuiLayout, rTexPacker etc.) are separate |
| Platforms (export) | Windows, Linux, macOS, Web (Emscripten/WebAssembly), Android, Raspberry Pi / DRM, FreeBSD; 6.0 adds a software renderer backend (rlsw) and experimental Win32 and Emscripten native backends |
| License / cost | zlib/libpng, free |
| Roblox-likeness | low: a library of functions, not an engine with a world tree, multiplayer or cloud services |

## Architecture and lifecycle
- Modules: `rcore` (window, input, timing, files; filesystem API moved here in 6.0, `utils` module removed), `rlgl` (OpenGL 1.1/2.1/3.3/4.3/ES2/ES3 abstraction + software renderer), `rshapes`, `rtextures`, `rtext`, `rmodels`, `raudio` (miniaudio). Header-only add-ons: `raymath.h`, `rcamera.h`, `rlgl.h`; `raygui.h` lives in a separate repo.
- One process, one window, immediate-mode drawing:
```c
InitWindow(w, h, "title");    // creates window + GL context: load GPU resources AFTER this
SetTargetFPS(60);
while (!WindowShouldClose()) {  // ESC or close button by default (SetExitKey(KEY_NULL) to disable ESC)
    float dt = GetFrameTime();  // update
    BeginDrawing();
        ClearBackground(RAYWHITE);
        // BeginMode2D(cam) / BeginMode3D(cam3d) ... End...
    EndDrawing();               // swaps buffers, polls input, waits for target FPS
}
CloseWindow();
```
- Input state is polled inside `EndDrawing()`; query it with `IsKeyPressed`/`IsKeyDown` during the next frame.
- No entities, no scene graph: you keep your own structs/arrays.
- Config flags must be set **before** `InitWindow`: `SetConfigFlags(FLAG_WINDOW_RESIZABLE | FLAG_VSYNC_HINT | FLAG_MSAA_4X_HINT | FLAG_WINDOW_HIGHDPI)`.

## Project layout
```
mygame/
  src/main.c
  resources/          # textures, fonts, sounds (paths relative to the working directory!)
  CMakeLists.txt      # or Makefile / build.zig; fetch raylib via CMake FetchContent or a prebuilt release
```
- Typical CMake: `FetchContent_Declare(raylib GIT_REPOSITORY https://github.com/raysan5/raylib.git GIT_TAG 6.0)` then `target_link_libraries(game raylib)`.
- Windows quick start: the official raylib installer bundles w64devkit (MinGW) + Notepad++ preset.
- Use `ChangeDirectory(GetApplicationDirectory())` at start so relative resource paths work when launched from elsewhere.

## Scripting idioms
```c
#include "raylib.h"
#include "raymath.h"

typedef struct { Vector2 pos; float speed; } Player;

Vector2 dir = { 0 };
if (IsKeyDown(KEY_RIGHT)) dir.x += 1;
if (IsKeyDown(KEY_LEFT))  dir.x -= 1;
p.pos = Vector2Add(p.pos, Vector2Scale(Vector2Normalize(dir), p.speed * GetFrameTime()));

Rectangle a = { p.pos.x, p.pos.y, 32, 32 };       // Rectangle fields are float
if (CheckCollisionRecs(a, coinRec)) score++;
DrawText(TextFormat("Score: %i", score), 10, 10, 20, DARKGRAY);   // TextFormat uses a static rotating buffer
```
- 2D camera: `Camera2D cam = { .offset = {w/2.0f, h/2.0f}, .target = p.pos, .rotation = 0, .zoom = 1 };` then `BeginMode2D(cam); ... EndMode2D();`; `GetScreenToWorld2D(GetMousePosition(), cam)` for mouse picking.
- 3D: `Camera3D cam = { .position={10,10,10}, .target={0}, .up={0,1,0}, .fovy=45, .projection=CAMERA_PERSPECTIVE };` `UpdateCamera(&cam, CAMERA_ORBITAL);` `BeginMode3D(cam); DrawCube(...); DrawGrid(10, 1.0f); EndMode3D();`
- Colors: predefined `RAYWHITE`, `DARKGRAY`, `RED`..., or `(Color){ r, g, b, a }` (0-255). `Fade(c, 0.5f)` / `ColorAlpha(c, 0.5f)`.
- Resource pairs: every `LoadX` has `UnloadX` (`LoadTexture`/`UnloadTexture`, `LoadSound`/`UnloadSound`, `LoadFont`/`UnloadFont`, `LoadModel`/`UnloadModel`, `LoadFileData`/`UnloadFileData`).
- Audio: `InitAudioDevice()` first; `Sound s = LoadSound("hit.wav"); PlaySound(s);`; overlapping copies via `LoadSoundAlias(s)`; streaming `Music m = LoadMusicStream("bgm.ogg"); PlayMusicStream(m);` and call `UpdateMusicStream(m)` **every frame**.
- raygui (single header, define implementation in exactly one .c):
```c
#define RAYGUI_IMPLEMENTATION
#include "raygui.h"
if (GuiButton((Rectangle){ 20, 60, 120, 30 }, "Restart")) Reset();   // returns int (1 = pressed) since 4.0
GuiSlider((Rectangle){ 20, 100, 200, 20 }, "Vol", NULL, &volume, 0.0f, 1.0f); // value by pointer since 4.0
```

- Web-friendly frame function (works on desktop too):
```c
#if defined(PLATFORM_WEB)
    #include <emscripten/emscripten.h>
#endif

static void UpdateDrawFrame(void) { /* update + BeginDrawing()...EndDrawing() */ }

int main(void)
{
    InitWindow(800, 450, "game");
#if defined(PLATFORM_WEB)
    emscripten_set_main_loop(UpdateDrawFrame, 0, 1);   // browser drives the frames; no ASYNCIFY needed
#else
    SetTargetFPS(60);
    while (!WindowShouldClose()) UpdateDrawFrame();
#endif
    CloseWindow();
    return 0;
}
```
- Bindings (community-maintained, listed in raylib's BINDINGS.md; versions lag the C release, check which raylib version a binding wraps): Raylib-cs (C#), raylib-python-cffi / `pyray` (Python), raylib-rs (Rust), raylib-go (Go), raylib-zig, Odin's vendor:raylib. API names stay close to C (`rl.InitWindow`, `Raylib.DrawText`), so the pitfalls below apply to them as well.

## Pitfalls (what AI answers get wrong)
1. **Loading GPU resources before `InitWindow`** (textures, fonts, shaders, models) fails: there is no GL context yet. 6.0 avoids the crash but still nothing loads.
2. **6.0 animation redesign**: `ModelAnimation` now has `keyframeCount` and `keyframePoses` (5.x had `frameCount`, `framePoses`, `bones`); `UpdateModelAnimation(Model, ModelAnimation, float frame)` takes a **float** frame (was `int`); `UpdateModelAnimationBones` is gone; blending via `UpdateModelAnimationEx(model, animA, frameA, animB, frameB, blend)`.
3. **6.0 removals**: `DrawModelPoints`/`DrawModelPointsEx` (moved to an example), `SetupFramebuffer`, `TRACELOGD`, GIF recording option, `RLGL_RENDER_TEXTURES_HINT`.
4. **6.0 signature changes**: `DrawCircleGradient(Vector2 center, float radius, Color inner, Color outer)` (was `int centerX, int centerY`); `SetSoundPan`/`SetMusicPan` range is now -1.0 (left) .. 0.0 (center) .. 1.0 (right) (was 0.5 center); `EncodeDataBase64`/`DecodeDataBase64` use NUL-terminated strings; `LoadFontData` gained a parameter; rlgl shader-loading function names changed.
5. **HiDPI (6.0)**: content scaling requires `FLAG_WINDOW_HIGHDPI` at window creation; use `GetRenderWidth()` vs `GetScreenWidth()` deliberately. Fullscreen modes were redesigned to use the current display resolution; prefer `ToggleBorderlessWindowed()` for "fullscreen" on desktop.
6. **`SaveStorageValue`/`LoadStorageValue` were removed** (moved to an example long ago); use `SaveFileData`/`LoadFileData` or `SaveFileText`/`LoadFileText`.
7. **Ancient names**: `Begin2dMode`/`End2dMode`/`Begin3dMode` -> `BeginMode2D`/`EndMode2D`/`BeginMode3D`; `GetMouseWheelMove()` returns float; `IsKeyPressed` (edge) vs `IsKeyDown` (held) vs `IsKeyPressedRepeat`.
8. **raygui 4.0/5.0**: all controls return `int`; many take values by pointer (`GuiSlider(..., &value, min, max)`, `GuiCheckBox(..., &checked)`); `GuiSpinner` and `GuiSliderPro` were removed in 5.0; `GuiMessageBox`/`GuiTextInputBox` result handling changed in 5.0. `RAYGUI_IMPLEMENTATION` must be defined in exactly one translation unit.
9. **Music without `UpdateMusicStream` every frame** stutters or stops; `PlaySound` on a playing sound restarts it (use `LoadSoundAlias` for overlaps).
10. **Strings from `TextFormat`** live in a small rotating static buffer: copy them if you keep them. 6.0 `TextInsert()` also uses a static buffer now.
11. **Web main loop**: a blocking `while (!WindowShouldClose())` needs `-s ASYNCIFY`; otherwise move the frame body to a function and use `emscripten_set_main_loop(UpdateDrawFrame, 0, 1)` (Emscripten API).
12. **C vs C++ literals**: `(Color){...}` compound literals are C; in C++ write `Color{...}` (raylib's `CLITERAL` macro handles both in its headers).
13. **6.2 (upcoming, not released)**: renames `ImageDrawTriangleEx` -> `ImageDrawTriangleGradient`, `GetSplinePointBezierQuad` -> `GetSplinePointBezierQuadratic`, reorders `DrawCapsule`/`ImageDraw` params and changes File API return values. Do not use these names against 6.0.

## Rendering
- Immediate-mode batching through rlgl; default backend OpenGL 3.3 on desktop, ES2/ES3 (WebGL1/2) on web and mobile; 6.0 adds `rlsw` CPU software renderer (no GPU needed).
- 2D: shapes (`DrawRectangleRec`, `DrawCircleV`, `DrawLineEx`, splines), textures (`DrawTexture`, `DrawTextureEx`, `DrawTextureRec` for sprite sheets, `DrawTexturePro` for scaled/rotated), `RenderTexture2D` via `LoadRenderTexture` + `BeginTextureMode`/`EndTextureMode` (pixel-perfect scaling), `BeginScissorMode`, `BeginBlendMode`.
- 3D: `LoadModel` (OBJ, IQM, glTF/GLB, VOX, M3D), `DrawModel`, `GenMesh*` procedural meshes, `LoadShader` + `BeginShaderMode`, skeletal animation (redesigned 6.0), `DrawBillboard`.
- Text: default font, `LoadFont`/`LoadFontEx` (TTF/OTF/BMFont), `DrawTextEx`, `MeasureText`/`MeasureTextEx`; SDF fonts supported.

## Physics
No physics engine. Built-in collision helpers only: `CheckCollisionRecs`, `CheckCollisionCircles`, `CheckCollisionCircleRec`, `CheckCollisionPointRec`, `GetCollisionRec`, 3D `CheckCollisionBoxes`, `GetRayCollisionMesh`/`Box`/`Sphere`. For real physics, link Box2D (C) or Chipmunk2D/Jolt (community, not raylib projects).

## Input
- Keyboard: `IsKeyPressed/IsKeyDown/IsKeyReleased/IsKeyUp/IsKeyPressedRepeat(KEY_X)`, `GetKeyPressed()`, text `GetCharPressed()` (call in a loop until 0).
- Mouse: `GetMousePosition()`, `GetMouseDelta()`, `IsMouseButtonPressed(MOUSE_BUTTON_LEFT)`, `GetMouseWheelMove()`, `DisableCursor()` for FPS look.
- Gamepad: `IsGamepadAvailable(0)`, `IsGamepadButtonDown(0, GAMEPAD_BUTTON_RIGHT_FACE_DOWN)`, `GetGamepadAxisMovement(0, GAMEPAD_AXIS_LEFT_X)`.
- Touch/gestures: `GetTouchPosition`, `GetGestureDetected`.

## UI
No retained UI. Options: hand-drawn with shapes/text, or **raygui 5.0** (immediate mode: `GuiButton`, `GuiLabel`, `GuiSlider`, `GuiCheckBox`, `GuiTextBox`, `GuiWindowBox`, `GuiListView`, styles via `GuiLoadStyle`). Layouts can be designed in rGuiLayout (official tool). Dear ImGui via rlImGui (community).

## Networking and multiplayer
No built-in networking. Use ENet, a sockets library, or a binding's language networking; for web, WebSockets via Emscripten. Community "raylib + enet" examples exist (unverified quality).

## Save data
- `SaveFileData(name, data, size)` / `LoadFileData(name, &size)` + `UnloadFileData`; `SaveFileText`/`LoadFileText` + `UnloadFileText`; `FileExists`, `DirectoryExists`, `MakeDirectory`; 6.0 adds `FileRename`, `FileRemove`, `FileCopy`, `FileMove`.
- Web: files go to Emscripten's in-memory FS; persist with IDBFS (Emscripten feature) or they vanish on reload.
- Pick a per-user directory yourself (e.g. `%APPDATA%`, `~/.local/share`); raylib has no "pref path" helper (unverified; SDL has `SDL_GetPrefPath`).

## Performance
- Draw calls are batched; keep texture switches low (use atlases / `DrawTextureRec`).
- Avoid `LoadTexture`/`LoadSound` inside the loop; load once.
- Large static 3D: upload meshes once (`UploadMesh` is done by `LoadModel`); use `DrawMeshInstanced` for many copies.
- `SetTargetFPS(0)` for uncapped profiling; `DrawFPS(x,y)`.
- Software renderer (rlsw) is for devices without GPU; expect low resolution/performance.

## Build and export
- Desktop: `gcc main.c -o game -lraylib -lGL -lm -lpthread -ldl -lrt -lX11` (Linux), `-lraylib -lopengl32 -lgdi32 -lwinmm` (MinGW Windows), or CMake. Ship the executable plus `resources/`.
- Web (official wiki): build `libraylib.a` with `PLATFORM=PLATFORM_WEB`, then
  `emcc -o game.html game.c -Os -Wall ./path-to/libraylib.a -I. -Ipath-to-raylib-h -L. -Lpath-to-libraylib-a -s USE_GLFW=3 -s ASYNCIFY --shell-file path-to/shell.html -DPLATFORM_WEB --preload-file resources`. Use `-s MAX_WEBGL_VERSION=2` for GLES3; `-s FORCE_FILESYSTEM=1` for save/load; serve over HTTP (`python -m http.server`/`emrun`), not file://. For itch.io: rename to `index.html` and zip with `.js/.wasm/.data`.
- Android: official Makefile/template with NDK; Raspberry Pi: `PLATFORM_DRM`.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| Texture is blank/white, log "failed to load" | Loaded before `InitWindow` or wrong relative path | Load after `InitWindow`; `ChangeDirectory(GetApplicationDirectory())`; check log |
| Music stops after a second | Missing `UpdateMusicStream` | Call it every frame |
| No sound | `InitAudioDevice()` not called | Call once after `InitWindow` |
| Game window closes on ESC | Default exit key | `SetExitKey(KEY_NULL)` |
| `UpdateModelAnimation` argument/field errors on 6.0 | 6.0 animation redesign | Use `keyframeCount`, float frame |
| Web build black screen "unsupported shader version" | GLES3 without WebGL2 flag | `-s MAX_WEBGL_VERSION=2` or build ES2 |
| `wasm-ld` errors | Stale object files from desktop build | Delete `.o` and `libraylib.a`, rebuild for web |
| Web game stutters with ASYNCIFY | Blocking loop timing | Use `emscripten_set_main_loop` frame function |
| Blurry pixel art when scaled | Bilinear filtering | `SetTextureFilter(tex, TEXTURE_FILTER_POINT)` or render to a `RenderTexture2D` and scale |
| Multiple definition of raygui functions | `RAYGUI_IMPLEMENTATION` in several files | Define it in one .c only |
| Window tiny/huge on HiDPI | 6.0 HiDPI changes | Set `FLAG_WINDOW_HIGHDPI`; use `GetRenderWidth` for render target sizes |

## Mapping from Roblox
| Roblox | raylib | Notes |
|---|---|---|
| Workspace / Instance tree | Your own arrays/structs | No scene graph |
| Part | `Rectangle`/`BoundingBox` + `DrawCube`/`DrawRectangleRec` | You draw it every frame |
| Model | `Model` from `LoadModel` (glTF/OBJ) | Meshes + materials only |
| Script / LocalScript | Code in the main loop / functions you call | Single program |
| ModuleScript | `.c/.h` files | |
| RemoteEvent | None; add ENet/sockets yourself | |
| DataStore | `SaveFileData`/`LoadFileData` | Local files only |
| Players | Your own player struct(s) | |
| Humanoid | Your own movement + collision code | |
| RunService.Heartbeat | Body of the `while (!WindowShouldClose())` loop with `GetFrameTime()` | |
| RenderStepped | Code between `BeginDrawing`/`EndDrawing` | |
| TweenService | Manual lerp: `Lerp`, `Vector2Lerp`, `Vector3Lerp` in raymath; easings header in examples | |
| CollectionService tags | Enum/flag fields in your structs | |
| Attributes | Struct fields | |
| ScreenGui | Draw UI after `EndMode2D/3D`, or raygui | |
| UserInputService | `IsKeyDown`, `GetMousePosition`, gamepad functions | |
| task.wait | Timers with accumulated `GetFrameTime()`; `WaitTime()` blocks the whole program | |
| Studio playtest | Build and run the executable | |
| Publishing | Ship binary/web build (itch.io etc.) yourself | |

## Minimal example
raylib 6.0, C: move a square with arrow keys, collect coins, show score.
```c
#include "raylib.h"
#include "raymath.h"

#define COINS 5

int main(void)
{
    InitWindow(800, 450, "raylib 6.0 - collect coins");
    SetTargetFPS(60);

    Vector2 player = { 400, 225 };
    const float speed = 250.0f;
    Vector2 coins[COINS];
    bool taken[COINS] = { 0 };
    for (int i = 0; i < COINS; i++) coins[i] = (Vector2){ 100.0f + i * 150.0f, 100.0f };
    int score = 0;

    while (!WindowShouldClose())
    {
        float dt = GetFrameTime();
        Vector2 dir = { 0 };
        if (IsKeyDown(KEY_RIGHT)) dir.x += 1;
        if (IsKeyDown(KEY_LEFT))  dir.x -= 1;
        if (IsKeyDown(KEY_DOWN))  dir.y += 1;
        if (IsKeyDown(KEY_UP))    dir.y -= 1;
        player = Vector2Add(player, Vector2Scale(Vector2Normalize(dir), speed * dt));

        Rectangle box = { player.x - 16, player.y - 16, 32, 32 };
        for (int i = 0; i < COINS; i++)
        {
            if (!taken[i] && CheckCollisionCircleRec(coins[i], 10, box)) { taken[i] = true; score++; }
        }

        BeginDrawing();
            ClearBackground(RAYWHITE);
            for (int i = 0; i < COINS; i++) if (!taken[i]) DrawCircleV(coins[i], 10, GOLD);
            DrawRectangleRec(box, BLUE);
            DrawText(TextFormat("Score: %i", score), 10, 10, 20, DARKGRAY);
        EndDrawing();
    }

    CloseWindow();
    return 0;
}
```

## Sources
- https://github.com/raysan5/raylib/releases (6.0 is latest release; 5.5 and 5.0 earlier; key 6.0 changes)
- https://raw.githubusercontent.com/raysan5/raylib/master/CHANGELOG ("Current Release: raylib 6.0 (23 April 2026)", 6.0 REMOVED/REDESIGNED lists, 6.2 unreleased "xx Oct 2026")
- https://raw.githubusercontent.com/raysan5/raylib/6.0/src/raylib.h (6.0 prototypes: UpdateModelAnimation float frame, UpdateModelAnimationEx, keyframeCount, DrawCircleGradient Vector2, SetSoundPan -1..1, FLAG_* list, LoadSoundAlias, File* functions)
- https://raw.githubusercontent.com/raysan5/raylib/5.5/src/raylib.h (5.5 had int frame, UpdateModelAnimationBones, DrawModelPoints, pan 0.5 center)
- https://github.com/raysan5/raylib/wiki/Working-for-Web-(HTML5) (emcc flags, ASYNCIFY, preload, MAX_WEBGL_VERSION, caveats)
- https://github.com/raysan5/raygui/releases (raygui 5.0 latest; 4.0 int returns and by-reference params; 5.0 removals)
- https://raw.githubusercontent.com/raysan5/raygui/master/src/raygui.h (GuiButton/GuiSlider/GuiCheckBox signatures; master is 5.1-dev)
- https://en.wikipedia.org/wiki/Raylib (community: confirms 6.0 stable date)

## Confidence and gaps
- High: 6.0 version/date, removed/redesigned functions, animation signatures, raygui control signatures, web build flags.
- Medium: raygui 5.0 release year (page shows "20 Jul" only); full rlgl shader function renames in 6.0 not enumerated; exact new name of `SHADER_LOC_VERTEX_INSTANCETRANSFORMS` not captured.
- Community/unverified: binding names and counts, ENet suggestions, rlImGui, absence of a pref-path helper.
- Example not compiled in this session.
