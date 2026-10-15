# Minecraft modding (Java: Fabric / NeoForge / data packs; Bedrock: add-ons + Script API): STAR engine research
**Verified 2026-10-13 against official docs. Current stable: Java Edition 26.3 (2026-09-15; Java 25 runtime), Bedrock 26.50 (2026-09-15, hotfix 26.52 on 2026-09-25) with `@minecraft/server` 2.10.0.** Modding tools are free/open source; the game is paid; Bedrock Marketplace sales need Marketplace Partner status.

## At a glance
| | |
|---|---|
| Best for | Extending Minecraft: new blocks/items/mobs/mechanics (Java mods), vanilla-compatible logic (data packs), cross-platform add-ons and scripted minigames (Bedrock) |
| Weak at | Standalone games; anything that fights the voxel engine; Java mods break every drop; Bedrock cannot change the renderer or add native code |
| Language(s) | Java 25 (Fabric, NeoForge); mcfunction + JSON (data packs); JSON + JavaScript/TypeScript (Bedrock Script API) |
| Editor / tooling | IntelliJ IDEA + Gradle (Fabric Loom / NeoForge ModDevGradle); VS Code + Blockbench + Bedrock Debugger/Minecraft Creator Tools; Bedrock Editor (in-game) |
| Platforms (export) | Java: Windows/macOS/Linux (client + server jar mods). Bedrock: Windows, consoles, mobile via add-ons/.mcaddon/Marketplace and Realms/BDS |
| License / cost | Mojang EULA + Minecraft Usage Guidelines; Fabric (Apache-2.0), NeoForge (LGPL-2.1) free |
| Roblox-likeness | medium: Bedrock add-ons (JSON components + event-driven JS on the server) feel closest; Java modding is low (patching a big Java codebase) |

## Architecture and lifecycle
**Version scheme (big trap).** Java went 1.21.11 (2025-12-09) -> 26.1 (2026-03-24) -> 26.1.1/26.1.2 -> 26.2 (2026-06-16) -> 26.3 (2026-09-15). Format `YY.D[.H]` (year, drop, hotfix). There is no 1.22. Snapshots are now named like `26.4-snapshot-4`. Bedrock uses the same year prefix but its own minor numbers (26.0, 26.10 ... 26.50); manifests still express engine versions as `[1, 26, 50]`-style triples (community-observed).

**Java Edition.** One codebase; logical server (always present, also inside singleplayer) + client. Game ticks 20/s. Content is registered into **registries** (`BuiltInRegistries.ITEM`, `BLOCK`, `ENTITY_TYPE` ...) by `ResourceKey`/`Identifier`. Many game definitions are **data-driven** via data packs (recipes, loot tables, advancements, tags, worldgen, enchantments, damage types...).
- Since 26.1 the game jar is **unobfuscated**: Mojang's own names are the runtime names. Yarn (Fabric's community mappings) is discontinued; the last Yarn build is for 1.21.11.
- **Fabric**: lightweight loader + Fabric API (events + helpers) + **Mixin** for patching vanilla. Entrypoints declared in `fabric.mod.json` (`main`, `client`, `server`, `fabric-datagen`).
- **NeoForge**: fork of Forge (July 2023, during 1.20.1, after most of the Forge team left). Event-bus architecture: mod bus (registration/lifecycle, passed into the `@Mod` constructor as `IEventBus`) and game bus (`NeoForge.EVENT_BUS`). `DeferredRegister` for registration, capabilities, data attachments, networking payloads. Version numbers now track Minecraft: NeoForge `26.3.0.x` for MC 26.3 (older: `21.1.x` for 1.21.1).
- Legacy **Forge** (MinecraftForge) still exists but most of the ecosystem moved to NeoForge/Fabric; don't mix their APIs (`net.minecraftforge.*` vs `net.neoforged.*`).

**Data packs** (no code): `pack.mcmeta` + `data/<namespace>/...`; functions (`.mcfunction`) run commands; `#minecraft:tick` / `#minecraft:load` function tags run every tick / on load.

