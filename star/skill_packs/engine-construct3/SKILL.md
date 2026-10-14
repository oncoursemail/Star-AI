---
name: engine-construct3
description: Construct 3 (r495 stable, 2026) event sheets plus JavaScript/TypeScript scripting; use for any Construct 3 game, event sheet or runtime script question.
---
# engine-construct3
## Scope
Construct 3, current stable r495.2 (Aug 2026), LTS r449.x (to end of 2026). Check the project's release number first: r450+ removed SDK v1 addons, NW.js export and flat export mode.
## Core model
Project -> layouts (levels) -> layers -> instances of object types (Sprite, Text, Tilemap...). Behaviors (Platform, 8 Direction, Bullet, Solid, Physics, Tween, Timer) add movement/logic. Event sheets run top to bottom every tick; conditions pick instances, actions apply to picked ones. Scripts are ES modules: the main script runs once, `runOnStartup(async runtime => ...)` gets the IRuntime before objects exist; per tick order is "pretick" -> behaviors -> "tick" -> event sheets -> "tick2".
## Idioms
- Main script: in runOnStartup add a "beforeprojectstart" listener, and inside that add the "tick" listener.
- Move by `runtime.dt` (seconds): `inst.x += speed * runtime.dt`.
- Object class vs instance: `runtime.objects.Player.getFirstInstance()`, `getAllInstances()`, `instances()`; spawn with `runtime.objects.Enemy.createInstance("Game", x, y)`.
- Instance data: `inst.instVars.health`, behaviors `inst.behaviors.Platform`, tags `inst.hasTag("enemy")`.
- Input: `runtime.keyboard.isKeyDown("ArrowLeft")` (KeyboardEvent.code strings); runtime "pointerdown"/"keydown" events.
- Collisions: `a.testOverlap(b)`, `inst.testOverlapSolid()`.
- Globals `runtime.globalVars.Score`; `runtime.callFunction("Name")`.
- Storage: `await runtime.storage.setItem(k, v)` / `getItem(k)`.
- TypeScript: annotate `runtime: IRuntime`, instance types `InstanceType.Player`, use `!` or guards for nullable `getFirstInstance()`.
## Pitfalls
1. Accessing instances inside runOnStartup: none exist yet; use "beforeprojectstart".
2. `runtime.objects.Sprite.x` is wrong: the object class has no position; get an instance first.
3. Construct 2 SDK code (`cr.plugins_`, `cr.behaviors`, `this.runtime.tickcount`) does not run in C3.
4. Own loops with requestAnimationFrame or setInterval: use the runtime "tick" event and `runtime.dt`.
5. `angle` is radians in script (event sheets use degrees); use `angleDegrees` when porting.
6. `isKeyDown(37)` numeric codes are deprecated; use "ArrowLeft", "KeyW", "Space".
7. `localStorage`/`window`/`document` are missing in worker mode; use `runtime.storage` and runtime events.
8. Scripts are modules: a top-level function in one file is not global in another.
9. Inline event-sheet scripts cannot `import`; use a script with Purpose "Imports for events".
10. Destroy while iterating: loop over `getAllInstances()`, not `instances()`.
11. SDK v1 third-party addons stop the project opening on r450+; update addons or stay on r449 LTS.
## Roblox to Construct 3
Workspace -> layout and layers; Part -> Sprite / 3D shape; Model -> hierarchy or template
Script/LocalScript -> event sheet or main script "tick"; ModuleScript -> module with export/import
RemoteEvent -> Multiplayer plugin messages (peer-to-peer, host authoritative)
DataStore -> runtime.storage / Local Storage plugin / cloud save service
Humanoid -> Platform or 8 Direction behavior; Heartbeat -> "tick" with runtime.dt
TweenService -> Tween behavior; CollectionService -> instance tags or families; Attributes -> instVars
ScreenGui -> UI layer with parallax 0 plus Text/Button; UserInputService -> Keyboard/Mouse/Touch
task.wait -> System Wait action or await; Studio playtest -> Preview; release -> Export
## Skeleton
```js
// main.js, Purpose: Main script. Objects: Player, Coin (Sprites), ScoreText (Text), Keyboard plugin.
let score = 0;
runOnStartup(async runtime => {
  runtime.addEventListener("beforeprojectstart", () => {
    runtime.addEventListener("tick", () => tick(runtime));
  });
});
function tick(runtime) {
  const p = runtime.objects.Player.getFirstInstance();
  if (!p) return;
  const kb = runtime.keyboard, s = 240 * runtime.dt;
  if (kb.isKeyDown("ArrowLeft")) p.x -= s;
  if (kb.isKeyDown("ArrowRight")) p.x += s;
  if (kb.isKeyDown("ArrowUp")) p.y -= s;
  if (kb.isKeyDown("ArrowDown")) p.y += s;
  for (const c of runtime.objects.Coin.getAllInstances()) {
    if (p.testOverlap(c)) { c.destroy(); score++; }
  }
  const t = runtime.objects.ScoreText.getFirstInstance();
  if (t) t.text = "Score: " + score;
}
```
## Verification
Open the project in the editor, Preview (F5), read the browser console (F12); Debug preview inspects instances. TypeScript errors show in the code editor. Say "not run" unless a preview was observed.
