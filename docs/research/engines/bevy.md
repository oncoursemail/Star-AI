# Bevy: STAR engine research
**Verified 2026-10-13 against official docs. Current stable: Bevy 0.20 (2026-10-08).** Free and open source, dual MIT / Apache-2.0, no fees.

## At a glance
| | |
|---|---|
| Best for | Code-first 2D/3D games and simulations in Rust; ECS-heavy designs with many entities; programmers who want full engine source |
| Weak at | Stability (breaking release every ~3-5 months), no shipping visual editor, small asset/plugin ecosystem vs Unity/Godot, long compile times, no built-in physics or networking |
| Language(s) | Rust (edition 2024 crates); shaders in WGSL/WESL (WESL replaced the custom WGSL dialect in 0.20) |
| Editor / tooling | No official editor. `cargo` + `bevy` crate; BSN (`bsn!` macro) scene notation since 0.19; in-engine gizmos, `TransformGizmoPlugin`, `InfiniteGridPlugin` and Feathers editor widgets are building blocks toward an editor |
| Platforms (export) | Windows, macOS, Linux, Web (wasm32 via WebGL2/WebGPU), iOS, Android; consoles not officially supported |
| License / cost | MIT OR Apache-2.0, free |
| Roblox-likeness | low: no editor/Studio, no hosted multiplayer, no DataStore; data-oriented ECS instead of an Instance tree. Only "Workspace has parts with components/tags" maps loosely |

## Architecture and lifecycle
- **App** = `App::new()` + plugins + schedules, then `.run()`. `DefaultPlugins` adds windowing (winit), rendering (wgpu), input, assets, audio, UI, text, picking, etc.
- **ECS**: Entities are IDs; **Components** are plain Rust structs (`#[derive(Component)]`); **Resources** are global singletons (`#[derive(Resource)]`, since 0.19 stored as components on singleton entities internally); **Systems** are plain functions whose parameters declare data access (`Query`, `Res`, `ResMut`, `Commands`, `Single`, `MessageReader`, `Local`, ...). The scheduler runs non-conflicting systems in parallel.
- **Schedules** (main): `PreStartup` -> `Startup` -> `PostStartup` (once), then each frame `First`, `PreUpdate`, `StateTransition`, `RunFixedMainLoop` (drives `FixedPreUpdate`/`FixedUpdate`/`FixedPostUpdate` at `Time<Fixed>` rate, default 64 Hz), `Update`, `PostUpdate`, `Last`. Rendering runs in a separate render world (extraction).
- **Commands** are deferred: `commands.spawn(...)`, `.insert`, `.despawn` apply at the next sync point (end of schedule or between chained systems with automatic sync points), not immediately.
- **Required Components (0.15+)**: spawning `Camera2d`, `Sprite`, `Text`, `Node`, `Mesh3d` auto-inserts what they need (`Transform`, `Visibility`, ...). Bundles like `SpriteBundle`, `Camera2dBundle`, `NodeBundle`, `TextBundle`, `PbrBundle` are gone; spawn a tuple of components.
- **Two event systems (0.17+)**: buffered **Messages** (`#[derive(Message)]`, `MessageWriter`/`MessageReader`, `app.add_message::<M>()`) read in systems each frame, and **Events + Observers** (`#[derive(Event)]` / `#[derive(EntityEvent)]`, `commands.trigger(...)`, observers take `On<E>`) that run immediately when triggered.
- **Hierarchy**: `ChildOf(parent)` relationship component + `Children` (0.16+). `despawn()` is recursive by default (0.16+). `children![...]` macro and `with_children` for spawning.
- **States**: `#[derive(States)]` enum, `app.init_state::<S>()`, schedules `OnEnter(S::X)`/`OnExit(S::X)`, run condition `in_state(S::X)`, `ResMut<NextState<S>>`; entities tagged `DespawnOnExit(S::X)` are cleaned up (0.17+, formerly `StateScoped`).
- **Scenes (0.19+)**: BSN via `bsn!` macro, `commands.spawn_scene(...)`; old glTF/RON scene types renamed to "world assets" (`SceneRoot` -> `WorldAssetRoot` in 0.19).

