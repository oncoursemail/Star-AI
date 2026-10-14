# MonoGame and FNA (plus KNI): STAR engine research
**Verified 2026-10-13 against official docs. Current stable: MonoGame 3.8.6 (2026-10-07); FNA 26.10 (2026-10-01); KNI v4.3.9001 (2026-08-22).** MonoGame and FNA are free and open source under the Microsoft Public License (Ms-PL); KNI license not re-checked (assumed Ms-PL lineage, unverified).

All three re-implement the Microsoft XNA 4.0 API (`Microsoft.Xna.Framework.*` namespaces) in C#/.NET:
- **MonoGame**: the most used; own content pipeline; many platforms incl. Android/iOS and consoles (vendor access); 3.8.5 added DesktopVK (Vulkan) and WindowsDX12 targets, 3.8.6 made the code-based **Content Builder** the recommended pipeline.
- **FNA**: strict XNA 4.0 Refresh accuracy, one project for all desktop platforms, FNA3D (Vulkan/D3D11/Metal/OpenGL via SDL), releases monthly as YY.MM; no official content tool.
- **KNI**: MonoGame/XNA-Touch derivative with web (Blazor/WebGL) and VR targets.

## At a glance
| | |
|---|---|
| Best for | Code-first 2D games in C# (Celeste, Stardew Valley, Terraria-era lineage); porting XNA games; programmers who want a framework, not an editor |
| Weak at | No scene editor, no built-in physics/UI/networking, 3D is low-level; web needs KNI (MonoGame has no official web target) |
| Language(s) | C# (.NET; Content Builder template asks for .NET 10 SDK; FNA recommends .NET 8 for new games); HLSL `.fx` effects |
| Editor / tooling | Any C# IDE (Visual Studio, VS Code + C# Dev Kit, Rider); `dotnet new` templates; Content Builder (3.8.6+) or legacy MGCB Editor (`dotnet tool restore`) |
| Platforms (export) | MonoGame: Windows (DX11, DX12), Desktop GL (Win/macOS/Linux), DesktopVK (3.8.5+), Android, iOS, Xbox/PlayStation/Switch/Switch 2 with vendor access. FNA: Win/macOS/Linux, consoles (Xbox GDK, Switch, PS5), iOS/tvOS; Android unofficial. KNI: desktop, Android, iOS, browsers (WebGL), Oculus |
| License / cost | Ms-PL, free |
| Roblox-likeness | low: no world tree, editor or online services; you write Update/Draw code by hand |

## Architecture and lifecycle
Subclass `Game`:
```
Program.Main -> new Game1().Run()
  Game1()          constructor: create GraphicsDeviceManager, set Content.RootDirectory, window options
  Initialize()     non-graphics init; base.Initialize() calls LoadContent()
  LoadContent()    create SpriteBatch, Content.Load<T>(...)
  loop:
    Update(GameTime)   input, logic (fixed step 1/60 s by default: IsFixedTimeStep = true)
    Draw(GameTime)     GraphicsDevice.Clear + SpriteBatch.Begin/Draw/End
  UnloadContent()  (ContentManager disposes loaded assets on Dispose)
```
- `IsFixedTimeStep` (default true) + `TargetElapsedTime` (default 1/60 s): Update may run several times per Draw to catch up; `gameTime.IsRunningSlowly` signals lag.
- `GameComponent`/`DrawableGameComponent` + `Components.Add(...)` for reusable subsystems; `Services` for service locator.
- `GraphicsDeviceManager`: `PreferredBackBufferWidth/Height`, `IsFullScreen`, `SynchronizeWithVerticalRetrace`, `ApplyChanges()`.
- MonoGame 3.8.x templates split code into a shared game library + per-platform head projects (e.g. `MyGame.Core`, `MyGame.DesktopGL`) in the newer StartKit templates; the classic `mgdesktopgl` template is a single project.

## Project layout
Classic (`dotnet new mgdesktopgl -n MyGame`):
```
MyGame/
  MyGame.csproj            # PackageReference MonoGame.Framework.DesktopGL, MonoGame.Content.Builder.Task
  Program.cs  Game1.cs
  Content/Content.mgcb     # legacy MGCB content project (edit with MGCB Editor)
  .config/dotnet-tools.json  # mgcb tools; run `dotnet tool restore`
```
Content Builder (3.8.6+, `dotnet new mgblankmgcbstartkit -n MyGame`, needs .NET 10 SDK):
```
MyGame.Content/
  Assets/                  # source files (png, wav, spritefont, fx ...)
  Builder/Builder.cs       # class Builder : ContentBuilder { override GetContentCollection() }
  BuildContent.targets     # imported by platform projects; builds content during game build
  MyGame.Content.csproj
MyGame.Core/               # shared game code (sets Content.RootDirectory = "Content")
MyGame.DesktopGL/          # platform head; <MonoGamePlatform>DesktopGL</MonoGamePlatform>
```
Output lands in `bin/<cfg>/net10.0/Content/*.xnb`. Load names are the path under `Assets/` without extension: `Assets/Textures/ball.png` -> `Content.Load<Texture2D>("Textures/ball")`.

