# Sources for engine-minecraft

Official documentation reviewed 2026-10-13 (accessed by web, not by a live engine run):

- https://piston-meta.mojang.com/mc/game/version_manifest_v2.json (26.3 released 2026-09-15; Java 25 runtime; 1.21.11 last 1.x)
- https://github.com/FabricMC/fabric-example-mod (Loom plugin id, gradle.properties for 26.3, Identifier, mixin config)
- https://github.com/FabricMC/fabric-api (CreativeModeTabEvents, KeyMappingHelper, ServerTickEvents locations)
- https://docs.fabricmc.net/develop/porting/mappings/ (Yarn discontinued from 26.1)
- https://docs.fabricmc.net/develop/items/first-item (item registration with setId, items/ definition files)
- https://docs.neoforged.net/docs/items/ (DeferredRegister.Items, setId mandatory)
- https://github.com/NeoForgeMDKs/MDK-26.3-ModDevGradle (NeoForge 26.3 MDK, ModDevGradle)
- https://learn.microsoft.com/en-us/minecraft/creator/documents/scriptingv2.0.0overview (Script API v2 changes)
- https://learn.microsoft.com/en-us/minecraft/creator/reference/content/addonsreference/packmanifest (manifest.json)

These are documentation references; no editor/compiler run is claimed for the skeleton.