**Bedrock Edition.** C++ engine; creators ship **behavior packs** (server logic: entity/block/item JSON, loot, recipes, functions, scripts) and **resource packs** (client visuals: models, textures, animations, render controllers, UI, sounds). Script API runs JavaScript (QuickJS) on the server side of the world. Script API 2.x (stable since `@minecraft/server` 2.0.0, 2025-06-17) uses **early execution**: top-level code runs before the world exists.

## Project layout
Fabric (example mod for 26.3):
```
build.gradle            # plugins { id 'net.fabricmc.fabric-loom' version "${loom_version}" }
gradle.properties       # minecraft_version=26.3, loader_version=0.19.5, loom_version=1.18-SNAPSHOT, fabric_api_version=0.162.0+26.3
src/main/java/com/example/ExampleMod.java          # implements ModInitializer
src/main/java/com/example/mixin/ExampleMixin.java
src/main/resources/fabric.mod.json, modid.mixins.json, assets/<modid>/..., data/<modid>/...
src/client/java/com/example/client/ExampleModClient.java  # split client source set
```
NeoForge (MDK-26.3-ModDevGradle):
```
build.gradle            # plugins { id 'net.neoforged.moddev' version '2.0.148' }
gradle.properties       # minecraft_version=26.3, neo_version=26.3.0.69-beta (latest on maven: 26.3.0.76)
src/main/java/com/example/examplemod/ExampleMod.java   # @Mod(MODID)
src/main/templates/META-INF/neoforge.mods.toml           # expanded into resources at build
src/generated/resources/                               # datagen output
```
Data pack:
```
mypack/pack.mcmeta
mypack/data/mypack/function/tick.mcfunction
mypack/data/minecraft/tags/function/tick.json   # {"values":["mypack:tick"]}
```
Bedrock:
```
development_behavior_packs/MyBP/manifest.json, entities/*.json, blocks/*.json, items/*.json, scripts/main.js
development_resource_packs/MyRP/manifest.json, textures/, models/entity/*.geo.json, entity/*.json (client entity)
```

## Scripting idioms
Fabric item registration (current docs, Mojang names):
```java
public final class ModItems {
    public static final ResourceKey<Item> RUBY_KEY =
        ResourceKey.create(Registries.ITEM, Identifier.fromNamespaceAndPath("modid", "ruby"));
    public static final Item RUBY = Registry.register(BuiltInRegistries.ITEM, RUBY_KEY,
        new Item(new Item.Properties().setId(RUBY_KEY)));

    public static void initialize() {
        CreativeModeTabEvents.modifyOutputEvent(CreativeModeTabs.INGREDIENTS)
            .register(tab -> tab.accept(RUBY));
    }
}
```
Fabric events: `ServerTickEvents.END_SERVER_TICK.register(server -> ...)`, `UseBlockCallback.EVENT.register((player, level, hand, hit) -> InteractionResult.PASS)`, `CommandRegistrationCallback.EVENT`. Mixin:
```java
@Mixin(MinecraftServer.class)
public class ExampleMixin {
    @Inject(at = @At("HEAD"), method = "loadLevel")
    private void init(CallbackInfo info) { }
}
```
NeoForge registration:
```java
@Mod(ExampleMod.MODID)
public class ExampleMod {
    public static final String MODID = "examplemod";
    public static final DeferredRegister.Items ITEMS = DeferredRegister.createItems(MODID);
    public static final DeferredItem<Item> RUBY = ITEMS.registerSimpleItem("ruby", p -> p);

    public ExampleMod(IEventBus modEventBus, ModContainer modContainer) {
        ITEMS.register(modEventBus);
        modEventBus.addListener(this::addCreative);
        NeoForge.EVENT_BUS.register(this);              // only if this class has @SubscribeEvent methods
    }
    private void addCreative(BuildCreativeModeTabContentsEvent e) {
        if (e.getTabKey() == CreativeModeTabs.INGREDIENTS) e.accept(RUBY);
    }
    @SubscribeEvent
    public void onServerStarting(ServerStartingEvent e) { }
}
```
`DeferredRegister.Items` helpers set the item id for you; when constructing `Item.Properties` yourself you must call `setId(...)` (exception otherwise).

