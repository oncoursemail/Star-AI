---
name: engine-heaps
description: Heaps 2.1 (Haxe 4.3, HashLink/JS) game framework idioms and version traps. Use when writing or fixing Heaps code (hxd.App, h2d, h3d, hxd.Res).
---
# engine-heaps
## Scope
Heaps 2.1.1 on Haxe 4.3.7, HashLink 1.16 or the JS/WebGL target. Check the project's version first (haxelib.json, `haxelib list`, hxml libs); Heaps 1.x code differs.

## Core model
- A game is a class extending `hxd.App`; `new Main()` from `static function main()`.
- Override `init()` once and `update(dt:Float)` every frame; dt is in seconds.
- `s2d` (h2d.Scene) and `s3d` (h3d.scene.Scene) are object trees; parent is the last constructor argument.
- `hxd.Res` is a compile-time typed tree of the `res/` folder; a loader must be initialized first.
- No built-in physics, no networking service; collision math only (h2d.col, h3d.col), hxbit for replication.

## Idioms
- `hxd.Res.initEmbed()` in `main()` before `new Main()` (use `initLocal()` only on HashLink for live reload).
- Sprites: `new h2d.Bitmap(hxd.Res.hero.toTile(), s2d)`; colored box: `h2d.Tile.fromColor(0xFF0000, w, h)`.
- Animation: `new h2d.Anim(tile.split(4), 10, s2d)`.
- Text: `new h2d.Text(hxd.res.DefaultFont.get(), s2d)` then set `.text`.
- Input: `hxd.Key.isDown(hxd.Key.LEFT)`, `hxd.Key.isPressed(hxd.Key.SPACE)`; clicks via `h2d.Interactive(w, h, parent)` and `onClick`.
- Overlap: `a.getBounds().intersects(b.getBounds())`.
- Fixed virtual resolution: `s2d.scaleMode = LetterBox(320, 180)`.
- 3D: `new h3d.scene.Mesh(new h3d.prim.Cube(1, 1, 1, true), s3d)`; Z is up.
- Save: `hxd.Save.save(data, "slot")`, `hxd.Save.load(defaults, "slot")`.
- Sound: `hxd.Res.sfx.jump.play()`.

## Pitfalls
1. Heaps 2.0 made `h3d.Vector` 3 components; use `h3d.Vector4` for x,y,z,w.
2. `h2d.Sprite` no longer exists (renamed `h2d.Object` in 1.5); `hxd.Stage` is `hxd.Window`.
3. `update(dt)` dt is seconds, not frames; use speed in units per second.
4. Accessing `hxd.Res.*` before `initEmbed/initLocal/initPak` crashes with a null loader; `initLocal` does not work on JS.
5. Override as `override function init()` and `override function update(dt:Float)`; adding `public` causes a visibility error.
6. HashLink needs `-lib hlsdl` or `-lib hldx` (DX12: `-lib hldx -D dx12`) in the hxml plus the native libs.
7. Buffers were unified into `h3d.Buffer` in 2.0; old index/managed buffer code from 1.x tutorials will not compile.
8. `h2d.Object.move(dx, dy)` moves along the object's rotation; use `x += ...` for axis movement.
9. Asset file names must be valid Haxe identifiers to get typed `hxd.Res` fields; rebuild after adding files.
10. Haxe 5 is only a preview; do not assume Haxe 5 syntax or features.
11. On current master `h3d.scene.CameraController` is abstract; check the source of the pinned version before instantiating it.

## Roblox to Heaps
- Workspace -> `s3d` tree; ScreenGui -> `s2d` (drawn over 3D)
- Part -> `h3d.scene.Mesh` with `h3d.prim.Cube`
- RunService.Heartbeat -> `override function update(dt)`
- UserInputService -> `hxd.Key`, `hxd.Pad`, `h2d.Interactive`
- DataStore -> `hxd.Save` (local only)
- RemoteEvent -> hxbit `@:rpc` over `hxd.net.Socket` (self-hosted)
- ModuleScript -> Haxe class + `import`
- task.wait -> accumulate a timer in `update`, or `haxe.Timer.delay`
- Studio playtest -> F5 in VS Code or `haxe compile.hxml` then `hl game.hl`

## Skeleton
```haxe
class Main extends hxd.App {
    var player : h2d.Bitmap;
    var label : h2d.Text;
    var score = 0;

    override function init() {
        s2d.scaleMode = LetterBox(320, 180);
        player = new h2d.Bitmap(h2d.Tile.fromColor(0x3080FF, 12, 12), s2d);
        label = new h2d.Text(hxd.res.DefaultFont.get(), s2d);
        label.text = "Score: 0";
    }

    override function update(dt : Float) {
        var speed = 160.0;
        if (hxd.Key.isDown(hxd.Key.LEFT)) player.x -= speed * dt;
        if (hxd.Key.isDown(hxd.Key.RIGHT)) player.x += speed * dt;
        if (hxd.Key.isPressed(hxd.Key.SPACE)) {
            score++;
            label.text = 'Score: $score';
        }
    }

    static function main() {
        hxd.Res.initEmbed();
        new Main();
    }
}
```

## Verification
Build with `haxe compile.hxml` (hxml has `-cp src -lib heaps -lib hlsdl -hl game.hl -main Main`) and run `hl game.hl`, or build `-js game.js` and open the HTML page through a local web server. Report compile errors verbatim. Do not claim it ran unless you saw the window.