Builder rules (from the docs):
```csharp
public override IContentCollection GetContentCollection()
{
    var contentCollection = new ContentCollection();
    contentCollection.Include<WildcardRule>("*");                 // everything with default importer/processor
    contentCollection.Exclude<WildcardRule>("Fonts/*.ttf");       // raw fonts referenced by .spritefont
    return contentCollection;
}
```
Explicit importer/processor: `contentCollection.Include("Textures/hero.png", new TextureImporter(), new TextureProcessor { PremultiplyAlpha = false });`.

FNA: `git clone --recursive` FNA, reference `FNA.Core.csproj` (.NET 8) from your game csproj, copy **fnalibs** (SDL3/FNA3D/FAudio native libs) next to the executable; assets usually loaded raw (PNG/WAV/OGG via `Content.Load` which FNA accepts for many raw formats; effects precompiled with FXC to `.fxb`).

## Scripting idioms
```csharp
protected override void Update(GameTime gameTime)
{
    var kb = Keyboard.GetState();
    if (kb.IsKeyDown(Keys.Escape)) Exit();
    float dt = (float)gameTime.ElapsedGameTime.TotalSeconds;
    Vector2 dir = Vector2.Zero;
    if (kb.IsKeyDown(Keys.Left)) dir.X -= 1;
    if (kb.IsKeyDown(Keys.Right)) dir.X += 1;
    if (dir != Vector2.Zero) dir.Normalize();
    _pos += dir * Speed * dt;
    base.Update(gameTime);
}
```
- Edge detection: keep `_prevKb` and compare `kb.IsKeyDown(k) && _prevKb.IsKeyUp(k)` (no built-in "pressed this frame").
- Drawing:
```csharp
GraphicsDevice.Clear(Color.CornflowerBlue);
_spriteBatch.Begin(samplerState: SamplerState.PointClamp);   // pixel art
_spriteBatch.Draw(_tex, _pos, null, Color.White, rotationRadians, origin, scale, SpriteEffects.None, 0f);
_spriteBatch.DrawString(_font, $"Score: {_score}", new Vector2(10, 10), Color.White);
_spriteBatch.End();
```
- Collision: `Rectangle.Intersects`, `Rectangle.Contains`, `BoundingBox`/`BoundingSphere` for 3D.
- Camera: pass `transformMatrix: Matrix.CreateTranslation(-camPos.X, -camPos.Y, 0) * Matrix.CreateScale(zoom)` to `SpriteBatch.Begin`.
- Audio: `SoundEffect` (`Content.Load<SoundEffect>("hit").Play()`), `Song` + `MediaPlayer.Play(song)`.
- Runtime textures without content: `Texture2D.FromStream(GraphicsDevice, stream)` (XNA API); 1x1 white pixel via `new Texture2D(GraphicsDevice, 1, 1)` + `SetData(new[] { Color.White })`.