Data pack function:
```mcfunction
# data/mypack/function/tick.mcfunction
execute as @a[scores={coins=10..}] run title @s actionbar {"text":"Rich!"}
give @p minecraft:diamond_sword[minecraft:custom_name="Ruby Blade"]
```
Bedrock Script API 2.x:
```js
import { world, system } from "@minecraft/server";

system.beforeEvents.startup.subscribe((init) => {
  init.blockComponentRegistry.registerCustomComponent("demo:glow", {
    onStepOn: (e) => e.entity?.addEffect("speed", 40),
  });
});

world.afterEvents.worldLoad.subscribe(() => {
  system.runInterval(() => {
    for (const p of world.getPlayers()) p.onScreenDisplay.setActionBar(`Coins: ${p.getDynamicProperty("coins") ?? 0}`);
  }, 20);
});
```

## Pitfalls (what AI answers get wrong)
1. **"Minecraft 1.22" / 1.21.x as current.** Current Java is 26.3 (YY.D scheme since 26.1). Always ask/check the project's `minecraft_version` and loader version.
2. **Yarn names after 1.21.11.** 26.1+ is unobfuscated; Fabric uses Mojang names. `net.minecraft.util.Identifier`/`ItemGroup`/`World`/`PlayerEntity`/`Text.literal` are Yarn-isms; Mojang names are `Identifier` (renamed from `ResourceLocation` by Mojang in 1.21.11, package `net.minecraft.resources`), `CreativeModeTab`, `Level`, `Player`, `Component.literal`. Fabric API classes/modules were renamed accordingly (`ItemGroupEvents` in `api.itemgroup.v1` -> `CreativeModeTabEvents` in `net.fabricmc.fabric.api.creativetab.v1`; `KeyBindingHelper` -> `KeyMappingHelper`).
3. **Loom plugin id and remapping.** 26.x Fabric uses `id 'net.fabricmc.fabric-loom'`, plain `implementation` dependencies (no `mappings ...` line, no `modImplementation` in the example mod), Java 25 (`options.release = 25`, mixin `compatibilityLevel: JAVA_25`). Old `id 'fabric-loom'` + `mappings "net.fabricmc:yarn:..."` targets pre-26 versions. Migrate code with Loom `migrateMappings` or the Ravel IntelliJ plugin.
4. **Forge vs NeoForge.** `net.minecraftforge.*`, `MinecraftForge.EVENT_BUS`, `FMLJavaModLoadingContext.get().getModEventBus()`, `mods.toml` are Forge. NeoForge: `net.neoforged.*`, `NeoForge.EVENT_BUS`, mod bus injected into the constructor, `META-INF/neoforge.mods.toml` (since 1.20.5). `@Mod.EventBusSubscriber` became `@EventBusSubscriber` (NeoForge 21.x).
5. **`new ResourceLocation("modid", "x")`** constructor is private since 1.21; and the class is now `Identifier` (`Identifier.fromNamespaceAndPath`, `Identifier.withDefaultNamespace`).
6. **Item.Properties id (1.21.2+).** Items and blocks need `.setId(ResourceKey)` on properties before construction; registering `new Item(new Item.Properties())` throws.
7. **InteractionResult (1.21.2+).** `InteractionResultHolder` was removed; `Item.use` returns `InteractionResult` (`SUCCESS`, `CONSUME`, `PASS`, `FAIL`).
8. **Item model files (1.21.4+).** Client item definitions live in `assets/<ns>/items/<id>.json` pointing to `models/item/<id>.json`; only creating `models/item` leaves a missing-texture item.
9. **Data pack folder names (1.21+).** Singular: `function/`, `recipe/`, `loot_table/`, `advancement/`, `predicate/`, `item_modifier/`, `structure/`, `tags/function/`, `tags/block/`, `tags/item/`. Plural folders are silently ignored.
10. **Item NBT vs components (1.20.5+).** `give @p diamond_sword{display:{Name:...}}` is dead; use `[minecraft:custom_name=...]` components. `pack.mcmeta` uses `min_format`/`max_format` (1.21.9+); 26.3 data pack format 121.0, resource pack 97.1.
11. **Bedrock Script API 1.x vs 2.x.** `world.afterEvents.worldInitialize` -> `world.afterEvents.worldLoad`; `world.beforeEvents.worldInitialize` -> `system.beforeEvents.startup`; `runCommandAsync` removed (use `runCommand` or `system.runJob`); `isValid()` became a property `isValid`; touching `world` state at top level in 2.x throws (early execution). Custom components: flattened JSON keys instead of `minecraft:custom_components`.
12. **Bedrock manifest.** Script module: `"type": "script", "language": "javascript", "entry": "scripts/main.js"`; dependency `{"module_name": "@minecraft/server", "version": "2.10.0"}` (beta APIs need `-beta` versions + the Beta APIs experiment). Each UUID unique; bump `header.version` or the game keeps a cached copy.
13. **Client/server split (Java).** Calling client classes (`Minecraft`, rendering) from common code crashes dedicated servers; keep them in the client source set / `@EventBusSubscriber(value = Dist.CLIENT)`.

