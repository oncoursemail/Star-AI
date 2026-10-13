# blender-brain2-20261013 (wave 2026-10-13): STAR sees Blender on brain 2

Branch `star/blender-brain2-20261013` (from origin/star/next 64c1982), worktree `worktrees/wt-blender-brain2`, board item #92.
PR -> star/next. Evidence: `docs/agents/blender-brain2-20261013/` (images, GLB, report.json).

## Status (23:40Z): code, tests, live run and PR #289 DONE. Not merged (owner / integrator).

## What exists (and what was actually run)
| piece | where | run on brain 2? |
|---|---|---|
| Blender 5.2.2 GUI on the shared virtual display (TurboVNC `:1`, 1920x1080) | `blender-lab.sh start` | yes, many times |
| Official Blender Lab MCP add-on 1.0.3 (needs 5.1+), bound to 127.0.0.1:9876, enabled per session | `blender-lab-startup.py` | yes |
| Lab MCP server (stdio) over ssh, same shape as the Studio connector | `blender-lab.sh mcp-server` | yes, 26 tools listed |
| STAR tool `star_blender` (one tool, 12 actions) + guard + evidence | `star/blender_brain2.py` | yes (demo below) |
| Settings gate `blender_brain2` (off by default; needs `blender_enabled`; `blender_edit` for anything that changes) | `star/desktop_core.py`, `react_shell.py` | unit tests only |
| Chat wiring: `blender_brain2` on -> the chat attaches `star_blender` instead of the local Blender tools | `star/desktop_core.py` | NOT run in a real chat (no model call allowed this wave) |
| Setup script, launcher, startup script | `server/brain2_blender/` (copies in the project folder `server/setup/server2/`) | launcher yes; setup script only written (its steps were done by hand, same commands) |

