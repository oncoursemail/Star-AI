---
name: engine-bevy
description: Bevy 0.20 (Rust ECS engine, Oct 2026): systems, Messages vs observer Events, required components, UI, states. Use for any Bevy code; check the project's Bevy version first.
---
# engine-bevy
## Scope
Bevy 0.20 (released 2026-10-08). Bevy breaks APIs every release: check `bevy = "..."` in Cargo.toml first; notes give the version of each change.
## Core model
- `App::new().add_plugins(DefaultPlugins).add_systems(Update, sys).run()`.
- Entities are IDs; components are `#[derive(Component)]` structs; resources are `#[derive(Resource)]` singletons.
- Systems are plain fns; params declare access (`Query`, `Single`, `Res`, `Commands`).
- Schedules: `Startup` once; `Update` per frame; `FixedUpdate` at fixed rate. Commands apply later (deferred).
- Required components: `Sprite`, `Camera2d`, `Text`, `Node` auto-add `Transform` etc.
## Idioms
- Spawn tuples: `commands.spawn((Player, Sprite::from_image(h), Transform::from_xyz(0.,0.,1.)))`.
- `Single<&mut Transform, With<Player>>` for exactly-one entities (system is skipped if not exactly one).
- Fallible systems return `Result` and use `q.single()?`.
- Order with `(a, b).chain()`, `.after(x)`, `.run_if(in_state(GameState::Playing))`.
- Buffered: `#[derive(Message)]`, `app.add_message::<M>()`, `MessageWriter::write`, `MessageReader::read`.
- Immediate: `#[derive(EntityEvent)]` + `commands.trigger(..)`; observers take `On<E>`.
## Pitfalls
1. `add_system`/`add_startup_system` removed (0.11): use `add_systems(Update, ..)` / `add_systems(Startup, ..)`.
2. No bundles: `SpriteBundle`, `Camera2dBundle`, `NodeBundle`, `TextBundle`, `PbrBundle` are gone; spawn `Sprite`, `Camera2d`, `Node`, `Text`, `(Mesh3d(m), MeshMaterial3d(mat))`.
3. Input is `Res<ButtonInput<KeyCode>>` (not `Input<KeyCode>`); keys `KeyCode::ArrowLeft`, `KeyCode::KeyA`.
4. `time.delta_secs()` (not `delta_seconds()`, renamed 0.15).
5. `query.single()` returns `Result` (0.16); `get_single()` deprecated. `despawn()` is recursive; `despawn_recursive` gone; `Parent` is `ChildOf`.
6. Events split (0.17): `EventWriter/EventReader/add_event` became `MessageWriter/MessageReader/add_message`; `#[derive(Event)]` is now for observers.
7. Observers: 0.16 `Trigger<OnAdd, Player>`, 0.17 `On<Add, Player>`, 0.20 `On<Add<Player>>`.
8. Pointer events 0.20 are flat: `On<PointerPress>` (not `On<Pointer<Press>>`); `press.pointer.position`.
9. Text 0.19: `TextFont { font_size: FontSize::Px(24.0), ..default() }`, `font: handle.into()`.
10. UI 0.20: `Interaction` deprecated (use `Hovered`/`Pressed` or pointer observers); `BorderColor::all(c)` (0.17).
11. States: `StateScoped` became `DespawnOnExit` (0.17); `NextState::set` always re-enters (0.18); `set_if_neq` became `set_if_different` (0.20).
12. Scenes 0.19: `SceneRoot` became `WorldAssetRoot`; custom shaders with imports must be `.wesl` (0.20). Physics/networking crates are community and version-pinned.
## Roblox to Bevy
- Workspace / Instance tree -> World of entities; `ChildOf`/`Children` hierarchy
- Part -> entity with `Mesh3d` + `MeshMaterial3d` + `Transform`
- Script / ModuleScript -> systems inside a `Plugin`; Rust modules
- RunService.Heartbeat -> `Update` with `time.delta_secs()`; fixed step -> `FixedUpdate`
- CollectionService tag -> marker component + `With<Tag>`
- Attributes -> component fields
- RemoteEvent -> local Messages/observers; networking via community crates
- DataStore -> serde file save or `SettingsPlugin` (0.19)
- ScreenGui -> root `Node`; UserInputService -> `ButtonInput<KeyCode>`
- task.wait -> `Timer` or `commands.delayed().secs(1.0)`; TweenService -> manual easing or community crate
- Studio playtest -> `cargo run`
## Skeleton
```rust
use bevy::prelude::*;

#[derive(Component)]
struct Player;
#[derive(Message)]
struct Scored(u32);

fn main() {
    App::new()
        .add_plugins(DefaultPlugins)
        .add_message::<Scored>()
        .add_systems(Startup, setup)
        .add_systems(Update, (move_player, log_score).chain())
        .run();
}

fn setup(mut commands: Commands) {
    commands.spawn(Camera2d);
    commands.spawn((Player, Sprite::from_color(Color::srgb(0.2, 0.6, 1.0), Vec2::splat(32.0)), Transform::default()));
}

fn move_player(keys: Res<ButtonInput<KeyCode>>, time: Res<Time>, mut p: Single<&mut Transform, With<Player>>) {
    let x = keys.pressed(KeyCode::ArrowRight) as i32 - keys.pressed(KeyCode::ArrowLeft) as i32;
    p.translation.x += x as f32 * 250.0 * time.delta_secs();
}

fn log_score(mut r: MessageReader<Scored>) {
    for s in r.read() { info!("{}", s.0); }
}
```
## Verification
Run `cargo check`, then `cargo run`; match compiler errors to the pitfalls. Claim success only after seeing the window.
