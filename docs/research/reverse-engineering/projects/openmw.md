# OpenMW — reverse-engineering case study (researched 2026-10-13)

OpenMW is a from-scratch, GPL-3.0 reimplementation of the engine behind The Elder Scrolls III: Morrowind (2002). It does not run or patch the original executable. Instead it reads the original data files (ESM/ESP, BSA, NIF) and reproduces the game's behaviour. It also ships OpenMW-CS, a replacement for the Construction Set, and a sandboxed Lua scripting API. Players must own Morrowind.

## 1. What it is and its 2026 state

- Latest stable release: **0.51.0, released 2026-06-19**. The GitHub README on master already lists 0.52.0 as the in-development version (as of 2026-10-13). Before that, 0.50.0 shipped on 2025-11-07.
- 0.51.0 lets mods create magic effects through Lua, adds a Lua "load context" that can modify records after content files load, and adds terrain vertex painting to OpenMW-CS. It also removes the fixed-function graphics pipeline and the legacy lighting method. The save format changed again, so 0.51 saves will not load in older builds.
- Licence: GPL-3.0. Bundled fonts carry their own licences. The project says it is an unaffiliated hobby effort, not supported by Bethesda or ZeniMax.
- Status per the README: the Morrowind, Tribunal and Bloodmoon main quests are completable. Some rare side-quest issues remain, and a milestone list tracks the work left before "1.0". Development is hosted on GitLab, with a GitHub mirror.
- History (Wikipedia): first public release 0.1.0 in June 2008. 0.37 replaced Ogre3D with OpenSceneGraph, with large performance gains. The TES3MP multiplayer fork became playable in 2017.

## 2. How the original was reversed

- The FAQ says OpenMW and OpenMW-CS were "written from scratch". The ESM/ESP (records), BSA (archives) and NIF (NetImmerse meshes) loaders were built from community documentation and online information. None of the official pages I fetched described disassembling morrowind.exe.
- Behaviour such as formulas, AI and the quirks of the original scripting language was matched by observing the original game. I could not read the OpenMW wiki "Research" pages because Anubis bot protection blocked the fetch. Treat the specific research methods as **unverified**.
- The original scripting language (mwscript) was reimplemented (the FAQ calls it "reimplemented and improved"). The README notes that its script compiler is stricter than the original, so some old mods fail because they relied on quirks of the original engine.
- Mods and tools that hook morrowind.exe, such as MWSE, MGE XE and MCP, cannot work. OpenMW reimplements some of their features natively, for example post-processing shaders and object paging for distant land.

## 3. Workflow: matching, non-matching or clean-room

- **Black-box / behavioural reimplementation, non-matching.** There is no attempt at binary or structural equivalence with the original. The target is observable behaviour plus data-format compatibility. "Black box" is my label: the official pages I fetched only say "from scratch".
- This gives full freedom of architecture: a new renderer (OSG), physics, navmesh pathfinding, multithreading and Lua. The price is a long tail of behaviour mismatches that have to be found through bug reports.
- Original bugs are not preserved by default. Compatibility is defined as "existing content works", not "identical code".

## 4. Testing and verification

- The C++ unit-test binaries (`components-tests`, `openmw-tests`, `openmw-cs-tests`) are built in CI (per CI config references found while searching).
- **Lua integration tests**: the engine runs headless under a virtual X server against the open "example-suite" game. Test scripts drive player controls and compare the results, such as positions, with tolerance matchers. Later additions cover menu scripts, save/load, and mwscript-to-magic interactions (MR !4511). These details come from search summaries of the merge requests, not from reading the test code itself, so treat them as partly unverified. This is the key trick: the tests run on free content, so CI never needs the copyrighted Morrowind data.
- The release-candidate cadence uses several RCs per release (0.49 went to RC9), with community playtesting of real mod lists.

## 5. Structuring a large legacy codebase

