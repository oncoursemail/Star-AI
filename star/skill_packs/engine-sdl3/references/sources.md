# Sources for engine-sdl3

Official documentation reviewed 2026-10-13 (accessed by web, not by a live engine run):

- https://github.com/libsdl-org/SDL/releases (SDL 3.4.18 released 2026-10-02; 3.4.0 on 2026-01-01 and its features)
- https://wiki.libsdl.org/SDL3/README-main-functions (SDL_AppInit/AppEvent/AppIterate/AppQuit signatures and rules)
- https://raw.githubusercontent.com/libsdl-org/SDL/main/docs/README-migration.md (SDL2 to SDL3 renames: events, renderer, IO, gamepad, audio, window)
- https://raw.githubusercontent.com/libsdl-org/SDL/release-3.4.18/include/SDL3/SDL_render.h (SDL_RenderFillRect with SDL_FRect, SDL_RenderTexture, SDL_SetRenderVSync, SDL_RenderDebugText)
- https://wiki.libsdl.org/SDL3/SDL_CreateWindowAndRenderer (signature, bool return)
- https://wiki.libsdl.org/SDL3/CategoryGPU (SDL_GPU workflow)
- https://wiki.libsdl.org/SDL3_ttf/TTF_RenderText_Blended (length parameter)
- https://raw.githubusercontent.com/libsdl-org/SDL_image/main/docs/README-migration.md (IMG_Init removed)
- https://wiki.libsdl.org/SDL3_mixer/CategoryAPI (MIX_* function names)

These are documentation references; no editor/compiler run is claimed for the skeleton.
