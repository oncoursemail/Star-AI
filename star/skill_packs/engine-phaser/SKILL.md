---
name: engine-phaser
description: Phaser 4.x (and 3.90) 2D HTML5 game framework in JS/TS. Use for Phaser scenes, Arcade/Matter physics, input, tweens, v3->v4 migration.
---
# engine-phaser
## Scope
Phaser 4.2.x (stable since April 2026; last v3 is 3.90). Check the project's version first (`package.json` "phaser"); v3 and v4 differ in rendering, tint, masks and FX. Phaser 2/CE code is obsolete.
## Core model
- `new Phaser.Game(config)` owns renderer, loop, scene manager, textures, input.
- Game logic lives in `Phaser.Scene` subclasses: `init(data)` -> `preload()` -> `create(data)` -> `update(time, delta)` (delta in ms).
- Scene systems are properties: `this.add`, `this.physics`, `this.input`, `this.tweens`, `this.time`, `this.cameras`, `this.load`.
- Physics opt-in via config: Arcade (AABB) or Matter (polygons). Browser only.
## Idioms
- Config object: `type: Phaser.AUTO`, `width`, `height`, `scale: { mode: Phaser.Scale.FIT }`, `physics: { default: 'arcade', arcade: { gravity: { x: 0, y: 300 } } }`, `scene: [...]`.
- Physics objects: `this.physics.add.sprite`, `staticGroup`, `group`; `this.physics.add.collider(a, b)` separates, `overlap(a, b, cb)` only detects.
- Input: `this.input.keyboard!.createCursorKeys()`, `obj.setInteractive().on('pointerdown', fn)`.
- Timers with `this.time.delayedCall`, not `setTimeout`; tweens with `this.tweens.add({ targets, x, duration, ease })`.
- Reset state in `init()`; clean listeners on `shutdown`.
- Pool with groups (`maxSize`, `get`, `disableBody(true, true)`).
## Pitfalls
1. Phaser 2/CE: `new Phaser.Game(800, 600, Phaser.AUTO, '', {...})`, `game.add.sprite`, `game.physics.startSystem` are wrong for 3/4.
2. v4 removed `setTintFill()`/`tintFill`: use `setTint(c).setTintMode(Phaser.TintModes.FILL)`.
3. v4 replaced preFX/postFX with `obj.filters.internal` / `filters.external`; Bloom/Shine became `Phaser.Actions.AddEffectBloom/AddEffectShine`.
4. v4 removed `BitmapMask`: use `obj.filters.internal.addMask(maskObj)`; GeometryMask is Canvas-only.
5. v4 removed pipelines: `setPipeline('Light2D')` -> `setLighting(true)`; custom pipelines become render nodes.
6. v4 `Geom.Point` removed (use `Phaser.Math.Vector2`); `Math.TAU` is now 2*PI; `Math.PI2` removed; `Struct.Set/Map` -> native.
7. v4 DynamicTexture/RenderTexture buffer draws: call `render()`.
8. v4 `roundPixels` default false; use `pixelArt: true` for pixel art. Mesh, Plane, Camera3D removed.
9. 3.60+: `this.add.particles(x, y, key, config)`; `createEmitter` is gone. Timelines via `this.add.timeline`.
10. Static Arcade bodies do not follow scale/position changes: call `refreshBody()`.
11. `body.blocked.down` (world/tiles) vs `body.touching.down` (bodies); Arcade and Matter bodies never collide.
12. TS: `this.input.keyboard` is nullable; serve over http, not file.
## Roblox to Phaser
- Workspace tree -> scene display list / `Container`
- Part -> `this.physics.add.image` or shape with Arcade body
- Model -> `Container` or `Group`
- LocalScript -> Scene class; ModuleScript -> ES module; server Script -> none (add your own backend)
- RemoteEvent -> WebSocket lib; DataStore -> `localStorage`/backend
- Heartbeat -> `update(time, delta)`; TweenService -> `this.tweens.add`
- Attributes -> `setData/getData`; tags -> groups or data keys
- ScreenGui -> HUD scene via `this.scene.launch('HUD')`
- UserInputService -> `this.input`; task.wait -> `this.time.delayedCall`
- Studio playtest -> `npm run dev`; ship -> `npm run build`
## Skeleton
```ts
import Phaser from 'phaser';

class Play extends Phaser.Scene {
  private player!: Phaser.Types.Physics.Arcade.SpriteWithDynamicBody;
  private cursors!: Phaser.Types.Input.Keyboard.CursorKeys;
  private score = 0;
  constructor() { super('Play'); }
  init() { this.score = 0; }
  preload() { this.load.image('hero', 'assets/hero.png'); }
  create() {
    this.player = this.physics.add.sprite(100, 300, 'hero').setCollideWorldBounds(true);
    this.cursors = this.input.keyboard!.createCursorKeys();
  }
  update(_time: number, _delta: number) {
    const vx = this.cursors.left.isDown ? -200 : this.cursors.right.isDown ? 200 : 0;
    this.player.setVelocityX(vx);
    if (this.cursors.up.isDown && this.player.body.blocked.down) this.player.setVelocityY(-330);
  }
}

new Phaser.Game({
  type: Phaser.AUTO, width: 800, height: 600,
  physics: { default: 'arcade', arcade: { gravity: { x: 0, y: 400 } } },
  scene: [Play],
});
```
## Verification
Run `npm install` then `npm run dev` (Vite template from `npm create @phaserjs/game@latest`) and check the browser console; `npx tsc --noEmit` for types; `npm run build` for a release bundle. Report only checks you actually ran.
