---
name: engine-sdl3
description: SDL3 3.4 (C platform layer, Oct 2026): main callbacks, bool returns, renamed events, SDL_Renderer, SDL_GPU, SDL3_image/ttf/mixer. Use for SDL3 code or SDL2 ports.
---
# engine-sdl3
## Scope
SDL 3.4.18 (2026-10-02). SDL3_image 3.4, SDL3_ttf 3.2, SDL3_mixer 3.2. Check first whether the project uses `<SDL3/SDL.h>` or SDL2.
## Core model
- A platform layer, not an engine: window, events, input, audio, 2D renderer, GPU, files.
- Preferred structure: `#define SDL_MAIN_USE_CALLBACKS 1` + `SDL_AppInit`, `SDL_AppEvent`, `SDL_AppIterate`, `SDL_AppQuit` (return `SDL_APP_CONTINUE`/`SDL_APP_SUCCESS`/`SDL_APP_FAILURE`); no `main()`.
- Or classic `main` + `SDL_PollEvent` loop with `<SDL3/SDL_main.h>`.
- 2D: `SDL_Renderer` with float rects; modern 3D: SDL_GPU (Vulkan/D3D12/Metal).
## Idioms
- Functions return `bool` (true = ok) or NULL; log `SDL_GetError()`.
- `SDL_CreateWindowAndRenderer("t", 800, 450, 0, &win, &ren)`; `SDL_SetRenderVSync(ren, 1)`.
- Held keys: `const bool *k = SDL_GetKeyboardState(NULL); k[SDL_SCANCODE_LEFT]`.
- Key press: `event->type == SDL_EVENT_KEY_DOWN && event->key.key == SDLK_SPACE`.
- Draw: `SDL_RenderClear`, `SDL_RenderFillRect(ren, &frect)`, `SDL_RenderTexture(ren, tex, NULL, &dst)`, `SDL_RenderPresent`.
- Saves: `SDL_GetPrefPath` + `SDL_SaveFile`.
## Pitfalls
1. `if (SDL_Init(..) < 0)` is SDL2; SDL3 returns bool: `if (!SDL_Init(SDL_INIT_VIDEO))`.
2. Events renamed: `SDL_QUIT`->`SDL_EVENT_QUIT`, `SDL_KEYDOWN`->`SDL_EVENT_KEY_DOWN`; `SDL_WINDOWEVENT` removed (`SDL_EVENT_WINDOW_RESIZED`...).
3. `event.key.keysym.sym` -> `event.key.key`; `keysym.mod` -> `event.key.mod`; `state` -> `down` (bool).
4. `SDL_RenderCopy`/`RenderCopyEx` -> `SDL_RenderTexture`/`SDL_RenderTextureRotated` with `SDL_FRect`; `SDL_RenderFillRectF` -> `SDL_RenderFillRect`; `SDL_RenderSetLogicalSize` -> `SDL_SetRenderLogicalPresentation`.
5. `SDL_CreateRenderer(win, NULL)` (no flags); `SDL_CreateWindow(title, w, h, flags)` has no x/y.
6. `SDL_FreeSurface`->`SDL_DestroySurface`; `SDL_RWops`->`SDL_IOStream`, `SDL_RWFromFile`->`SDL_IOFromFile`.
7. `SDL_GameController`->`SDL_Gamepad`; `SDL_CONTROLLER_BUTTON_A`->`SDL_GAMEPAD_BUTTON_SOUTH`; `SDL_INIT_EVERYTHING` removed.
8. Audio: `SDL_OpenAudioDeviceStream` + `SDL_PutAudioStreamData` (not `SDL_QueueAudio`); init `SDL_INIT_AUDIO`.
9. Callbacks: no `main()`, no event polling inside `SDL_AppIterate`, keep state in `*appstate`.
10. SDL3_image: no `IMG_Init`; use `IMG_LoadTexture(ren, path)`.
11. SDL3_ttf: `TTF_OpenFont(path, 24.0f)`; `TTF_RenderText_Blended(font, text, 0, color)` (length arg; `TTF_RenderUTF8_*` gone).
12. SDL3_mixer is redesigned: `MIX_Init`, `MIX_CreateMixerDevice`, `MIX_LoadAudio`, `MIX_CreateTrack`, `MIX_PlayTrack`/`MIX_PlayAudio`; no `Mix_OpenAudio`/`Mix_Chunk`.
## Roblox to SDL3
- Workspace / Instance tree -> your own structs
- Part -> `SDL_FRect` + `SDL_RenderFillRect`
- Script / LocalScript -> code in `SDL_AppIterate` / `SDL_AppEvent`
- RunService.Heartbeat -> `SDL_AppIterate` with dt from `SDL_GetTicksNS`
- UserInputService -> `SDL_AppEvent` + `SDL_GetKeyboardState`
- ScreenGui -> draw last (SDL3_ttf)
- DataStore -> `SDL_GetPrefPath` files / `SDL_OpenUserStorage` (local)
- RemoteEvent -> not in core (SDL_net, ENet, sockets)
- task.wait -> timers in your loop
- Studio playtest -> build with CMake and run
## Skeleton
```c
#define SDL_MAIN_USE_CALLBACKS 1
#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>

static SDL_Window *win;
static SDL_Renderer *ren;
static SDL_FRect player = { 100, 100, 32, 32 };
static Uint64 last;

SDL_AppResult SDL_AppInit(void **appstate, int argc, char **argv) {
    if (!SDL_Init(SDL_INIT_VIDEO)) return SDL_APP_FAILURE;
    if (!SDL_CreateWindowAndRenderer("game", 800, 450, 0, &win, &ren)) return SDL_APP_FAILURE;
    last = SDL_GetTicksNS();
    return SDL_APP_CONTINUE;
}
SDL_AppResult SDL_AppEvent(void *appstate, SDL_Event *e) {
    return e->type == SDL_EVENT_QUIT ? SDL_APP_SUCCESS : SDL_APP_CONTINUE;
}
SDL_AppResult SDL_AppIterate(void *appstate) {
    Uint64 now = SDL_GetTicksNS();
    float dt = (now - last) / 1e9f; last = now;
    const bool *k = SDL_GetKeyboardState(NULL);
    player.x += (k[SDL_SCANCODE_RIGHT] - k[SDL_SCANCODE_LEFT]) * 250.0f * dt;
    SDL_SetRenderDrawColor(ren, 0, 0, 0, 255);
    SDL_RenderClear(ren);
    SDL_SetRenderDrawColor(ren, 60, 150, 255, 255);
    SDL_RenderFillRect(ren, &player);
    SDL_RenderPresent(ren);
    return SDL_APP_CONTINUE;
}
void SDL_AppQuit(void *appstate, SDL_AppResult r) {}
```
## Verification
Build with CMake (`find_package(SDL3)`), run, watch `SDL_Log` output; SDL2-name compile errors map to the pitfalls. Claim it runs only after seeing the window.
