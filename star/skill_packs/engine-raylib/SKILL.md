---
name: engine-raylib
description: raylib 6.0 (C game library, Apr 2026) with raymath and raygui 5.0: main loop, drawing, input, audio, web builds. Use for raylib code in C or its bindings.
---
# engine-raylib
## Scope
raylib 6.0 (2026-04-23) plus raygui 5.0. 6.2 is unreleased and renames some functions. Check the project's `RAYLIB_VERSION` (raylib.h) or binding version first; 5.x and 6.0 differ in animation, audio pan and some signatures.
## Core model
- A C library, not an engine: no scene graph, entities or editor; you own structs and arrays.
- `InitWindow` creates the window and GL context; then loop `while (!WindowShouldClose())`.
- Each frame: update with `GetFrameTime()`, then `BeginDrawing()` ... `EndDrawing()` (polls input, swaps, waits for FPS).
- Every `LoadX` has an `UnloadX`; call `CloseWindow()` at the end.
## Idioms
- `SetConfigFlags(FLAG_WINDOW_RESIZABLE | FLAG_VSYNC_HINT)` before `InitWindow`; `SetTargetFPS(60)`.
- Movement: `pos = Vector2Add(pos, Vector2Scale(Vector2Normalize(dir), speed * GetFrameTime()))`.
- Collision helpers: `CheckCollisionRecs`, `CheckCollisionCircleRec`, `CheckCollisionPointRec`.
- 2D camera: `Camera2D` + `BeginMode2D(cam)`/`EndMode2D()`; 3D: `Camera3D`, `UpdateCamera(&cam, CAMERA_ORBITAL)`, `BeginMode3D`.
- Text: `DrawText(TextFormat("Score: %i", s), 10, 10, 20, DARKGRAY)`.
- Audio: `InitAudioDevice()`; `LoadSound`/`PlaySound`; `LoadMusicStream` + `UpdateMusicStream` every frame.
- raygui: `#define RAYGUI_IMPLEMENTATION` in one .c; `if (GuiButton(rect, "Go"))`; sliders take `&value`.
## Pitfalls
1. Loading textures, fonts, shaders or models before `InitWindow` fails (no GL context).
2. 6.0 animation: `ModelAnimation` uses `keyframeCount`/`keyframePoses` (not `frameCount`/`framePoses`); `UpdateModelAnimation(model, anim, float frame)`; `UpdateModelAnimationBones` removed; blend with `UpdateModelAnimationEx`.
3. 6.0 removed `DrawModelPoints`, `DrawModelPointsEx`, `SetupFramebuffer`, `TRACELOGD`.
4. 6.0 `DrawCircleGradient(Vector2 center, float r, Color in, Color out)`; old int x/y form fails.
5. 6.0 `SetSoundPan`/`SetMusicPan`: -1 left, 0 center, 1 right (5.x used 0.5 as center).
6. HiDPI scaling needs `FLAG_WINDOW_HIGHDPI` at creation (6.0); use `GetRenderWidth` for render sizes.
7. `SaveStorageValue`/`LoadStorageValue` no longer exist: use `SaveFileData`/`LoadFileData` or `SaveFileText`.
8. Old names `Begin2dMode`/`End2dMode` are gone: `BeginMode2D`/`EndMode2D`.
9. raygui 4.0+: controls return int and take values by pointer; 5.0 removed `GuiSpinner` and `GuiSliderPro`.
10. Music needs `UpdateMusicStream` every frame; overlapping one-shots need `LoadSoundAlias`.
11. `TextFormat` returns a static rotating buffer: copy strings you keep.
12. Web: a blocking loop needs `-s ASYNCIFY`, or use `emscripten_set_main_loop(frame, 0, 1)`; link with `-s USE_GLFW=3`, `--preload-file resources`, serve over HTTP.
## Roblox to raylib
- Workspace / Instance tree -> your own arrays of structs
- Part -> `Rectangle`/`BoundingBox` you draw each frame
- Model -> `LoadModel("x.glb")` + `DrawModel`
- Script / ModuleScript -> functions in .c/.h files called from the loop
- RunService.Heartbeat -> loop body with `GetFrameTime()`
- UserInputService -> `IsKeyDown`, `IsKeyPressed`, `GetMousePosition`
- ScreenGui -> draw after `EndMode2D`, or raygui
- TweenService -> `Lerp`/`Vector2Lerp` with a timer
- task.wait -> accumulate `GetFrameTime()` (never block the loop)
- DataStore -> `SaveFileData`/`LoadFileData` (local only)
- RemoteEvent -> none built in (add ENet or sockets)
- Studio playtest -> compile and run the executable
## Skeleton
```c
#include "raylib.h"
#include "raymath.h"

int main(void)
{
    InitWindow(800, 450, "game");
    SetTargetFPS(60);
    Vector2 p = { 400, 225 };
    int score = 0;
    while (!WindowShouldClose())
    {
        Vector2 d = { (float)(IsKeyDown(KEY_RIGHT) - IsKeyDown(KEY_LEFT)),
                      (float)(IsKeyDown(KEY_DOWN) - IsKeyDown(KEY_UP)) };
        p = Vector2Add(p, Vector2Scale(Vector2Normalize(d), 250.0f * GetFrameTime()));
        if (CheckCollisionCircles(p, 16, (Vector2){ 600, 200 }, 10)) score = 1;
        BeginDrawing();
            ClearBackground(RAYWHITE);
            DrawCircleV((Vector2){ 600, 200 }, 10, GOLD);
            DrawCircleV(p, 16, BLUE);
            DrawText(TextFormat("Score: %i", score), 10, 10, 20, DARKGRAY);
        EndDrawing();
    }
    CloseWindow();
    return 0;
}
```
## Verification
Build with the project's CMake/Makefile and run it; check the log for "failed to load". Web: emcc build, open via a local HTTP server. Report a run only if you saw it.
