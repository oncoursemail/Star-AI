---
name: engine-rpgmaker-mz
description: RPG Maker MZ (1.10.0, core 1.9/1.10) JavaScript plugins: annotations, registerCommand, aliasing, Scene/Window/Game classes, saves. Use for MZ or MV-to-MZ plugin work.
---
# engine-rpgmaker-mz
## Scope
RPG Maker MZ, editor 1.10.0 (Feb 2026); core scripts rmmz_*.js on PixiJS 5. Check the project's version first (js/rmmz_core.js header and Utils.RPGMAKER_VERSION) and whether it is MV (rpg_*.js) instead. RPG Maker Unite (Unity/C#) cannot run MZ plugins.
## Core model
Plugins in js/plugins/*.js load in Plugin Manager order and patch core prototypes. Game_* objects hold saved state ($gameParty, $gamePlayer, $gameMap, $gameVariables, $gameSystem). Scene_* classes run the frame loop (SceneManager.goto/push/pop); Window_* and Sprite_* draw. $data* globals are read-only database JSON. Event commands run in Game_Interpreter.
## Idioms
- Header block starting with /*: containing @target MZ, @plugindesc, @author, @help, @param/@type/@default, @command plus @arg, and @base/@orderAfter/@orderBefore for dependencies.
- `PluginManager.registerCommand(pluginName, "cmd", function (args) {...})`: args is an object of strings; `this` is the Game_Interpreter when using a normal function.
- `const pluginName = "MyPlugin"` must equal the file name MyPlugin.js.
- `PluginManager.parameters(pluginName)` returns strings: use Number(), `=== "true"`, JSON.parse for struct and array types.
- Alias: `const _Scene_Map_start = Scene_Map.prototype.start; Scene_Map.prototype.start = function () { _Scene_Map_start.apply(this, arguments); ... };`
- Windows: `new Window_Base(new Rectangle(x, y, w, h))`, `this.addWindow(win)` in a scene, `this.contents.clear()`, `this.drawText(text, x, y, width, align)`.
- State: `$gameVariables.setValue(id, v)`, `$gameSwitches.setValue(id, true)`, `$gameParty.gainGold(n)`, `$gameParty.gainItem($dataItems[id], n)`.
- Input: `Input.isTriggered("ok")`, `Input.isPressed("left")`.
- Plugin save data: fields on $gameSystem, defaulted again after load.
## Pitfalls
1. MV plugin commands (`Game_Interpreter.prototype.pluginCommand` with string arrays, `args[0]`) are the deprecated path; MZ uses @command/@arg and registerCommand with object args.
2. Missing @target MZ makes the editor treat the file as an MV plugin.
3. MV window constructor `(x, y, width, height)` is wrong in MZ; pass a Rectangle.
4. MZ core is rmmz_*.js, not MV rpg_*.js; never edit core files.
5. Parameters and args are strings; "false" is truthy.
6. Plugin name differs from the file name, so commands silently do nothing.
7. Arrow functions in registerCommand lose the interpreter `this`.
8. Classes saved in game objects must be on window (JsonEx restores by window[name]); a class hidden in the IIFE loads as a plain object.
9. Overriding a method without calling the saved original breaks plugins loaded earlier.
10. Writing progress into $data* objects: they are not saved.
11. 1.9.0 made icon/face sizes configurable, 1.10.0 renamed defaultIconWidth/defaultFaceWidth: use ImageManager.standardIconWidth / standardFaceWidth (and Height), not 32 or 144.
12. require("fs") exists only in the desktop NW.js build.
## Roblox to RPG Maker MZ
Workspace -> $gameMap plus events; Part -> tile or event graphic; Model -> event pages or common event
Script/LocalScript -> plugin that aliases core methods; ModuleScript -> plugin with @base exposing globals on window
RemoteEvent -> none (single player); DataStore -> save files via DataManager.saveGame
Players -> $gameParty and $gamePlayer; Humanoid -> Game_Actor stats plus Game_Player movement
Heartbeat -> alias Scene_Map.prototype.update or a parallel event; TweenService -> Move Picture / movement routes
CollectionService/Attributes -> notetags (meta), variables, switches
ScreenGui -> Window_* classes or pictures; UserInputService -> Input and TouchInput
task.wait -> Wait event command (frames); Studio playtest -> Playtest; release -> Deployment
## Skeleton
```js
/*:
 * @target MZ
 * @plugindesc Gives gold from a plugin command.
 * @author you
 * @command give
 * @arg amount
 * @type number
 * @default 100
 */
(() => {
  "use strict";
  const pluginName = "GiveGold"; // file js/plugins/GiveGold.js
  PluginManager.registerCommand(pluginName, "give", function(args) {
    $gameParty.gainGold(Number(args.amount));
  });
  const _Scene_Map_start = Scene_Map.prototype.start;
  Scene_Map.prototype.start = function() {
    _Scene_Map_start.apply(this, arguments);
    console.log(pluginName + " ready");
  };
})();
```
## Verification
Enable the plugin in Plugin Manager, add the Plugin Command to an event, Playtest (Ctrl+R), read errors in DevTools (F8). Say "not run" unless the playtest was observed.
