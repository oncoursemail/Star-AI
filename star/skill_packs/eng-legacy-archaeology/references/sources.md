# Sources for eng-legacy-archaeology

Written in STAR's own words on 2026-10-13. The method combines general legacy-code practice with what the reverse-engineering projects in `docs/research/reverse-engineering/` did. Not verified with the STAR knowledge service /api-lookup: the pack names no Roblox API beyond common service and class names (DataStore, RemoteEvent, RemoteFunction, ModuleScript), which are described by the Creator Documentation pages below.

- https://martinfowler.com/bliki/StranglerFigApplication.html (Martin Fowler, strangler fig application, revised 2024-08-22: gradual replacement around seams)
- https://en.wikipedia.org/wiki/Characterization_test (characterization / golden master tests; term coined by Michael Feathers)
- https://rojo.space/docs/v7/ (Rojo: Roblox projects as files, so Git history, diff and search work)
- https://create.roblox.com/docs/cloud-services/data-stores (Roblox data stores: the persistence layer whose records must stay compatible)
- https://create.roblox.com/docs/scripting/module (ModuleScripts: the replacement for _G / shared state)
- https://create.roblox.com/docs/reference/engine/datatypes/Random (Random.new(seed): seeded generators for reproducible tests)
- https://github.com/OpenRCT2/OpenRCT2 (incremental function-by-function replacement while the game stayed playable)
- https://github.com/zeldaret/oot (matching decomp: byte-exact oracle, then naming and documentation passes)

Book: Michael Feathers, Working Effectively with Legacy Code (Prentice Hall, 2004): seams, characterization tests, "legacy code is code without tests".
