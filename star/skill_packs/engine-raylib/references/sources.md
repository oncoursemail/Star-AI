# Sources for engine-raylib

Official documentation reviewed 2026-10-13 (accessed by web, not by a live engine run):

- https://raw.githubusercontent.com/raysan5/raylib/master/CHANGELOG (current release raylib 6.0, 23 April 2026; 6.0 removed/redesigned functions; 6.2 not yet released)
- https://raw.githubusercontent.com/raysan5/raylib/6.0/src/raylib.h (6.0 prototypes: UpdateModelAnimation float frame, keyframeCount, DrawCircleGradient Vector2, SetSoundPan range, config flags)
- https://raw.githubusercontent.com/raysan5/raylib/5.5/src/raylib.h (5.5 signatures for comparison: int frame, UpdateModelAnimationBones, DrawModelPoints)
- https://github.com/raysan5/raylib/releases (release list and 6.0 key changes)
- https://github.com/raysan5/raylib/wiki/Working-for-Web-(HTML5) (emcc flags, ASYNCIFY, preload-file, WebGL2 flag)
- https://github.com/raysan5/raygui/releases (raygui 5.0 latest; int returns and by-pointer values since 4.0)

These are documentation references; no editor/compiler run is claimed for the skeleton.