## Rendering
Java: OpenGL renderer (26.2 added an experimental Vulkan renderer; 26.3 snapshots introduced OIT transparency, unverified details). Mods render via block/item models (JSON), entity renderers/models, shaders through core shader JSON or loaders like Iris (third-party). Bedrock: RenderDragon; geometry `.geo.json`, materials, render controllers, Vibrant Visuals (`pbr` capability) and ray tracing packs; no custom shader code for add-ons.

## Physics
Fixed voxel collision + entity AABBs; no rigid-body engine. Java: velocity via `entity.setDeltaMovement(...)`, `entity.hurt...`/damage sources, `level.getBlockState(pos)`. Bedrock: `entity.applyImpulse(vec)`, `entity.applyKnockback(VectorXZ, vertical)` (2.0 signature), `minecraft:physics`, `minecraft:collision_box` components.

## Input
Java client: `KeyMapping` (Mojang name; Fabric `KeyMappingHelper` in `fabric-key-mapping-api-v1` (was `KeyBindingHelper` before 26.1), NeoForge `RegisterKeyMappingsEvent`), then send a custom payload to the server. Bedrock: no raw key input for add-ons; use item use events (`world.afterEvents.itemUse`), `playerButtonInput` events (verify per version), interact/attack events, forms.

## UI
Java: `Screen` subclasses (client), `AbstractContainerMenu` + `AbstractContainerScreen` for inventories, HUD via Fabric `HudElementRegistry`/NeoForge `RegisterGuiLayersEvent` (names version-sensitive). Bedrock: `@minecraft/server-ui` `ActionFormData`, `ModalFormData`, `MessageFormData` (2.2.0 stable), action bar/title via `player.onScreenDisplay`, JSON UI in resource packs (fragile), experimental HTML custom UI capability.

## Networking and multiplayer
Java is client/server even in singleplayer. All game logic must run on the server (`!level.isClientSide()`). Custom packets: `CustomPacketPayload` + `StreamCodec`; Fabric `PayloadTypeRegistry` + `ServerPlayNetworking`/`ClientPlayNetworking`; NeoForge `RegisterPayloadHandlersEvent`. Both sides need the mod unless it is server-only. Bedrock scripts run only on the server/host; clients get state via entity properties, scoreboards, dynamic properties are server-side; multiplayer through Realms, BDS or featured servers.

## Save data
Java: `SavedData` (per level, Codec-based `SavedDataType` in recent versions), NeoForge data attachments (`AttachmentType`) on entities/chunks/levels, Fabric Data Attachment API; item stacks use data components (`DataComponentType`). Data packs: scoreboards and `data storage`. Bedrock: `world.setDynamicProperty(k, v)`, `entity.setDynamicProperty(...)` (persisted with the world), scoreboard objectives, structure storage.

## Performance
Tick budget 50 ms. Avoid per-tick scans of all entities/chunks; cache registry lookups; do not load chunks from tick handlers; use tags not string compares. Mixins: prefer `@Inject`/`@WrapOperation` (MixinExtras) over `@Overwrite` for compatibility. Bedrock: watchdog terminates long script work; split loops with `system.runJob(generator)`; avoid `runCommand` in hot paths; `runInterval` with >1 tick where possible.