- The repo is split into `apps/` (openmw, openmw-cs, launcher, tools such as ESMTool) and `components/` (shared libraries for formats, VFS, Lua, settings). The game and the editor share the same loaders, which avoids format drift between the two.
- The **Lua API is versioned** (API revision 163 per the docs page fetched). Renames go through deprecation, for example `factionReaction` became `factionReputation` with the old name kept as deprecated in 0.51.
- Mods are resolved through layered `data=` directories loaded in order, so later entries override earlier ones. Content files are ordered separately in the launcher.
- OpenMW-CS can author standalone games that do not need Morrowind. The Example Suite is the reference.

## 6. Engine architecture insights

- **Lua script classes** (official docs):
  - *Global* scripts are always active and can see the whole world.
  - *Local* scripts are attached to one object, are active only while its cell is active, can change only their own object, and have read-only access to others.
  - *Player* scripts add UI and camera control.
  - *Menu* scripts run with no game loaded.
- **Multiplayer-ready by design:** the split mirrors TES3MP's client/server model, with global scripts on the server and local scripts on the client. Scripts talk only through **asynchronous events**, delivered one frame later in single-player. Events carry one serializable argument and cannot return values. Handlers run in reverse load order, and returning false stops the chain.
- **Sandbox:** no OS access, and no native DLLs or precompiled bytecode. `require` is limited to approved packages and data-folder Lua files. The language is Lua 5.1/LuaJIT with some 5.2/5.3 additions. Teal type declarations are experimental.
- **Persistence:** state survives only through `onSave`/`onLoad`. Data must be serializable: no functions, metatables, shared references or cycles. Timers come in a saved "reliable" kind and an unsaved kind.

## 7. Legal history and lessons

- No takedowns were found. The legal posture rests on three things: shipping no assets, requiring the user's own installation, writing the code from scratch, and declaring no affiliation (FAQ).
- The asset-free Example Suite lets the project test, demo and onboard developers without touching proprietary data.

## 8. Transferable lessons for STAR

1. **Design scripting for client/server from day one.** OpenMW's global/local split is the same rule as Roblox server Scripts vs LocalScripts. When STAR generates Luau, server code should own world mutation, client code should touch only its own presentation, and the two should talk through validated RemoteEvents, not shared state.
2. **Events take one serializable payload and return nothing.** This maps directly onto RemoteEvent payload hygiene. STAR should flag Instances-as-identity, functions, metatables and cyclic tables in remote or DataStore payloads.
3. **Explicit save hooks with a serializability contract.** This is a good template for DataStore profile schemas: plain tables only, plus a version field and migrations.
4. **Version the scripting API and deprecate rather than break.** For STAR's own tool/plugin APIs, keep old names as aliases with warnings for one cycle.
5. **Test on free content.** Build headless integration tests on an open fixture game, the way OpenMW uses the Example Suite. For Roblox that means a minimal test place plus TestEZ/Jest-Lua run in CI, not a live production place.
6. **Behavioural parity before structural parity.** When porting a legacy Roblox game (for example deprecated APIs or `wait()`-based code), define "correct" as observable behaviour checked by tests, not a line-by-line translation.

## Sources

- [OpenMW FAQ (official)](https://openmw.org/faq/)
- [OpenMW 0.51.0 release announcement](https://openmw.org/2026/openmw-0-51-0-released/)
- [OpenMW GitHub repo/README](https://github.com/OpenMW/openmw)
- [OpenMW releases page](https://github.com/OpenMW/openmw/releases)
- [OpenMW Lua scripting overview (docs)](https://openmw.readthedocs.io/en/latest/reference/lua-scripting/overview.html)
- [OpenMW docs index](https://openmw.readthedocs.io/en/latest/)
- [Modding OpenMW vs Morrowind (docs)](https://openmw.readthedocs.io/en/latest/reference/modding/differences.html)
- [Wikipedia: OpenMW](https://en.wikipedia.org/wiki/OpenMW)
