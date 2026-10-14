# Major game engines: Unity, Unreal Engine 5, Godot 4

Researched 2026-10-13 so STAR can answer questions about the three major engines as well as it answers Roblox ones.

| Engine | Deep reference | Skill packs (`star/skill_packs/`) | Golden suite (prose-checked) |
|---|---|---|---|
| Unity 6 | [unity.md](unity.md) | `unity-scripting-core`, `unity-netcode-data`, `unity-rendering-performance` | `evals/unity/golden-tasks-diagnosis-v1.json` (UNI-D01..06) |
| Unreal Engine 5 | [unreal.md](unreal.md) | `unreal-cpp-gameplay`, `unreal-replication-gas`, `unreal-rendering-performance` | `evals/unreal/golden-tasks-diagnosis-v1.json` (UE-D01..06) |
| Godot 4 | [godot.md](godot.md) | `godot-migration-and-pitfalls`, `godot-multiplayer-data`, `godot-rendering-performance` | `evals/godot/golden-tasks-diagnosis-v1.json` (GD-D01..06) |

Each reference covers versions as of October 2026, architecture and lifecycle, project layout, scripting idioms and
pitfalls, rendering, physics, animation, UI, input, networking, save data, profiling, build and deploy, a table of common
bugs with fixes, and a Roblox-to-engine concept map. Every section ends with the official pages it was checked against;
anything not confirmed on an official page is marked *(unverified)*. Unity (CC BY-NC-ND) and Epic documentation are not
copied: the text is STAR's own wording with links. Godot documentation is CC BY 3.0 (class reference MIT).

## How STAR uses them

- **Skill packs** are chosen in code (`star/skill_packs/__init__.py`): an engine pack is added to a turn only when the
  prompt names that engine (`_UNITY_CONTEXT`, `_UNREAL_CONTEXT`, `_GODOT_CONTEXT`) and the pack's topic; Roblox packs
  are added only when no other engine is named. Roblox golden-task prompts never reach an engine pack
  (`tests/test_major_engine_packs.py`), so their requests are byte-identical.
- They are **off by default**, like every pack that has not passed the gate (docs/evals.md). Turn them on with
  `STAR_SKILL_PACKS=all` or a comma list of names. In agent mode the model can also load any of them, and its
  `references/sources.md`, on demand through `star_skill_catalog` / `star_skill_load` / `star_skill_reference`.

## Putting a pack through the gate

The suites use the existing golden-task schema with `"code": false` and prose-scope checks (the grader extracts only Luau
code blocks, so C#, C++ and GDScript are judged by what the answer states outside code fences). Reference answers
(`reference/<ID>.md` must pass, `<ID>.bad.md` must fail) are checked offline by `tests/test_major_engine_packs.py`.

```text
python -m star.evals routing --suite evals/unity/golden-tasks-diagnosis-v1.json
python -m star.evals run --suite evals/unity/golden-tasks-diagnosis-v1.json --out evals/results/baseline-unity-diagnosis-v1.json --packs off
python -m star.evals run --suite evals/unity/golden-tasks-diagnosis-v1.json --out evals/results/pack-unity-core.json --packs unity-scripting-core
python -m star.evals gate --baseline evals/results/baseline-unity-diagnosis-v1.json --candidate evals/results/pack-unity-core.json --allow-partial
```

No suite has been run against the STAR Server yet, so there is no baseline and no pack is enabled by default.

## Known gaps

- No engine documentation is indexed by STAR Knowledge (`doc_grounding` routes Unity/Unreal/Godot questions to "none");
  Unity docs are link-only by licence (`server/knowledge/sources/unity-*.json`) and there is no Unreal manifest.
- The graders cannot compile or run C#, C++ or GDScript; the suites test diagnosis and API knowledge, not working code.
- Engine facts move fast: re-check the version tables at each engine release (Unity 6.x/7, UE 5.8/UE6, Godot 4.7+).