## Build and export
- Fabric: `./gradlew build` -> `build/libs/<mod>.jar`; dev run `./gradlew runClient` / `runServer`; datagen `runDatagen`. Distribute on Modrinth/CurseForge.
- NeoForge: `./gradlew build`, `runClient`, `runServer`, `runData`/`runClientData`.
- Data packs: zip with `pack.mcmeta` at root; `/reload` to reload functions.
- Bedrock: develop in `development_behavior_packs`/`development_resource_packs` (com.mojang), `/reload` reloads scripts; package as `.mcpack`/`.mcaddon`; TypeScript via `@minecraft/server` typings + a bundler (esbuild/Creator Tools). Marketplace: only approved Marketplace Partners can sell; free distribution via sites like MCPEDL.

## Common bugs and fixes
| Symptom | Cause | Fix |
|---|---|---|
| `Cannot resolve symbol 'ResourceLocation'` on 26.x | Renamed to `Identifier` | `Identifier.fromNamespaceAndPath(ns, path)` |
| `Item id not set` exception | Missing `Item.Properties.setId` | Use `setId(key)` or NeoForge `registerSimpleItem` |
| Purple-black item | Missing `assets/<ns>/items/<id>.json` | Add client item definition + model |
| Data pack functions not found | Plural folder (`functions/`) | Rename to `function/` |
| Pack "made for older/newer version" | Wrong `min_format`/`max_format` | 26.3: data 121, resource 97 |
| Dedicated server crash `ClassNotFound ... client` | Client class in common code | Move to client source set / Dist.CLIENT |
| Mixin `InvalidInjectionException` | Target method name/descriptor changed in new version | Check Mojang name in the decompiled 26.x jar |
| Bedrock script error "native function ... cannot be used in early execution" | World access at top level in 2.x | Move into `world.afterEvents.worldLoad` or `system.run` |
| Bedrock pack changes not loading | Cached pack, same version, wrong folder | Use development_* folders, bump version, `/reload` |
| `runCommandAsync is not a function` | Removed in 2.0 | `dimension.runCommand(...)` |

## Mapping from Roblox
| Roblox | Minecraft | Notes |
|---|---|---|
| Workspace / Instance tree | Level (dimensions) of blocks + entities; Bedrock `world.getDimension("overworld")` | No arbitrary object tree |
| Part | Block (`Block` + `BlockState`) or display entity (`block_display`, Java) | Voxel grid, 1 m cubes |
| Model | Structure (`.nbt`/structure blocks), entity with custom geometry | |
| Script (server) | Mod common code / data pack function / Bedrock behavior-pack script | |
| LocalScript | Java client entrypoint (`ClientModInitializer`, Dist.CLIENT) | Bedrock: none |
| ModuleScript | Java class / JS ES module | |
| RemoteEvent | Custom payload packets (`CustomPacketPayload`) | Bedrock: not needed (server-only scripts) |
| DataStore | `SavedData` / attachments; Bedrock dynamic properties | World-bound, not cloud |
| Players | `server.getPlayerList()`; Bedrock `world.getPlayers()` | |
| Humanoid | `LivingEntity`/`Player` (health, attributes) | Bedrock `minecraft:health` component |
| RunService.Heartbeat | `ServerTickEvents.END_SERVER_TICK` / NeoForge `ServerTickEvent.Post`; `#minecraft:tick`; `system.runInterval(fn, 1)` | 20 TPS fixed |
| RenderStepped | Client render events (`WorldRenderEvents` Fabric / `RenderLevelStageEvent` NeoForge) | Client only |
| TweenService | Display entity interpolation (`interpolation_duration`), animations in resource packs | |
| CollectionService tags | Registry tags (`#minecraft:logs`), entity tags (`/tag`, `addTag`) | |
| Attributes | Data components / attachments; Bedrock dynamic properties, entity properties | |
| ScreenGui | `Screen`/HUD layers; Bedrock forms, action bar | |
| UserInputService | `KeyMapping` (client) | Bedrock: item use / button input events |
| task.wait | Scheduled ticks / counter in tick handler; Bedrock `system.runTimeout`, `await system.waitTicks(n)` | |
| Studio playtest | `./gradlew runClient`; Bedrock `/reload` in a dev world | |
| Publishing | Modrinth/CurseForge jar; Bedrock Marketplace (partners) or .mcaddon | |