Not done: a UI toggle for `blender_brain2` in the React frontend (the setting is accepted by the settings API, so it can be set
from the existing settings call; no panel yet). The old local `star_blender_*` tools (PR #68 line) are untouched.

## Findings that differ from the brief
- Brain 2 DOES have a GPU path: `/dev/dri/renderD128` is passed into the container and `glxinfo`/Blender report
  "Mesa Intel UHD Graphics 630 (CFL GT2), OpenGL 4.6 core" (hardware iGPU, not llvmpipe). So no `LIBGL_ALWAYS_SOFTWARE` or
  `MESA_GL_VERSION_OVERRIDE` is needed; Blender starts as-is. (Software GL was never tried; not needed.)
- The Lab add-on's own screenshot tools (`get_screenshot_of_area_as_image`, `..._of_window_as_image`) return an
  all-black image on this display (1574x932, and 1920x1056). STAR therefore takes viewport pictures from the X window
  (`import -window <Blender>` + crop to the 3D region, geometry read from Blender). The window is raised first: the
  Studios share the display with no compositor, and a Studio window above Blender would otherwise be in the picture
  (seen once: a black Studio window covered the viewport).
- The Lab add-on only starts its socket when Blender runs with `--online-mode` (checks `bpy.app.online_access`). The launcher
  passes it for the GUI process only; nothing is written to the preferences.
- `MemoryHigh` on a transient unit WITHOUT swap froze Blender in `mem_cgroup_handle_over_high` (D state) after a heavy
  moment: throttled forever, not killed. The launcher now sets only `MemoryMax=2560M` (+ no swap): a runaway scene kills
  Blender, never a Studio.
- projects.blender.org serves a bot challenge for archive downloads and raw files (403 / "Just a moment"); not bypassed.
  Release assets and the Gitea API work, so the setup script pins the two release files by SHA-256 (add-on zip
  `a7a9da81...`, MCP bundle `d6fe04dd...`).

## Measurements (brain 2, Studios running at the time: 1-3)
- GUI start: window visible 0.79 s after launch; Lab MCP port open 1.95-2.29 s after `start` (3 runs); idle RSS ~500 MB,
  ~650-900 MB with a scene and viewport screenshots.
- Frame draw (3D viewport 1574x932, default cube scene and the lantern, with 2 Studios using CPU): full window draw+swap
  21.5-26 ms/frame (~40-47 fps), 3D region only 6.3-6.8 ms.
- Through STAR (this PC -> ssh -> container -> Lab MCP -> Blender): MCP session up 1.4 s; a `bpy` call 0.2-0.6 s;
  one viewport screenshot (set angle + frame + capture + fetch) ~2-3 s each; Eevee 640x360 preview 2.1-2.6 s
  (Workbench 0.7 s); GLB export 2.7-3.0 s; the whole lantern demo ~22 s.
- Memory coexistence: start refuses below 3000 MB MemAvailable (exit 5) - verified with 3 Studios running (632-1666 MB
  available, nothing started). Blender never ran while free memory was below that; Studios were not touched. It is a
  transient user unit `star-blender` (MemoryMax 2560M, MemorySwapMax 0, RuntimeMaxSec 1800, Nice 5, CPUWeight 50).

## Security model (the Lab add-on runs any Python it is sent)
1. Off by default: `blender_enabled` + `blender_brain2`; `blender_edit` for start/stop/new/open/run_bpy/render/export.
2. The operator's launcher command (ssh ...) is stored in `<home>/blender/brain2.json` or `STAR_BLENDER_BRAIN2_COMMAND`; never
   shown to a model; errors carry only the exception kind.
3. A model never sends raw code to the Lab except `run_bpy`, which passes `check_bpy_code` first (AST allow-list: modules
   bpy/bmesh/mathutils/math/random/colorsys/itertools/functools/collections; only the operator modules object, mesh, curve,
   material, node, transform, collection, uv ...; no open/exec/eval/getattr/dunder names/classes/while; no file or
   path-like strings; no `.filepath`, `.load`, `.save`, `.app`, `.utils`, `.preferences`). It is defence in depth, NOT a
   sandbox (it cannot stop a huge `for` computed at run time).
4. Blender listens on 127.0.0.1 only, only while it runs (on demand, stops by itself after 30 min). Any process running as the
   same user inside that container can still reach the port while Blender is up (the Lab protocol has no authentication).
5. Files: Blender writes only inside the sandbox folder (fixed templates use an environment variable, no path in the repo);
   STAR reads back only validated relative names (`fetch` checks them again on the server: no `..`, one folder level, no
   symlinks, 24 MB).
6. Nothing is uploaded to Roblox; GLB/FBX go to the STAR evidence folder for the Studio importer (manual).
Not exposed on purpose: the Lab tools `execute_blender_code_for_cli` (arbitrary .blend path), `*_for_cli`, `render_*_to_path`,
`jump_*`, `get_blendfile_summary_*`.

## Demo (evidence in docs/agents/blender-brain2-20261013/)
Lantern built by `run_bpy` (3 joined meshes: iron, emissive glass, flame; 636 triangles, 0.54 x 0.54 x 0.87 m): viewport
screenshots `viewport-three_quarter|front|top.png`, Eevee preview `render-three_quarter.png`, `lantern.glb` (24,680 bytes,
read back and parsed: 3 meshes, 636 triangles, KHR_materials_emissive_strength), `gui-window.png` (whole Blender window),
`report.json` (every step with seconds). Not checked: the GLB was not imported into Roblox Studio (that would be an edit in
Studio; the importer is manual and the place is not mine to touch here).

## How to use
```
python -m star.blender_brain2 --home <STAR home> --set-command '["ssh","-o","BatchMode=yes","<brain2>","lxc","exec","<container>","--","sudo","-u","<user>","-H","<bin>/blender-lab.sh"]'
python -m star.blender_brain2 --home <STAR home> --status
python -m star.blender_brain2 --home <STAR home> --edit --call '{"action":"screenshot","scene":"lantern","angles":["front","top"]}'
python -m star.blender_brain2 --home <STAR home> --demo <outdir>      # builds the lantern, needs ~3 GB free on brain 2
# in STAR: settings blender_enabled=true, blender_brain2=true (+ blender_edit=true to let it change scenes)
# always when done:  blender-lab.sh stop   (it also stops itself after 30 minutes)
```
Coordination: while Blender is up it is the top window on display :1 for screenshots, so a Studio dialog (e.g. Auto Recovery)
can be hidden behind it; stop Blender before Studio-lab runs that look at the display. Message #239 told all agents.

## Next
- A Blender panel toggle in the React frontend (blender_brain2).
- Resource planner: count the `star-blender` unit as a capacity user (it holds <= 2.5 GB).
- Optional: private virtual display for Blender (own Xvnc) to remove the window-stacking dependency.
- Roblox side: round-trip the GLB through the importer in a throwaway place and compare scale/orientation.

## Log
- 22:53Z start, claim #92. 22:54 GUI first screenshot. 23:00 add-on + venv installed. 23:06 Lab MCP up, probe over ssh ok.
- 23:11 first demo run: Eevee preview stalled Blender (MemoryHigh throttle) -> removed MemoryHigh. 23:15 demo ok.
- 23:20 black Studio window over Blender in a screenshot -> raise window first. 23:21 final demo evidence.
- Tests: tests/test_blender_brain2_remote.py (67) + tests/test_blender_brain2.py (12) green; full suite see PR.