## Project layout
```
my_game/
  Cargo.toml        # [dependencies] bevy = "0.20"
  src/main.rs       # App::new()...run()
  src/player.rs     # one Plugin per feature: impl Plugin for PlayerPlugin { fn build(&self, app: &mut App) {...} }
  assets/           # loaded by AssetServer with paths relative to assets/ (e.g. "sprites/player.png")
  .cargo/config.toml  # optional: faster linker settings
```
Recommended dev profile (from Bevy's quick start; speeds up debug builds):
```toml
[profile.dev]
opt-level = 1
[profile.dev.package."*"]
opt-level = 3
```
`cargo run --features bevy/dynamic_linking` speeds up iterative compiles on desktop (do not ship with it).

## Scripting idioms
```rust
use bevy::prelude::*;

#[derive(Component)]
struct Player { speed: f32 }

#[derive(Resource, Default)]
struct Score(u32);

pub struct PlayerPlugin;
impl Plugin for PlayerPlugin {
    fn build(&self, app: &mut App) {
        app.init_resource::<Score>()
            .add_systems(Startup, spawn_player)
            .add_systems(Update, move_player.run_if(in_state(GameState::Playing)));
    }
}

fn spawn_player(mut commands: Commands, assets: Res<AssetServer>) {
    commands.spawn((
        Player { speed: 300.0 },
        Sprite::from_image(assets.load("player.png")),
        Transform::from_xyz(0.0, 0.0, 1.0),
    ));
}

// Single<D, F>: exactly one match, otherwise the system is skipped (no panic).
fn move_player(
    keys: Res<ButtonInput<KeyCode>>,
    time: Res<Time>,
    player: Single<(&Player, &mut Transform)>,
) {
    let (p, mut tf) = player.into_inner();
    let mut dir = Vec2::ZERO;
    if keys.pressed(KeyCode::KeyA) { dir.x -= 1.0; }
    if keys.pressed(KeyCode::KeyD) { dir.x += 1.0; }
    tf.translation += (dir * p.speed * time.delta_secs()).extend(0.0);
}
```
- Fallible systems (0.16+): return `Result` and use `?`: `fn sys(q: Query<&Transform, With<Player>>) -> Result { let t = q.single()?; Ok(()) }`.
- Ordering: `.add_systems(Update, (a, b, c).chain())`, `.before(x)`, `.after(x)`, `SystemSet`s via `configure_sets`. 0.20 adds `chain_weak()/before_weak()/after_weak()`.
- Change detection: `Query<&Health, Changed<Health>>`, `Added<T>`, `Ref<T>::is_changed()`.
- Messages:
```rust
#[derive(Message)]
struct Damage { target: Entity, amount: f32 }
app.add_message::<Damage>();
fn deal(mut w: MessageWriter<Damage>) { /* w.write(Damage { .. }); */ }
fn apply(mut r: MessageReader<Damage>) { for d in r.read() { /* ... */ } }
```
- Observers (0.20 lifecycle syntax):
```rust
app.add_observer(|_add: On<Add<Player>>| info!("player spawned"));
#[derive(EntityEvent)]
struct Explode { entity: Entity }
commands.trigger(Explode { entity });
app.add_observer(|e: On<Explode>, mut commands: Commands| { commands.entity(e.entity).despawn(); });
```
- Timers: `Timer::from_seconds(1.0, TimerMode::Repeating)`, tick with `timer.tick(time.delta())`, check `timer.just_finished()`.
- Delayed commands (0.19+): `commands.delayed().secs(1.0).spawn(...)`.

## Pitfalls (what AI answers get wrong)
Most training data is 0.10-0.14. Check `Cargo.toml` first; then apply this ladder.
1. **`add_system` / `add_startup_system` (removed 0.11+)** -> `add_systems(Update, sys)` / `add_systems(Startup, sys)`.
2. **Bundles (deprecated 0.15, removed later)**: `SpriteBundle`, `Camera2dBundle`, `Camera3dBundle`, `NodeBundle`, `TextBundle`, `PbrBundle`, `ImageBundle`, `ButtonBundle` -> spawn `Sprite`, `Camera2d`, `Camera3d`, `Node`, `Text`, `(Mesh3d(h), MeshMaterial3d(m))`, `ImageNode`, `Button` directly; required components fill the rest.
3. **Input**: `Res<Input<KeyCode>>` (pre-0.13) -> `Res<ButtonInput<KeyCode>>`; key names `KeyCode::Left/A` -> `KeyCode::ArrowLeft/KeyA`.
4. **Time**: `time.delta_seconds()` (pre-0.15) -> `time.delta_secs()`; `elapsed_seconds()` -> `elapsed_secs()`.
5. **Query::single (0.16)**: `single()`/`single_mut()` return `Result`; `get_single()` deprecated. Use `?` in a `-> Result` system or `Single<...>` param.
6. **Despawn (0.16)**: `despawn_recursive()` gone; `despawn()` despawns children. `Parent` -> `ChildOf` (`child_of.parent()`), `set_parent` -> `insert(ChildOf(p))`; `ChildBuilder` -> `ChildSpawnerCommands`. 0.18: `clear_children` -> `detach_all_children`, `remove_children` -> `detach_children`.
7. **Events renamed to Messages (0.17)**: `EventWriter`/`EventReader`/`Events<T>`/`add_event` -> `MessageWriter`/`MessageReader`/`Messages<T>`/`add_message`; `send` -> `write` (0.16 already renamed `send` to `write`). `#[derive(Event)]` now means an observer event.
8. **Observers (0.17 and again 0.20)**: `Trigger<OnAdd, Player>` + `trigger.target()` (0.16) -> `On<Add, Player>` + `add.entity` (0.17) -> **`On<Add<Player>>` (0.20)**. `world.trigger_targets(ev, e)` -> `world.trigger(EntityEventStruct { entity: e })`. `OnInsert/OnRemove/OnDespawn` -> `Insert/Remove/Despawn`.
9. **Pointer/picking (0.20)**: `On<Pointer<Click>>`-style generic events -> flat types such as `On<PointerPress>`; fields `press.pointer.id`, `press.pointer.position`. 0.17 had renamed `Pointer<Pressed>` -> `Pointer<Press>`.
10. **UI (0.15 -> 0.20)**: `Style` merged into `Node`; `BorderRadius` became a `Node::border_radius` field (0.18) and fields are now `CornerRadius` (0.20); `BorderColor(c)` -> `BorderColor::all(c)` (0.17); `ui::Interaction` and `ui::widgets::Button` deprecated in 0.20 in favor of `ui_widgets::Button` + `Hovered`/`Pressed` components; `JustifyText` -> `Justify` (0.17).
11. **Text (0.19 Parley)**: `TextFont { font_size: 35.0 }` -> `font_size: FontSize::Px(35.0)`; `TextFont { font: handle }` -> `font: handle.into()`; `TextLayout::new_with_justify` -> `TextLayout::justify`; 0.20 default font size is `FontSize::Rem(1.)`. `Text2d` for world-space text.
12. **States (0.17/0.18/0.20)**: `StateScoped` -> `DespawnOnExit`; `next_state.set(S)` now always re-runs `OnEnter/OnExit` even if unchanged (0.18); `set_if_neq` -> `set_if_different` (0.20).
13. **System set names (0.17)**: `*Set`/`*System` -> `*Systems` (`TransformSystems`, `UiSystems`, `RenderSystems`, `PickingSystems`).
14. **Scenes (0.19)**: `SceneRoot(asset_server.load("m.gltf#Scene0"))` -> `WorldAssetRoot(...)`; `DynamicScene` -> `DynamicWorld`; `bevy::scene` -> `bevy::world_serialization`. `bsn!` is the new scene notation.
15. **Exclusive systems (0.20)**: `&mut World` is now a normal `SystemParam`; `ExclusiveFunctionSystem` & co. removed.
16. **Camera/render**: `Camera { hdr: true }` -> `Hdr` component (0.17); `Camera::target` -> separate `RenderTarget` component (0.18); `AmbientLight` resource -> `GlobalAmbientLight` (0.18); materials need `MeshMaterial3d<T>` wrapper (0.15).
17. **Shaders (0.20)**: Bevy-specific WGSL preprocessor files must become `.wesl`.
18. **Audio**: `AudioBundle` -> `AudioPlayer::new(handle)` + `PlaybackSettings` (0.15). With `default-features = false`, the `audio` feature and input features (`keyboard`, `mouse`, `gamepad`...) must be enabled explicitly (0.18/0.19).
19. **Resource + Component on one type (0.19)**: `#[derive(Component, Resource)]` on the same struct no longer allowed; split types.
20. **Name (0.20)**: `Name::from(&str)` needs `'static`; use `Name::new(s.to_owned())` for runtime strings.

## Rendering
- 2D: `Camera2d`, `Sprite { image, color, custom_size, flip_x, .. }`, `Sprite::from_image(h)`, `Sprite::from_color(color, size)`, `TextureAtlas` + `TextureAtlasLayout` for sheets, `Text2d`, `Mesh2d` + `MeshMaterial2d<ColorMaterial>`. 0.20 moved sprites onto a mesh+material backend (`Sprite::alpha_mode`, give overlapping sprites distinct Z).
- 3D: `Camera3d`, `Mesh3d(meshes.add(Cuboid::new(1.,1.,1.)))`, `MeshMaterial3d(materials.add(StandardMaterial{..}))`, `PointLight`, `DirectionalLight`, `SceneRoot`/`WorldAssetRoot` for glTF. PBR, clustered forward + deferred, SSAO/SSR, bloom (`bevy_post_process`), TAA/FXAA/SMAA (`bevy_anti_alias`), contact shadows (0.19), Solari path tracing (experimental), DLSS on supported hardware.
- Colors: `Color::srgb(r,g,b)`, `Color::srgba`, `Color::WHITE`; palettes in `bevy::color::palettes::css::*`. (`Color::rgb` was removed in 0.14.)
- Gizmos for debug: `fn g(mut gizmos: Gizmos) { gizmos.circle_2d(Vec2::ZERO, 10.0, Color::WHITE); }`; `Gizmos::cuboid` -> `Gizmos::cube` (0.18); `Gizmos::text_2d` (0.19).
- Render graph replaced by ECS schedules for render passes (0.19): passes are systems in `Core2d`/`Core3d`.

## Physics
No built-in physics. Community crates (not official): **Avian** (`avian2d`/`avian3d`, ECS-native, successor of bevy_xpbd) and **bevy_rapier** (Rapier). Each pins a Bevy version: match crate version to your Bevy minor. For simple games use `bevy::math::bounding` (`Aabb2d`, `BoundingCircle`, `IntersectsVolume`) or distance checks.

## Input
- `Res<ButtonInput<KeyCode>>`: `pressed`, `just_pressed`, `just_released`; `Res<ButtonInput<MouseButton>>`; `AccumulatedMouseMotion`, `AccumulatedMouseScroll` resources; gamepads are entities with `Gamepad` component (`gamepad.pressed(GamepadButton::South)`, `gamepad.left_stick()`).
- Cursor position: `window.cursor_position()` on `Single<&Window, With<PrimaryWindow>>`; world position via `camera.viewport_to_world_2d(cam_tf, pos)` (returns `Result`).
- Picking (built in, `DefaultPlugins`): observers on pointer events (`On<PointerPress>` etc. in 0.20). Sprite picking via `sprite_picking` feature; mesh picking `MeshPickingPlugin`.
- Text input: `EditableText` + `TextInput` components (0.19/0.20).
- Community: `leafwing-input-manager` for action maps.

## UI
- Flexbox/Grid via taffy. Root: `Node { width: Val::Percent(100.), .. }`; text `Text::new("hi")` + `TextFont` + `TextColor`; images `ImageNode`; buttons `Button` component (0.20: `bevy::ui_widgets::Button`; state via `Hovered`/`Pressed`), `BackgroundColor`, `BorderColor::all(..)`.
- Units: `Val::Px`, `Val::Percent`, `Val::Vw/Vh`, new `Val::Em/Val::Rem` (0.20); helper fns `px()`, `percent()`, `em()`, `rem()`.
- Interaction: prefer observers (`.observe(|_: On<PointerPress>| ...)` on the entity). `Interaction` is deprecated in 0.20.
- Feathers (editor-style widget set) and headless `bevy_ui_widgets` (sliders, scrollbars, tabs, checkboxes) exist; Feathers is still marked experimental.
- 0.20: UI rendering is retained; `FixedNode` positions relative to the camera viewport.

## Networking and multiplayer
No built-in networking. Community (not official): `lightyear` (client prediction, rollback), `bevy_replicon` (server-authoritative replication), `bevy_matchbox` (WebRTC P2P), `renet`/`bevy_renet`. Each pins a Bevy version. BRP (Bevy Remote Protocol, `bevy_remote`) is for tooling/inspection, not gameplay networking.

## Save data
- No DataStore equivalent. Options: `serde` + `ron`/`serde_json` to a file under a platform dir (e.g. `dirs` crate), or reflection-based world serialization (`DynamicWorld`, `bevy_world_serialization` in 0.19+).
- 0.19 added `SettingsPlugin::new("com.example.mygame")` that loads `SettingsGroup` resources (derive `Resource, SettingsGroup, Reflect`, `#[reflect(Default, SettingsGroup)]` required in 0.20) and saves with `SaveSettingsDeferred`/`SaveSettingsSync`.
- `ron` is no longer re-exported (0.18); add it as a direct dependency.
- Web: use `web-sys` localStorage; filesystem is not available on wasm.

## Performance
- Release builds (`cargo run --release`) are often 10-100x faster than unoptimized debug; use the dev profile above.
- Avoid querying broadly every frame; use marker components (`With<Enemy>`), `Changed<T>`, and run conditions (`run_if`).
- Many identical sprites/meshes batch automatically when they share material/image.
- Use `par_iter_mut()` for heavy per-entity work; 0.19 `contiguous_iter_mut()` for SIMD-friendly loops.
- Diagnostics: `FrameTimeDiagnosticsPlugin`, `DiagnosticsOverlay::fps()` (0.19), `RenderDebugOverlay` (0.20, F1/F2), Tracy via `trace_tracy` feature.
- `ScheduleBuildSettings::shuffle_seed` (0.20, `debug` feature) randomizes ambiguous system order to find ordering bugs.

## Build and export
- Desktop: `cargo build --release`; ship the binary plus the `assets/` folder next to it.
- Web: `rustup target add wasm32-unknown-unknown`; build with `wasm-bindgen-cli` or `trunk` (community tool) or the Bevy CLI (`bevy run web`, official but still alpha, unverified current status). WebGL2 is default; WebGPU via `webgpu` feature.
- Mobile: iOS via Xcode project, Android via `cargo-apk`/Gradle examples in the Bevy repo; requires extra setup.
- Disable unused features (`default-features = false` + explicit list) to cut compile time and size; remember 0.18+ needs input/audio features listed explicitly.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| `no method named add_system` | Bevy 0.11+ API | `add_systems(Update, sys)` |
| `cannot find type SpriteBundle` | Bundles removed | Spawn `Sprite` (+ `Transform`) tuple |
| `cannot find type Input` | Renamed 0.13 | `ButtonInput<KeyCode>` |
| `EventWriter not found` / `add_event` missing | 0.17 Messages split | `MessageWriter`, `add_message::<T>()`, `#[derive(Message)]` |
| Observer generic error on `On<Add, Player>` | 0.20 moved bundle generic | `On<Add<Player>>` |
| System panics "expected one entity" (old) / silently not running | `Single` skips system when 0 or 2+ matches | Check spawn ran; use `Query` + `iter()` if many |
| "Query conflicts" panic at startup | Two params borrow same component mutably | `Without<T>` filters or `ParamSet` |
| Blank window, sprite missing | No camera spawned, or asset path wrong | `commands.spawn(Camera2d)`; path relative to `assets/` |
| Entity spawned in system A not visible in system B same frame | Commands deferred | `.chain()` (inserts sync point) or `.after()` |
| Text font size type error | 0.19 `FontSize` enum | `font_size: FontSize::Px(24.0)` |
| Third-party plugin fails to compile | Crate pinned to older Bevy | Use the crate version matching your Bevy minor |
| `despawn_recursive` not found | 0.16 | `despawn()` (recursive by default) |
| `.wgsl` with `#import` fails (0.20) | WESL migration | Rename to `.wesl` and convert directives |

## Mapping from Roblox
| Roblox | Bevy | Notes |
|---|---|---|
| Workspace / Instance tree | `World` of entities; hierarchy via `ChildOf`/`Children` | Flat ECS, hierarchy optional |
| Part | Entity with `Mesh3d` + `MeshMaterial3d` + `Transform` (+ physics crate collider) | No built-in physics body |
| Model | Parent entity with children, or a BSN scene function | `children![...]` |
| Script / LocalScript | Systems (functions) registered in a `Plugin` | No client/server split built in |
| ModuleScript | Rust module (`mod player;`) / `Plugin` | |
| RemoteEvent | Community networking crate messages (lightyear/replicon) | Locally: Messages or observer Events |
| DataStore | serde file save / `SettingsPlugin` | No cloud storage |
| Players / Player | Your own `Player` component entities | |
| Humanoid | Your own components + physics character controller crate | |
| RunService.Heartbeat | `Update` schedule (variable dt); `FixedUpdate` for physics-style ticks | `time.delta_secs()` |
| RenderStepped | `PostUpdate` ordered before transform propagation, or `Update` | |
| TweenService | No built-in tween; animate with `Time` + `EaseFunction`/`EasingCurve` (bevy_math), or `bevy_tweening` (community) | |
| CollectionService tags | Marker components (`#[derive(Component)] struct Enemy;`) + `With<Enemy>` | Very natural in ECS |
| Attributes | Components / fields | Reflection via `#[derive(Reflect)]` |
| ScreenGui | UI `Node` tree spawned with a root `Node` | |
| UserInputService | `ButtonInput<KeyCode>`, `ButtonInput<MouseButton>`, gamepad entities | |
| task.wait | `Timer` component/resource, `commands.delayed()` (0.19) | No coroutines |
| Studio playtest | `cargo run` | |
| Publishing | Build binary/wasm and ship via itch.io/Steam yourself | |

## Minimal example
Bevy 0.20: move a square with WASD/arrows, collect coins, show score.
```rust
use bevy::prelude::*;

#[derive(Component)]
struct Player;
#[derive(Component)]
struct Coin;
#[derive(Component)]
struct ScoreText;
#[derive(Resource, Default)]
struct Score(u32);
#[derive(Message)]
struct CoinCollected;

fn main() {
    App::new()
        .add_plugins(DefaultPlugins)
        .init_resource::<Score>()
        .add_message::<CoinCollected>()
        .add_systems(Startup, setup)
        .add_systems(Update, (move_player, collect_coins, update_score).chain())
        .run();
}

fn setup(mut commands: Commands) {
    commands.spawn(Camera2d);
    commands.spawn((
        Player,
        Sprite::from_color(Color::srgb(0.2, 0.6, 1.0), Vec2::splat(32.0)),
        Transform::from_xyz(0.0, 0.0, 1.0),
    ));
    for i in 0..5 {
        commands.spawn((
            Coin,
            Sprite::from_color(Color::srgb(1.0, 0.85, 0.1), Vec2::splat(16.0)),
            Transform::from_xyz(-200.0 + i as f32 * 100.0, 120.0, 0.0),
        ));
    }
    commands.spawn((
        ScoreText,
        Text::new("Score: 0"),
        TextFont { font_size: FontSize::Px(28.0), ..default() },
        Node { position_type: PositionType::Absolute, top: Val::Px(12.0), left: Val::Px(12.0), ..default() },
    ));
}

fn move_player(
    keys: Res<ButtonInput<KeyCode>>,
    time: Res<Time>,
    mut player: Single<&mut Transform, With<Player>>,
) {
    let mut dir = Vec2::ZERO;
    if keys.any_pressed([KeyCode::ArrowLeft, KeyCode::KeyA]) { dir.x -= 1.0; }
    if keys.any_pressed([KeyCode::ArrowRight, KeyCode::KeyD]) { dir.x += 1.0; }
    if keys.any_pressed([KeyCode::ArrowUp, KeyCode::KeyW]) { dir.y += 1.0; }
    if keys.any_pressed([KeyCode::ArrowDown, KeyCode::KeyS]) { dir.y -= 1.0; }
    player.translation += (dir.normalize_or_zero() * 250.0 * time.delta_secs()).extend(0.0);
}

fn collect_coins(
    mut commands: Commands,
    player: Single<&Transform, With<Player>>,
    coins: Query<(Entity, &Transform), With<Coin>>,
    mut collected: MessageWriter<CoinCollected>,
) {
    let p = player.translation.truncate();
    for (entity, tf) in &coins {
        if p.distance(tf.translation.truncate()) < 24.0 {
            commands.entity(entity).despawn();
            collected.write(CoinCollected);
        }
    }
}

fn update_score(
    mut reader: MessageReader<CoinCollected>,
    mut score: ResMut<Score>,
    mut text: Single<&mut Text, With<ScoreText>>,
) {
    let n = reader.read().count() as u32;
    if n > 0 {
        score.0 += n;
        **text = Text::new(format!("Score: {}", score.0));
    }
}
```

## Sources
- https://bevy.org/news/ (release list and dates: 0.20 2026-10-08, 0.19 2026-06-19, 0.18 2026-01-13, 0.17 2025-09-30, 0.16 2025-04-24)
- https://bevy.org/news/bevy-0-20/ (0.20 features: WESL, flat pointer events, chain_weak, Val::Em/Rem, Sprite on Mesh2d, BSN changes)
- https://bevy.org/news/bevy-0-19/ (BSN `bsn!`, Parley text, FontSize, EditableText, SettingsPlugin, resources as components, delayed commands, render graph as systems)
- https://bevy.org/learn/migration-guides/0-19-to-0-20/ (On<Add<A>>, PointerPress, exclusive systems unified, set_if_different, Interaction/Button deprecations, Name 'static, CornerRadius)
- https://bevy.org/learn/migration-guides/0-18-to-0-19/ (SceneRoot->WorldAssetRoot, TextFont FontSize::Px, Component+Resource split, InputFocus API)
- https://bevy.org/learn/migration-guides/0-17-to-0-18/ (next_state.set always transitions, detach_* renames, RenderTarget component, GlobalAmbientLight, explicit input features, Gizmos::cube)
- https://bevy.org/learn/migration-guides/0-16-to-0-17/ (Event->Message split, Trigger->On, OnAdd->Add, EntityEvent, *Systems renames, StateScoped->DespawnOnExit, Hdr, BorderColor::all)
- https://bevy.org/learn/migration-guides/0-15-to-0-16/ (Query::single Result, despawn recursive, ChildOf, EventWriter::write, fallible systems)
- https://bevy.org/learn/migration-guides/introduction/ (migration guide policy)
- https://docs.rs/bevy/latest/bevy/app/struct.App.html (0.20 App has add_message, add_observer; no add_event)
- https://raw.githubusercontent.com/bevyengine/bevy/v0.20.0/examples/2d/move_sprite.rs (Sprite::from_image, Camera2d, time.delta_secs at v0.20.0)

## Confidence and gaps
- High: release dates, Messages/Observers renames, `On<Add<A>>` in 0.20, Query::single Result, despawn, bundles removal, FontSize::Px, WorldAssetRoot.
- Medium: exact 0.20 accessor for the entity on lifecycle observers (`On<Add<A>>`) was not confirmed; example avoids it. `px()` helper return type/usage not checked; `Val::Px` used instead.
- Community crates (Avian, bevy_rapier, lightyear, bevy_replicon, leafwing-input-manager, bevy_tweening, trunk) named from general knowledge; versions for 0.20 not verified.
- Bevy CLI web workflow status and Rust MSRV for 0.20 not verified.
- No code was compiled; example is checked against docs only.