## Minimal example
Fabric 26.3: a "coin" item that gives score when used and tells the player.
```java
package com.example;

import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.creativetab.v1.CreativeModeTabEvents;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.CreativeModeTabs;
import net.minecraft.world.item.Item;
import net.minecraft.world.level.Level;

public class CoinMod implements ModInitializer {
    public static final String MOD_ID = "coinmod";
    public static final ResourceKey<Item> COIN_KEY =
        ResourceKey.create(Registries.ITEM, Identifier.fromNamespaceAndPath(MOD_ID, "coin"));

    public static final Item COIN = Registry.register(BuiltInRegistries.ITEM, COIN_KEY,
        new CoinItem(new Item.Properties().setId(COIN_KEY).stacksTo(64)));

    @Override
    public void onInitialize() {
        CreativeModeTabEvents.modifyOutputEvent(CreativeModeTabs.INGREDIENTS).register(tab -> tab.accept(COIN));
    }

    static class CoinItem extends Item {
        CoinItem(Properties p) { super(p); }
        @Override
        public InteractionResult use(Level level, Player player, InteractionHand hand) {
            if (!level.isClientSide()) {
                player.getItemInHand(hand).shrink(1);
                player.giveExperiencePoints(5);
                player.sendSystemMessage(Component.literal("+5 XP"));
            }
            return InteractionResult.SUCCESS;
        }
    }
}
```
Bedrock 26.50 manifest dependency for the script snippet above: `{"module_name": "@minecraft/server", "version": "2.10.0"}`.

## Sources
- https://piston-meta.mojang.com/mc/game/version_manifest_v2.json (official launcher manifest: 26.3 released 2026-09-15, 26.2 2026-06-16, 26.1 2026-03-24, 1.21.11 2025-12-09; 26.3 javaVersion 25)
- https://github.com/FabricMC/fabric-example-mod (build.gradle with `net.fabricmc.fabric-loom`, gradle.properties 26.3 / loader 0.19.5 / Fabric API 0.162.0+26.3, Identifier, mixin JAVA_25)
- https://meta.fabricmc.net/v2/versions/yarn (last Yarn = 1.21.11+build.6)
- https://docs.fabricmc.net/develop/porting/mappings/ (Yarn discontinued from 26.1, migrateMappings/Ravel)
- https://github.com/FabricMC/fabric-api (source tree: creativetab.v1.CreativeModeTabEvents, keymapping.v1.KeyMappingHelper, hud.HudElementRegistry, PayloadTypeRegistry)
- https://docs.fabricmc.net/develop/items/first-item (ResourceKey + setId + Registry.register, CreativeModeTabEvents, items/ definition path)
- https://docs.neoforged.net/docs/concepts/registries/ (DeferredRegister, mod bus, RegisterEvent; docs at 26.1)
- https://docs.neoforged.net/docs/items/ (DeferredRegister.Items, setId mandatory)
- https://docs.neoforged.net/docs/gettingstarted/modfiles (neoforge.mods.toml)
- https://github.com/NeoForgeMDKs/MDK-26.3-ModDevGradle (net.neoforged.moddev 2.0.148, neo_version 26.3.0.69-beta, ExampleMod.java)
- https://maven.neoforged.net/api/maven/latest/version/releases/net/neoforged/neoforge (latest 26.3.0.76)
- https://minecraft.wiki/w/Pack_format (community: data/resource pack formats; min_format/max_format)
- https://learn.microsoft.com/en-us/minecraft/creator/documents/scriptingv2.0.0overview (Script API v2 changes, startup/worldLoad, early execution)
- https://learn.microsoft.com/en-us/minecraft/creator/reference/content/addonsreference/packmanifest (manifest fields, format_version 2/3)
- https://registry.npmjs.org/@minecraft/server (2.10.0 latest 2026-09-15; 2.11.0-beta.1.26.50/52-stable tags)
- https://www.gameserverkings.com/knowledge-base/minecraft/updating-your-server-version/ (community: YY.D.H scheme)

## Confidence and gaps
- High: Java/Bedrock version numbers and dates, Fabric/NeoForge build setup, Yarn end, Script API 2.x changes, Identifier rename.
- Medium: HUD API usage details; Bedrock manifest engine-version triple for 26.x; NeoForge `@EventBusSubscriber` history.
- Not verified: 26.3 content/feature list, Bedrock `playerButtonInput` event name, Bedrock Marketplace 2026 policy changes. No code was compiled.
