# SDL3: STAR engine research
**Verified 2026-10-13 against official docs. Current stable: SDL 3.4.18 (2026-10-02); 3.4.0 shipped 2026-01-01, first stable SDL3 was 3.2.0 (Jan 2025).** zlib license, free. Satellite libraries: SDL3_image 3.4.x, SDL3_ttf 3.2.x, SDL3_mixer 3.2.4 (2026-06-03).

## At a glance
| | |
|---|---|
| Best for | Cross-platform window/input/audio/graphics layer for C/C++ engines and games; ports; custom engines; 2D games with SDL_Renderer; modern GPU code via SDL_GPU |
| Weak at | Not a game engine: no scene graph, physics, UI, asset pipeline, networking or editor |
| Language(s) | C (C99 API); usable from C++, and via many bindings (C#, Rust, Python, Zig, Odin...) |
| Editor / tooling | None. CMake (official), prebuilt dev packages for Windows (VC/MinGW), macOS framework, distro packages; `SDL_shadercross` for GPU shaders |
| Platforms (export) | Windows, macOS, Linux (X11/Wayland/KMSDRM), iOS, tvOS, visionOS, Android, Emscripten (web), Haiku, consoles via NDA ports (PS2 display hints even mentioned in 3.4) |
| License / cost | zlib, free |
| Roblox-likeness | low: you write the entire game loop and every system yourself |

## Architecture and lifecycle
Two ways to structure the program:

1. **Main callbacks (recommended for portability, required-feeling on web/iOS)**:
```c
#define SDL_MAIN_USE_CALLBACKS 1   /* define before including SDL_main.h, in ONE file */
#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>

SDL_AppResult SDL_AppInit(void **appstate, int argc, char **argv);  /* once */
SDL_AppResult SDL_AppEvent(void *appstate, SDL_Event *event);       /* per event */
SDL_AppResult SDL_AppIterate(void *appstate);                       /* per frame */
void SDL_AppQuit(void *appstate, SDL_AppResult result);             /* once */
```
   Return `SDL_APP_CONTINUE`, `SDL_APP_SUCCESS` (exit 0) or `SDL_APP_FAILURE`. Do not write `main()`; do not pump/poll events in `SDL_AppIterate` or `SDL_AppEvent` (SDL does it). Store state in `*appstate` (it is NULL later unless set). SDL calls `SDL_Quit` after `SDL_AppQuit`. Iteration rate can be capped with the `SDL_HINT_MAIN_CALLBACK_RATE` hint.
2. **Classic main loop**: `int main(int argc, char *argv[])` with `#include <SDL3/SDL_main.h>` in that file, `SDL_Init`, `while (running) { while (SDL_PollEvent(&e)) {...} update; render; }`, `SDL_Quit()`.

Subsystems: `SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMEPAD)`. Audio is no longer initialized implicitly. `SDL_INIT_EVERYTHING` and `SDL_INIT_TIMER` are gone.

Graphics options: **SDL_Renderer** (2D, batched, float coordinates; backends D3D11/12, Metal, OpenGL, Vulkan, GPU, software) or **SDL_GPU** (modern explicit API over Vulkan/D3D12/Metal) or raw OpenGL/Vulkan with SDL windows. 3.4 lets the 2D renderer run on the GPU API and use custom fragment shaders, improving interop.

## Project layout
```
mygame/
  CMakeLists.txt     # find_package(SDL3 REQUIRED CONFIG) or add_subdirectory(vendor/SDL)
  src/main.c
  assets/            # load relative to SDL_GetBasePath()
```
```cmake
cmake_minimum_required(VERSION 3.16)
project(mygame C)
find_package(SDL3 REQUIRED CONFIG)
add_executable(mygame src/main.c)
target_link_libraries(mygame PRIVATE SDL3::SDL3)
```
(Satellite libs: `find_package(SDL3_image)`, `SDL3_ttf`, `SDL3_mixer` with targets `SDL3_image::SDL3_image` etc.; exact component names unverified.)

## Scripting idioms
- Error checking: almost every function returns `bool` (true = success) or a pointer (NULL = failure); then `SDL_Log("...: %s", SDL_GetError())`.
```c
if (!SDL_Init(SDL_INIT_VIDEO)) { SDL_Log("init: %s", SDL_GetError()); return SDL_APP_FAILURE; }
if (!SDL_CreateWindowAndRenderer("game", 800, 450, SDL_WINDOW_RESIZABLE, &window, &renderer)) { ... }
SDL_SetRenderVSync(renderer, 1);
SDL_SetRenderLogicalPresentation(renderer, 320, 180, SDL_LOGICAL_PRESENTATION_INTEGER_SCALE);
```
- Delta time: `Uint64 now = SDL_GetTicksNS(); float dt = (now - last) / 1e9f; last = now;` (`SDL_GetTicks()` is `Uint64` ms).
- Continuous keys: `const bool *keys = SDL_GetKeyboardState(NULL); if (keys[SDL_SCANCODE_LEFT]) ...`.
- Discrete keys: `if (event->type == SDL_EVENT_KEY_DOWN && event->key.key == SDLK_SPACE && !event->key.repeat)`.
- Drawing: `SDL_SetRenderDrawColor(r, 0,0,0,255); SDL_RenderClear(r); SDL_FRect rc = {x,y,32,32}; SDL_RenderFillRect(r, &rc); SDL_RenderTexture(r, tex, NULL, &dst); SDL_RenderPresent(r);`
- Debug text without SDL_ttf (3.2+): `SDL_RenderDebugText(renderer, 10, 10, "Score: 3");` (8x8 bitmap font).
- Images: `SDL_LoadBMP` built in; 3.4 adds native PNG load/save in core; SDL3_image `IMG_LoadTexture(renderer, "a.png")` for everything else. `SDL_CreateTextureFromSurface` + `SDL_DestroySurface`.
- Pixel art: `SDL_SetTextureScaleMode(tex, SDL_SCALEMODE_NEAREST)`.
- Metadata: `SDL_SetAppMetadata("My Game", "1.0", "com.example.mygame");` early.

## Pitfalls (what AI answers get wrong)
1. **Return values are `bool`**: SDL2 code `if (SDL_Init(...) < 0)` is wrong; SDL3 returns `true` on success. Likewise `SDL_RenderTexture`, `SDL_SetRenderDrawColor`, etc.
2. **Event names**: `SDL_QUIT` -> `SDL_EVENT_QUIT`; `SDL_KEYDOWN` -> `SDL_EVENT_KEY_DOWN`; `SDL_MOUSEBUTTONDOWN` -> `SDL_EVENT_MOUSE_BUTTON_DOWN`; `SDL_WINDOWEVENT` removed, subtypes are top-level (`SDL_EVENT_WINDOW_RESIZED`, `SDL_EVENT_WINDOW_CLOSE_REQUESTED`, `SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED`).
3. **Key event fields**: `event.key.keysym.sym` -> `event.key.key`; `keysym.mod` -> `event.key.mod`; `event.key.state == SDL_PRESSED` -> `event.key.down` (bool).
4. **Renderer API**: `SDL_CreateRenderer(window, NULL)` (driver name string, no index/flags; vsync via `SDL_SetRenderVSync`). `SDL_RenderCopy` -> `SDL_RenderTexture` (takes `SDL_FRect*`); `SDL_RenderCopyEx` -> `SDL_RenderTextureRotated`; `SDL_RenderDrawLine/Rect` -> `SDL_RenderLine/SDL_RenderRect`; `SDL_RenderFillRectF` -> `SDL_RenderFillRect` (float rects); `SDL_RenderSetLogicalSize` -> `SDL_SetRenderLogicalPresentation`.
5. **Window creation**: `SDL_CreateWindow(title, w, h, flags)` (no x/y; use `SDL_CreateWindowWithProperties` for position); `SDL_WINDOW_SHOWN` removed; `SDL_WINDOW_ALLOW_HIGHDPI` -> `SDL_WINDOW_HIGH_PIXEL_DENSITY`; `SDL_SetWindowFullscreen(win, bool)` is asynchronous.
6. **Surfaces/IO**: `SDL_FreeSurface` -> `SDL_DestroySurface`; `SDL_CreateRGBSurface*` -> `SDL_CreateSurface`; `SDL_RWops` -> `SDL_IOStream`, `SDL_RWFromFile` -> `SDL_IOFromFile`, `SDL_RWread` -> `SDL_ReadIO`.
7. **Gamepads**: `SDL_GameController*` -> `SDL_Gamepad*` (`SDL_OpenGamepad`, `SDL_GetGamepadButton`); `SDL_CONTROLLER_BUTTON_A` -> `SDL_GAMEPAD_BUTTON_SOUTH` (positional face buttons); `SDL_INIT_GAMECONTROLLER` -> `SDL_INIT_GAMEPAD`.
8. **Audio**: callback `SDL_OpenAudioDevice` + `SDL_QueueAudio` -> `SDL_OpenAudioDeviceStream` + `SDL_PutAudioStreamData`; `SDL_PauseAudioDevice(dev, 0)` -> `SDL_ResumeAudioDevice`; `AUDIO_S16` -> `SDL_AUDIO_S16LE`.
9. **Keyboard state** is `const bool *` (was `Uint8 *`); text input is off by default and `SDL_StartTextInput(window)` needs the window.
10. **Main callbacks**: defining `main()` while `SDL_MAIN_USE_CALLBACKS` is set fails to link; polling events inside `SDL_AppIterate` is wrong; forgetting `SDL_main.h` in the main file breaks Windows/mobile entry points.
11. **SDL3_image**: `IMG_Init`/`IMG_Quit` removed (formats load on demand); `IMG_GetError` -> `SDL_GetError`; `*_RW` -> `*_IO`.
12. **SDL3_ttf**: `TTF_OpenFont(file, float ptsize)`; `TTF_RenderUTF8_*` -> `TTF_RenderText_*` with an explicit `size_t length` (0 = NUL-terminated): `TTF_RenderText_Blended(font, "Hi", 0, color)`; UNICODE variants removed; `TTF_MeasureText` -> `TTF_MeasureString`; new text engine API (`TTF_CreateRendererTextEngine`, `TTF_CreateText`, `TTF_DrawRendererText`).
13. **SDL3_mixer 3.x is a full redesign**: `Mix_OpenAudio`, `Mix_Chunk`, `Mix_PlayChannel` are SDL2_mixer; SDL3_mixer uses `MIX_Init`, `MIX_CreateMixerDevice`, `MIX_LoadAudio`, `MIX_CreateTrack`, `MIX_SetTrackAudio`, `MIX_PlayTrack`, `MIX_PlayAudio` (fire-and-forget), `MIX_Quit`.
14. **Timing**: `SDL_GetTicks()` returns `Uint64`; `SDL_TICKS_PASSED` removed (compare directly); event timestamps are nanoseconds.

## Rendering
- **SDL_Renderer (2D)**: textures, points/lines/rects (float), `SDL_RenderGeometry` for arbitrary triangles, render targets (`SDL_TEXTUREACCESS_TARGET` + `SDL_SetRenderTarget`), blend modes, logical presentation (letterbox/integer scale), `SDL_RenderDebugText`. Always-on batching: call `SDL_FlushRenderer` before mixing raw graphics API calls. 3.4: GPU-backed renderer, custom fragment shaders, YUV/HDR colorspaces, palette textures, tiled 9-grid.
- **SDL_GPU (3.2+)**: `SDL_CreateGPUDevice(formats, debug, NULL)` -> `SDL_ClaimWindowForGPUDevice` -> per frame `SDL_AcquireGPUCommandBuffer` -> `SDL_WaitAndAcquireGPUSwapchainTexture` -> `SDL_BeginGPURenderPass` -> `SDL_BindGPUGraphicsPipeline`/`SDL_BindGPUVertexBuffers`/`SDL_DrawGPUPrimitives` -> `SDL_EndGPURenderPass` -> `SDL_SubmitGPUCommandBuffer`. Shaders: SPIR-V (Vulkan), DXIL/DXBC (D3D12), MSL (Metal); cross-compile with SDL_shadercross. Copy passes for uploads (`SDL_UploadToGPUBuffer`/`Texture`), compute passes.
- OpenGL: `SDL_WINDOW_OPENGL`, `SDL_GL_CreateContext`, `SDL_GL_DestroyContext` (was `SDL_GL_DeleteContext`), `SDL_GL_SwapWindow`.

## Physics
No built-in support. Rect helpers only: `SDL_HasRectIntersectionFloat`, `SDL_GetRectIntersectionFloat`, `SDL_PointInRectFloat` (float variants of the integer ones). Use Box2D, Chipmunk2D, Jolt (external).

## Input
- Events: `SDL_EVENT_KEY_DOWN/UP` (`key`, `scancode`, `mod`, `down`, `repeat`), `SDL_EVENT_MOUSE_MOTION` (float `x,y,xrel,yrel`), `SDL_EVENT_MOUSE_BUTTON_DOWN`, `SDL_EVENT_MOUSE_WHEEL`, `SDL_EVENT_GAMEPAD_ADDED/REMOVED/BUTTON_DOWN/AXIS_MOTION`, `SDL_EVENT_TEXT_INPUT`, touch/pen events, pinch gestures (3.4).
- Polling: `SDL_GetKeyboardState`, `SDL_GetMouseState(&x,&y)` (floats), `SDL_GetGamepadAxis`.
- Relative mouse: `SDL_SetWindowRelativeMouseMode(window, true)`.
- Gamepad mapping database is built in; face buttons are positional (South/East/West/North).

## UI
No built-in UI. Options: draw your own with SDL_Renderer + SDL3_ttf; Dear ImGui has official SDL3 + SDL_Renderer3/SDL_GPU3 backends (ImGui repo, not SDL); Nuklear/microui (community). 3.4 adds on-screen keyboard show/hide events and Windows/Linux taskbar progress.

## Networking and multiplayer
Not in core SDL. SDL_net exists as a satellite library for SDL3 (status/version unverified in this check); many projects use ENet, GameNetworkingSockets or plain sockets. Web builds must use WebSockets/WebRTC.

## Save data
- `SDL_GetPrefPath("org", "app")` returns a writable per-user folder (free it with `SDL_free`); write with `SDL_IOFromFile` + `SDL_WriteIO`, or `SDL_SaveFile`/`SDL_LoadFile` helpers.
- Storage API (3.2+): `SDL_OpenUserStorage(org, app, props)`, `SDL_OpenTitleStorage` for read-only game data; required abstraction on some consoles; poll `SDL_StorageReady`.
- Read-only assets: `SDL_GetBasePath()`.

## Performance
- Batching is automatic in SDL_Renderer; keep texture switches low (atlases), avoid creating textures every frame (cache text textures from SDL3_ttf or use `TTF_Text` objects).
- VSync via `SDL_SetRenderVSync(renderer, 1)`; with callbacks, iteration is paced by the platform/hint, not by `SDL_Delay`.
- Use `SDL_GetPerformanceCounter`/`SDL_GetPerformanceFrequency` or `SDL_GetTicksNS` for timing.
- SDL_GPU: create pipelines/buffers at init; set `SDL_SetGPUAllowedFramesInFlight` if latency matters.

## Build and export
- Desktop: CMake (`cmake -S . -B build && cmake --build build`), ship SDL3.dll/.so/.dylib (or link statically with `SDL_STATIC`) next to the binary plus assets.
- Web: Emscripten builds SDL3 from source with CMake (`emcmake cmake ...`); main callbacks avoid ASYNCIFY because the browser drives `SDL_AppIterate`. 3.4 improved Emscripten (fill-document windows, canvas/keyboard element hints).
- Android: Gradle template in `android-project/`; iOS: Xcode with SDL as subproject or xcframework.
- Version macros: `SDL_MAJOR_VERSION`, `SDL_MINOR_VERSION`, `SDL_MICRO_VERSION`; runtime `SDL_GetVersion()`.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| `if (SDL_Init(...) < 0)` never errors / logic inverted | SDL3 returns bool | `if (!SDL_Init(...))` |
| `SDL_QUIT`/`SDL_KEYDOWN` undeclared | SDL3 renamed events | `SDL_EVENT_QUIT`, `SDL_EVENT_KEY_DOWN` |
| `keysym` has no member | Field flattened | `event.key.key`, `event.key.scancode` |
| `SDL_RenderCopy` undeclared | Renamed | `SDL_RenderTexture(r, t, NULL, &frect)` |
| Multiple definition of `main` / undefined `SDL_main` | Callbacks + own main, or missing SDL_main.h | Use one model; include `SDL_main.h` once |
| No sound | Audio subsystem not initialized | `SDL_Init(SDL_INIT_AUDIO)` (or via mixer) |
| `Mix_OpenAudio` undeclared with SDL3_mixer | API redesigned | `MIX_Init` + `MIX_CreateMixerDevice` + tracks |
| Text renders garbage length | Missing `length` arg in SDL3_ttf | `TTF_RenderText_Blended(font, s, 0, col)` |
| Blurry scaled pixel art | Linear scale mode | `SDL_SetTextureScaleMode(t, SDL_SCALEMODE_NEAREST)` + integer logical presentation |
| Assets not found when launched from IDE | Working directory differs | Build paths from `SDL_GetBasePath()` |
| Fullscreen state wrong right after call | Fullscreen is async | Wait for `SDL_EVENT_WINDOW_ENTER_FULLSCREEN` or `SDL_SyncWindow` |

## Mapping from Roblox
| Roblox | SDL3 | Notes |
|---|---|---|
| Workspace / Instance tree | Your own data structures | SDL has no world |
| Part | `SDL_FRect` drawn with `SDL_RenderFillRect` | |
| Model | Your mesh loader + SDL_GPU/OpenGL | No model loading in SDL |
| Script / LocalScript | Code in `SDL_AppIterate`/`SDL_AppEvent` | |
| ModuleScript | .c/.h modules | |
| RemoteEvent | SDL_net / ENet / sockets | Not in core |
| DataStore | `SDL_GetPrefPath` files or `SDL_OpenUserStorage` | Local only |
| Players | Your structs | |
| Humanoid | Your movement code | |
| RunService.Heartbeat | `SDL_AppIterate` with dt from `SDL_GetTicksNS` | |
| RenderStepped | Rendering part of `SDL_AppIterate` before `SDL_RenderPresent` | |
| TweenService | Manual interpolation | |
| CollectionService tags | Flags/enums in structs | |
| Attributes | Struct fields / `SDL_PropertiesID` for SDL objects | |
| ScreenGui | Draw last each frame; SDL3_ttf or Dear ImGui | |
| UserInputService | `SDL_AppEvent` events + `SDL_GetKeyboardState` | |
| task.wait | Timers in your loop; `SDL_AddTimer` callbacks run on another thread | Never `SDL_Delay` in callbacks |
| Studio playtest | Build and run | |
| Publishing | Ship binaries/web build yourself | |

## Minimal example
SDL 3.4 with main callbacks and SDL_Renderer: move a square with arrows, collect a coin, show score with debug text.
```c
#define SDL_MAIN_USE_CALLBACKS 1
#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>

typedef struct {
    SDL_Window *window;
    SDL_Renderer *renderer;
    SDL_FRect player, coin;
    int score;
    Uint64 last;
} App;

SDL_AppResult SDL_AppInit(void **appstate, int argc, char **argv)
{
    SDL_SetAppMetadata("Coins", "1.0", "com.example.coins");
    if (!SDL_Init(SDL_INIT_VIDEO)) {
        SDL_Log("SDL_Init failed: %s", SDL_GetError());
        return SDL_APP_FAILURE;
    }
    App *app = SDL_calloc(1, sizeof(App));
    if (!app) return SDL_APP_FAILURE;
    *appstate = app;
    if (!SDL_CreateWindowAndRenderer("coins", 800, 450, 0, &app->window, &app->renderer)) {
        SDL_Log("window/renderer failed: %s", SDL_GetError());
        return SDL_APP_FAILURE;
    }
    SDL_SetRenderVSync(app->renderer, 1);
    app->player = (SDL_FRect){ 100, 200, 32, 32 };
    app->coin = (SDL_FRect){ 600, 200, 16, 16 };
    app->last = SDL_GetTicksNS();
    return SDL_APP_CONTINUE;
}

SDL_AppResult SDL_AppEvent(void *appstate, SDL_Event *event)
{
    if (event->type == SDL_EVENT_QUIT) return SDL_APP_SUCCESS;
    if (event->type == SDL_EVENT_KEY_DOWN && event->key.key == SDLK_ESCAPE) return SDL_APP_SUCCESS;
    return SDL_APP_CONTINUE;
}

SDL_AppResult SDL_AppIterate(void *appstate)
{
    App *app = appstate;
    Uint64 now = SDL_GetTicksNS();
    float dt = (float)(now - app->last) / 1e9f;
    app->last = now;

    const bool *keys = SDL_GetKeyboardState(NULL);
    float speed = 250.0f * dt;
    if (keys[SDL_SCANCODE_LEFT])  app->player.x -= speed;
    if (keys[SDL_SCANCODE_RIGHT]) app->player.x += speed;
    if (keys[SDL_SCANCODE_UP])    app->player.y -= speed;
    if (keys[SDL_SCANCODE_DOWN])  app->player.y += speed;

    if (SDL_HasRectIntersectionFloat(&app->player, &app->coin)) {
        app->score++;
        app->coin.x = (float)SDL_rand(780);
        app->coin.y = (float)SDL_rand(430);
    }

    SDL_SetRenderDrawColor(app->renderer, 20, 20, 30, 255);
    SDL_RenderClear(app->renderer);
    SDL_SetRenderDrawColor(app->renderer, 255, 210, 0, 255);
    SDL_RenderFillRect(app->renderer, &app->coin);
    SDL_SetRenderDrawColor(app->renderer, 60, 150, 255, 255);
    SDL_RenderFillRect(app->renderer, &app->player);
    SDL_SetRenderDrawColor(app->renderer, 255, 255, 255, 255);
    char buf[32];
    SDL_snprintf(buf, sizeof(buf), "Score: %d", app->score);
    SDL_RenderDebugText(app->renderer, 10, 10, buf);
    SDL_RenderPresent(app->renderer);
    return SDL_APP_CONTINUE;
}

void SDL_AppQuit(void *appstate, SDL_AppResult result)
{
    App *app = appstate;
    if (app) {
        SDL_DestroyRenderer(app->renderer);
        SDL_DestroyWindow(app->window);
        SDL_free(app);
    }
}
```

## Sources
- https://github.com/libsdl-org/SDL/releases (3.4.18 on 2026-10-02 latest; 3.4.0 on 2026-01-01; 3.4.0 feature list)
- https://raw.githubusercontent.com/libsdl-org/SDL/release-3.4.18/include/SDL3/SDL_version.h (3.4.18 version macros)
- https://raw.githubusercontent.com/libsdl-org/SDL/release-3.4.18/include/SDL3/SDL_render.h (SDL_RenderFillRect FRect, SDL_RenderTexture, SDL_SetRenderVSync, SDL_RenderDebugText, logical presentation modes)
- https://raw.githubusercontent.com/libsdl-org/SDL/release-3.4.18/include/SDL3/SDL_keyboard.h, SDL_timer.h, SDL_rect.h, SDL_filesystem.h, SDL_storage.h, SDL_init.h (const bool* keyboard state, Uint64 ticks, rect float intersection, pref path, user storage, SDL_SetAppMetadata)
- https://wiki.libsdl.org/SDL3/README-main-functions (callback signatures, SDL_AppResult, rules)
- https://raw.githubusercontent.com/libsdl-org/SDL/main/docs/README-migration.md (SDL2 -> SDL3 renames: events, renderer, surfaces, IO, gamepad, audio, window)
- https://wiki.libsdl.org/SDL3/SDL_CreateWindowAndRenderer (signature, bool, since 3.2.0)
- https://wiki.libsdl.org/SDL3/CategoryGPU (SDL_GPU workflow and functions)
- https://github.com/libsdl-org/SDL_ttf/releases and https://raw.githubusercontent.com/libsdl-org/SDL_ttf/main/docs/README-migration.md (SDL3_ttf 3.2.2, text engines, renames)
- https://wiki.libsdl.org/SDL3_ttf/TTF_RenderText_Blended and https://wiki.libsdl.org/SDL3_ttf/TTF_OpenFont (length param, float ptsize)
- https://raw.githubusercontent.com/libsdl-org/SDL_image/main/docs/README-migration.md (IMG_Init removed, *_IO)
- https://discourse.libsdl.org/t/announcing-sdl-image-3-4-0/65822 (SDL_image 3.4.0 features)
- https://github.com/libsdl-org/SDL_mixer/releases and https://wiki.libsdl.org/SDL3_mixer/CategoryAPI (SDL3_mixer 3.2.4, MIX_* API names)

## Confidence and gaps
- High: version/dates of SDL core, callback API, renames, renderer/keyboard/timer signatures (read from 3.4.18 headers).
- Medium: SDL 3.2.0 release month (from memory: January 2025); SDL3_image latest patch (3.4.4 seen in distro packages); SDL3_ttf may have a newer release than 3.2.2.
- Unverified: SDL_net for SDL3 status; exact CMake target names for satellites. Checked: `SDL_rand`, `SDL_SaveFile`/`SDL_LoadFile`, `SDL_SetWindowRelativeMouseMode`, `SDL_SCALEMODE_NEAREST` and `SDL_HINT_MAIN_CALLBACK_RATE` were confirmed in 3.4.18 headers.
- Example not compiled in this session.