## Pitfalls (what AI answers get wrong)
1. **Content pipeline generation**: 3.8.6 recommends the code-based **Content Builder** (`Builder : ContentBuilder`, `GetContentCollection`, `Include<WildcardRule>`); `.mgcb` + MGCB Editor is now "legacy" (still works). Older answers mention the MonoGame 3.7 installer, "Pipeline Tool" (`Pipeline.exe`) or Visual Studio extensions: obsolete since 3.8 (tools come from NuGet/`dotnet tool`).
2. **Load names have no extension** and are relative to `Content.RootDirectory`: `Content.Load<Texture2D>("player")`, not `"player.png"` or `"Content/player.xnb"`.
3. **Templates**: install with `dotnet new install MonoGame.Templates.CSharp`; IDs `mgdesktopgl`, `mgwindowsdx`, `mgandroid`, `mgios`, `mgblankmgcbstartkit` (Content Builder). DesktopVK/WindowsDX12 (3.8.5+) are set via `<MonoGamePlatform>` + package swap (`MonoGame.Framework.Native` + `MonoGame.Runtime.*`).
4. **Rotation is in radians** (`SpriteBatch.Draw` rotation; 3.8.6 docs clarify). Use `MathHelper.ToRadians`.
5. **Everything drawn must be between `Begin` and `End`**; calling `Begin` twice without `End` throws. Default `SpriteBatch` uses premultiplied alpha (`BlendState.AlphaBlend`); textures built by the pipeline are premultiplied by default.
6. **No input "pressed" events**: compare current vs previous `KeyboardState`/`MouseState`/`GamePadState`.
7. **Fixed timestep surprises**: Update runs at 60 Hz by default even on 144 Hz monitors; set `IsFixedTimeStep = false` and `graphics.SynchronizeWithVerticalRetrace` to taste, and always scale by `ElapsedGameTime`.
8. **Resolution changes** need `_graphics.ApplyChanges()` after setting back buffer size (and not inside Draw).
9. **XNA-only APIs that do not exist**: `Microsoft.Xna.Framework.Net`, `GamerServices` (Xbox LIVE), XACT `.xap` audio (MonoGame has partial XACT; FNA supports XACT). `StorageContainer` was re-added in MonoGame 3.8.6 but is not the usual way to save on desktop.
10. **Effects/shaders**: MonoGame compiles `.fx` with MGFX per platform via the pipeline; FNA needs FXC-compiled DXBC effect binaries (one file for all platforms). Shader model differences break DX vs GL builds.
11. **FNA vs MonoGame confusion**: FNA has no `MonoGame.Framework.*` NuGet packages, no MGCB requirement, and needs fnalibs; MonoGame extension APIs (e.g. `Texture2D.FromFile`, 3.8.6 `Vector3.TransformCoord`, `Span` overloads) are not in FNA. FNA extensions are separate and clearly marked.
12. **Build command change (3.8.6)**: build scripts for MonoGame's own native build use `--mg-arch`; projects referencing NuGet are unaffected.
13. **Pre-3.8.4 projects**: follow the 3.8.x update guide (package names/versions must all match; `MonoGame.Content.Builder.Task` version must equal the framework version).

## Rendering
- 2D: `SpriteBatch` (sort modes `Deferred`, `BackToFront`, `FrontToBack`, `Texture`; `Immediate` breaks batching), `SpriteFont` (built from `.spritefont` XML via pipeline), `RenderTarget2D` for low-res pixel-perfect rendering.
- 3D: `BasicEffect`, `Model` (FBX/OBJ via pipeline; 3.8.6 fixed FBX sideways import), `VertexBuffer`/`IndexBuffer`, custom `Effect` (HLSL .fx). Skinned animation needs custom processors/libraries.
- Backends: DesktopGL (OpenGL via SDL2), WindowsDX (DX11), WindowsDX12 and DesktopVK (3.8.5+, intended long-term replacements), 3.8.6 adds a Native OpenGL backend. FNA3D: Vulkan, D3D11, Metal, OpenGL.

