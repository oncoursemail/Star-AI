---
name: engine-monogame
description: MonoGame 3.8.6 (Oct 2026) and FNA 26.10, XNA-style C# frameworks: Game loop, SpriteBatch, input, Content Builder vs MGCB. Use for MonoGame, FNA or KNI code.
---
# engine-monogame
## Scope
MonoGame 3.8.6 (2026-10-07), FNA 26.10 (2026-10-01), KNI 4.3 (XNA derivative with web target). Check the csproj first: `MonoGame.Framework.*` package version, or an `FNA.Core.csproj` reference (FNA).
## Core model
- Subclass `Game`; constructor creates `GraphicsDeviceManager` and sets `Content.RootDirectory = "Content"`.
- `Initialize` -> `LoadContent` (create `SpriteBatch`, `Content.Load<T>`) -> loop `Update(GameTime)` / `Draw(GameTime)`.
- Fixed timestep by default (`IsFixedTimeStep = true`, 60 Hz); scale by `ElapsedGameTime`.
- Assets are built to `.xnb` by the content pipeline and loaded by name.
- No editor, scene graph, physics, UI or networking built in.
## Idioms
- `var kb = Keyboard.GetState(); if (kb.IsKeyDown(Keys.Left)) ...`; keep the previous state for "pressed this frame".
- `float dt = (float)gameTime.ElapsedGameTime.TotalSeconds;`
- Draw: `GraphicsDevice.Clear(..)`, `_spriteBatch.Begin(samplerState: SamplerState.PointClamp)`, `Draw`, `DrawString`, `End()`.
- Collisions: `Rectangle.Intersects`.
- Audio: `Content.Load<SoundEffect>("hit").Play()`; `MediaPlayer.Play(song)`.
- Content Builder (3.8.6): `class Builder : ContentBuilder`, override `GetContentCollection()`, `contentCollection.Include<WildcardRule>("*")`.
## Pitfalls
1. 3.8.6 recommends the code-based Content Builder; `.mgcb` + MGCB Editor is legacy but works (`dotnet tool restore`). No Pipeline Tool installer since 3.8.
2. Load names have no extension: `Content.Load<Texture2D>("Textures/ball")`, never `"ball.png"`.
3. Templates: `dotnet new install MonoGame.Templates.CSharp`; ids `mgdesktopgl`, `mgwindowsdx`, `mgandroid`, `mgios`, `mgblankmgcbstartkit` (Content Builder, .NET 10 SDK).
4. Rotation in `SpriteBatch.Draw` is radians (`MathHelper.ToRadians`).
5. Draw only between `Begin` and `End`; nested `Begin` throws.
6. No key-pressed events: compare current and previous `KeyboardState`.
7. Resolution changes need `_graphics.ApplyChanges()`.
8. XNA `Net`/`GamerServices` do not exist; use LiteNetLib or Steamworks.NET.
9. DesktopVK and WindowsDX12 (3.8.5+) need `<MonoGamePlatform>` plus `MonoGame.Framework.Native` and `MonoGame.Runtime.*` packages.
10. Keep all MonoGame package versions identical (framework and content builder task).
11. FNA: no MonoGame NuGet packages; ship fnalibs next to the exe; effects are FXC-compiled; MonoGame-only APIs are missing.
12. Pixel art needs `SamplerState.PointClamp`; pipeline textures are premultiplied (use `BlendState.AlphaBlend`).
## Roblox to MonoGame
- Workspace / Instance tree -> your own object lists
- Part -> class with `Rectangle` + texture drawn in `Draw`
- Script / LocalScript -> `Update`/`Draw`, `GameComponent`
- RunService.Heartbeat -> `Update(GameTime)`; RenderStepped -> `Draw(GameTime)`
- UserInputService -> `Keyboard/Mouse/GamePad.GetState()`
- ScreenGui -> last `SpriteBatch` pass without camera matrix
- TweenService -> `Vector2.Lerp` with a timer
- DataStore -> JSON file in AppData (local)
- RemoteEvent -> LiteNetLib messages
- task.wait -> accumulate elapsed time
- Studio playtest -> `dotnet run`
## Skeleton
```csharp
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Microsoft.Xna.Framework.Input;

public class Game1 : Game
{
    private readonly GraphicsDeviceManager _graphics;
    private SpriteBatch _sb;
    private Texture2D _tex;
    private Vector2 _pos = new(100, 100);

    public Game1()
    {
        _graphics = new GraphicsDeviceManager(this);
        Content.RootDirectory = "Content";
    }

    protected override void LoadContent()
    {
        _sb = new SpriteBatch(GraphicsDevice);
        _tex = Content.Load<Texture2D>("player");
    }

    protected override void Update(GameTime gameTime)
    {
        var kb = Keyboard.GetState();
        float dt = (float)gameTime.ElapsedGameTime.TotalSeconds;
        if (kb.IsKeyDown(Keys.Left)) _pos.X -= 250f * dt;
        if (kb.IsKeyDown(Keys.Right)) _pos.X += 250f * dt;
        base.Update(gameTime);
    }

    protected override void Draw(GameTime gameTime)
    {
        GraphicsDevice.Clear(Color.CornflowerBlue);
        _sb.Begin();
        _sb.Draw(_tex, _pos, Color.White);
        _sb.End();
        base.Draw(gameTime);
    }
}
```
## Verification
Run `dotnet build`, then `dotnet run` in the platform project; content errors show as `[E]` lines or `ContentLoadException`. Claim a run only after seeing the window.