## Physics
No built-in support. Common community choices: Aether.Physics2D (Box2D port for C#), Box2D.NET, BEPUphysics v2 (3D). Simple games use `Rectangle.Intersects`.

## Input
- `Keyboard.GetState()`, `Mouse.GetState()` (`Position`, `LeftButton == ButtonState.Pressed`, `ScrollWheelValue` cumulative), `GamePad.GetState(PlayerIndex.One)` (3.8.5: up to 8 controllers), `TouchPanel.GetState()` on mobile.
- Text input: `Window.TextInput += (s, e) => ...` (MonoGame extension; FNA uses `TextInputEXT`).

## UI
No built-in UI. Options: draw with `SpriteBatch`/`SpriteFont`; community libraries Gum (Gum.MonoGame, used in MonoGame's own 2D tutorial series, unverified), Myra, ImGui.NET with a MonoGame renderer, Apos.Gui.

## Networking and multiplayer
None built in (XNA's `Net` namespace not implemented). Use LiteNetLib, Lidgren, Steamworks.NET, or `System.Net.Sockets`/`HttpClient` from .NET.

## Save data
Plain .NET: `System.Text.Json` + `File.WriteAllText` into `Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData)` (or `LocalApplicationData`). `TitleContainer.OpenStream` for read-only bundled files. `StorageContainer` exists in FNA and again in MonoGame 3.8.6 (console-style save areas).

## Performance
- One `SpriteBatch.Begin/End` pair per layer; sort by texture; use atlases. Avoid `SpriteSortMode.Immediate`.
- Avoid per-frame allocations (LINQ, string concatenation in `DrawString` every frame on hot paths, closures) to reduce GC pauses; cache strings when values unchanged.
- Use `RenderTarget2D` for static layers; dispose textures you create yourself.
- NativeAOT publishing is supported (3.8.4 included AOT fixes; FNA has a NativeAOT appendix).

## Build and export
- `dotnet run` / `dotnet build -c Release`; ship via `dotnet publish -c Release -r win-x64 --self-contained` (or `linux-x64`, `osx-arm64`); content is copied to the output `Content/` folder.
- Android/iOS via platform templates and .NET workloads; consoles need vendor developer access and private repos.
- FNA: publish your game with `FNA.Core` + fnalibs per OS (see FNA "Distributing FNA Games"). KNI: BlazorGL target for browsers.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| `ContentLoadException: file not found` | Asset not built, wrong name, or extension in name | Include asset in Content Builder/MGCB; load `"Textures/ball"` without extension; check `Content.RootDirectory` |
| MGCB Editor won't open | Tools not restored | `dotnet tool restore` (legacy pipeline) |
| Black window, nothing drawn | Draw before `Begin`, or forgot `End` | Wrap draws in `Begin`/`End` |
| Sprite rotates wildly | Degrees passed as radians | `MathHelper.ToRadians(deg)` |
| Jump triggers every frame while held | No edge detection | Compare with previous `KeyboardState` |
| Movement speed differs by machine | Not using elapsed time / fixed step off | Multiply by `ElapsedGameTime.TotalSeconds` |
| Blurry pixel art | Linear sampling | `SamplerState.PointClamp` in `Begin` |
| Dark fringes around sprites | Non-premultiplied texture with AlphaBlend | Keep pipeline premultiply on, or use `BlendState.NonPremultiplied` |
| Resolution change ignored | Missing `ApplyChanges()` | Call after setting back buffer size |
| FNA game crashes at start (DllNotFoundException) | fnalibs not next to exe | Copy fnalibs for the OS/arch |
| Package version mismatch errors | Framework and builder task versions differ | Use the same 3.8.x version for all MonoGame packages |

## Mapping from Roblox
| Roblox | MonoGame / FNA | Notes |
|---|---|---|
| Workspace / Instance tree | Your own lists of objects / scene classes | No hierarchy built in |
| Part | Your class with `Rectangle`/`Vector2` + texture drawn in Draw | |
| Model | `Model` from content pipeline (3D) or composite class | |
| Script / LocalScript | `Update`/`Draw` overrides, `GameComponent`s | |
| ModuleScript | C# classes/namespaces | |
| RemoteEvent | LiteNetLib/Steamworks messages | Not built in |
| DataStore | JSON file in AppData | Local only |
| Players | Your player class(es) | |
| Humanoid | Your movement/state code | |
| RunService.Heartbeat | `Update(GameTime)` | Fixed 60 Hz by default |
| RenderStepped | `Draw(GameTime)` | |
| TweenService | Manual lerp (`Vector2.Lerp`, `MathHelper.Lerp`) with timers | Community tween libs exist |
| CollectionService tags | Interfaces / enum flags / lists per type | |
| Attributes | C# properties | |
| ScreenGui | SpriteBatch pass drawn last without camera transform; Gum/Myra | |
| UserInputService | `Keyboard/Mouse/GamePad.GetState()` | Poll, compare with previous |
| task.wait | Accumulate `ElapsedGameTime`; `async` is possible but not tied to frames | |
| Studio playtest | `dotnet run` / F5 | |
| Publishing | `dotnet publish`, then itch.io/Steam yourself | |

## Minimal example
MonoGame 3.8.6 (DesktopGL), C#: move with arrows/WASD, collect coins, show score. Expects a `SpriteFont` asset named `Fonts/Score` (a `.spritefont` file in `Assets/Fonts/` built by the Content Builder or MGCB).
```csharp
using System.Collections.Generic;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Microsoft.Xna.Framework.Input;

public class Game1 : Game
{
    private readonly GraphicsDeviceManager _graphics;
    private SpriteBatch _spriteBatch;
    private Texture2D _pixel;
    private SpriteFont _font;
    private Vector2 _player = new(100, 100);
    private readonly List<Rectangle> _coins = new();
    private int _score;
    private const float Speed = 250f;

    public Game1()
    {
        _graphics = new GraphicsDeviceManager(this);
        Content.RootDirectory = "Content";
        IsMouseVisible = true;
    }

    protected override void Initialize()
    {
        for (int i = 0; i < 5; i++) _coins.Add(new Rectangle(150 + i * 100, 300, 16, 16));
        base.Initialize();
    }

    protected override void LoadContent()
    {
        _spriteBatch = new SpriteBatch(GraphicsDevice);
        _pixel = new Texture2D(GraphicsDevice, 1, 1);
        _pixel.SetData(new[] { Color.White });
        _font = Content.Load<SpriteFont>("Fonts/Score");
    }

    protected override void Update(GameTime gameTime)
    {
        var kb = Keyboard.GetState();
        if (kb.IsKeyDown(Keys.Escape)) Exit();

        float dt = (float)gameTime.ElapsedGameTime.TotalSeconds;
        Vector2 dir = Vector2.Zero;
        if (kb.IsKeyDown(Keys.Left) || kb.IsKeyDown(Keys.A)) dir.X -= 1;
        if (kb.IsKeyDown(Keys.Right) || kb.IsKeyDown(Keys.D)) dir.X += 1;
        if (kb.IsKeyDown(Keys.Up) || kb.IsKeyDown(Keys.W)) dir.Y -= 1;
        if (kb.IsKeyDown(Keys.Down) || kb.IsKeyDown(Keys.S)) dir.Y += 1;
        if (dir != Vector2.Zero) dir.Normalize();
        _player += dir * Speed * dt;

        var playerRect = new Rectangle((int)_player.X, (int)_player.Y, 32, 32);
        _score += _coins.RemoveAll(c => c.Intersects(playerRect));

        base.Update(gameTime);
    }

    protected override void Draw(GameTime gameTime)
    {
        GraphicsDevice.Clear(Color.CornflowerBlue);
        _spriteBatch.Begin(samplerState: SamplerState.PointClamp);
        foreach (var c in _coins) _spriteBatch.Draw(_pixel, c, Color.Gold);
        _spriteBatch.Draw(_pixel, new Rectangle((int)_player.X, (int)_player.Y, 32, 32), Color.White);
        _spriteBatch.DrawString(_font, $"Score: {_score}", new Vector2(10, 10), Color.Black);
        _spriteBatch.End();
        base.Draw(gameTime);
    }
}
```
`Program.cs`: `using var game = new Game1(); game.Run();`

## Sources
- https://github.com/MonoGame/MonoGame/releases (3.8.6 stable 2026-10-07 marked Latest; 3.8.5 2026-07-15; 3.8.5.1; 3.8.6 changes: Native OpenGL backend, Switch 2, StorageContainer re-added, radians doc, --mg-arch)
- https://monogame.net/blog/2026-07-15-3.8.5-release-2026/ (DesktopVK, WindowsDX12, package names, Content Builder intro, ARM64, 8 gamepads)
- https://monogame.net/blog/2025-06-09-monogame-384/ (3.8.4 AOT/Android fixes)
- https://docs.monogame.net/articles/getting_started/content_pipeline/index.html (Content Builder recommended from 3.8.6; MGCB legacy)
- https://docs.monogame.net/articles/getting_started/content_pipeline/content_builder/index.html (mgblankmgcbstartkit, .NET 10 SDK, project layout, Include<WildcardRule>, load names)
- https://docs.monogame.net/articles/getting_started/content_pipeline/content_builder/setup.html (Builder : ContentBuilder, Include/Exclude, importer/processor examples)
- https://docs.monogame.net/articles/getting_started/platforms.html (template IDs and NuGet packages)
- https://docs.monogame.net/articles/getting_started/2_choosing_your_ide_vscode.html (dotnet new install MonoGame.Templates.CSharp, mgdesktopgl, dotnet tool restore)
- https://www.nuget.org/packages/MonoGame.Templates.CSharp (templates 3.8.6, updated 2026-10-08)
- https://github.com/FNA-XNA/FNA/releases (FNA 26.10, 2026-10-01)
- https://fna-xna.github.io/docs/1%3A-Setting-Up-FNA/ (clone --recursive, FNA.Core.csproj for .NET 8, fnalibs, monthly releases)
- https://fna-xna.github.io/docs/2b%3A-Building-New-Games-with-FNA/ (Content.Load with raw formats, FXC effects, TitleContainer, StorageContainer)
- https://fna-xna.github.io/docs/appendix/Appendix-D%3A-MonoGame/ (FNA vs MonoGame differences and platform table)
- https://github.com/kniEngine/kni and https://github.com/kniEngine/kni/releases (KNI description, platforms, v4.3.9001 on 2026-08-22)

## Confidence and gaps
- High: versions/dates, Content Builder API names (`ContentBuilder`, `GetContentCollection`, `ContentCollection`, `Include<WildcardRule>`), template IDs, FNA setup and differences.
- Medium: exact list of templates in 3.8.6 beyond those named; whether the classic `mgdesktopgl` template now defaults to Content Builder or still to `.mgcb`; .NET minimum for non-Content-Builder projects.
- Unverified: KNI license; Gum being used in official tutorials; community physics/UI/network library status; `Texture2D.FromFile` availability details.
- Example not compiled in this session.
