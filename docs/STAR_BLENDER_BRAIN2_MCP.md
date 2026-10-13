# STAR Brain 2 — own local Blender MCP and Roblox-ready asset pipeline

Date: 2026-10-11. Branch: star/blender-brain2-20261011. **Draft, opt-in.** This is a first-party Blender MCP connector and real trusted Blender script workflow. It is not Blender itself, not an automatic installer, not an unrestricted Blender Python REPL, not proof of photo-realistic 1:1 replicas, and not a Roblox Studio importer.

## What is actually implemented

| Layer | Implementation | What it can prove |
| --- | --- | --- |
| Brain 2 routing | star/desktop_core.py and star/agent.py | A relevant Blender/3D task can attach authorized MCP tool schemas; unrelated chats do not start Blender. |
| STAR Blender MCP | star/blender_mcp.py | Real MCP SDK tools/list and tools/call using local in-memory transport, plus explicit-operator stdio mode. No HTTP listeners or third-party addon. |
| Permissions | Settings.blender_enabled / blender_edit / blender_executable | Off by default; status/probe separate from project writes; build hidden until owner permits it. |
| Blender worker | star/blender_worker.py | Uses real Blender bpy to generate new .blend + .glb; optional fixed-camera 640×360 PNG. Only trusted worker code, not user Python. |
| Asset grammar | star/blender_bridge.py | Validated authored scene JSON (48 bounded object recipes max): cube, cone, cylinder, sphere, faceted rock, stylized tree, arched masonry and pitched roof, plus camera, material color, sky/ground. |
| Isolation | project-named hashed directory under STAR data/blender/jobs | Unique immutable job IDs; no overwriting existing Blender files; only inspect STAR's own job IDs under the selected project. |
| Desktop | BlenderPanel, Qt status + testBlender, saved settings | Owner can enable connection and independently permit scene writes; check local installed Blender. |
| Packaging | Windows workflow and scripts/build_windows.ps1 | Bundles the real worker source in the packaged STAR.exe, not just the Python module bytecode. |

## How the Blender connector works

~~~text
User prompts Brain 2 to create a Blender model
  -> Relevant task-intent gate + saved Blender owner permission
    -> Agent sees star_blender_status / probe / inspect / (if write-approved) build_scene
      -> first-party STAR Blender MCP (MCP SDK, local in-memory session)
        -> schema validation, project isolation, process-time budget
          -> vetted Blender executable, --background --factory-startup
            -> bundled blender_worker.py, JSON recipe, no arbitrary Python
              -> project folder: scene.blend + scene.glb + optional preview.png
                -> Blender/Studio review and voluntary approved asset import
~~~

All Blender jobs use a new directory. Source work, other open Blender files, other projects and existing Roblox places remain untouched. The connector **does not** install software, call a shell tool from model-supplied text, fetch assets, upload art or publish Roblox games. Even so, Blender is a real native program and is not a security sandbox: choose a trusted official installation.

## Install Blender locally once

1. Install Blender from its official source: https://www.blender.org/download/ . STAR does not download it silently. On Windows the binary is often under Program Files/Blender Foundation/Blender X.Y/blender.exe; in PowerShell, \`Get-Command blender\` may show an existing PATH installation.
2. In STAR **Tools → Blender for Brain 2**, choose **Enable Blender MCP**. Leave **Allow Blender scene creation** off for read-only discovery and version checks.
3. Leave **Blender executable** blank for PATH/common Windows install search, or enter the full trusted local blender.exe path.
4. **Save connector settings**. Then select **Test local Blender** to run a harmless background version probe; a path existing on disk is not proof that Blender works.
5. If the check succeeds, enable **Allow Blender scene creation** and save again. Brain 2 can now use \`star_blender_build_scene\` on explicitly relevant Blender modeling requests in tool-using Chat modes.
6. Files are saved locally at \`%APPDATA%\STAR\blender\jobs\<project-slug-hash>\<job-id>\` on Windows. A Blender job contains \`scene.blend\`, \`scene.glb\`, \`scene.json\`, \`result.json\`, and \`worker.log\`; optionally \`preview.png\`.

The configured binary path is a *local executable*, not a Python script, remote MCP URL, command line, plugin install path, or website. No separate credentials are required.

## CLI proof without a model

For a source checkout with its Python dependencies installed:

~~~powershell
python -m star.blender_bridge --settings "$env:APPDATA\STAR\settings.json" --probe
python -m star.blender_bridge --settings "$env:APPDATA\STAR\settings.json" --scene examples\blender\enchanted_forest.json
python -m star.blender_bridge --settings "$env:APPDATA\STAR\settings.json" --scene examples\blender\volcanic_crypt.json
# Use the returned job_id to inspect only that STAR project:
python -m star.blender_bridge --settings "$env:APPDATA\STAR\settings.json" --inspect <job-id>
~~~

For external MCP clients that support stdio:

~~~json
{
  "mcpServers": {
    "star-blender": {
      "command": "python",
      "args": ["-m", "star.blender_mcp", "--settings", "C:\\Users\\YOUR_USER\\AppData\\Roaming\\STAR\\settings.json"]
    }
  }
}
~~~

This example needs to be adapted to the **trusted local STAR Python environment** and actual settings location. STAR Desktop does **not** require an external client, and it does not expose a network port. The stdio server inherits the same saved project scope and allowlist.

## How to request work from Brain 2

Example: "Use Blender to build an editable stylized forest clearing with three trees, a wooden cottage, a curved stone arch and a camera at (16,-24,12). Save a GLB for Roblox Studio. Render a preview and report what you actually created."

For higher quality, describe recognizable modular architecture and approximate dimensions. The first-party worker generates a **first-pass 3D scene**, not a photographically reconstructed map. Its tree and arch operators are authored stylized geometry. Genuine 1:1 visual matching, skinned wind animation, original scene assets, detailed UV/PBR baking, particle effects, terrain blending and gameplay lighting still need separately validated tooling and Studio integration.

### Roblox import

Roblox's official Blender workflow explicitly discusses coordinate/scale differences (Blender Z-up vs Studio Y-up). Studio imports .gltf/.glb, .fbx, and .obj. STAR emits GLB as a predictable starting point. Open Roblox Studio's **File → Import** and inspect geometry, materials, size, orientation, collisions and warnings. STAR intentionally does not auto-upload these assets or apply edits to an existing Roblox experience.

- https://create.roblox.com/docs/art/blender
- https://create.roblox.com/docs/studio/importer
- https://create.roblox.com/docs/art/modeling/surface-appearance

## Security review & bounded autonomy

- Input schema uses explicit enums, finite numeric positions/scales and limited counts; N=48 scene entries maximum, 24 KB recipe maximum, strict names, no URLs, file paths, scripts, plugins or user-chosen export directory.
- The parent is an SDK-based first-party local MCP endpoint with no public listener. Input schema validation is repeated inside the Blender controller; read and write operations are allowed by host settings only, never instructions in model output or untrusted returned text.
- The only subprocess is the configured local Blender binary with fixed flags \`--background --factory-startup --python\` pointing at STAR's bundled trusted worker and a newly created private recipe file. There is **no** general \`execute_blender_code\`, REPL, \`--python-expr\` with model content, downloaded addon, network search or external asset import in the write tool. \`--python-expr\` is used only for a constant trusted version probe.
- A short environment allowlist omits credentials such as Roblox API keys and cloud model secrets. The tool returns a sanitized error instead of private worker stdout. The full worker log remains under the owner's local STAR profile.
- Child processes are time-bounded and killed on cancellation or timeout; partial outputs are not certified complete. All output paths are composed by the host under STAR's local app-data directory, never accepted from a model. Each write gets a fresh random ID.
- An enabled read-only connector cannot inspect arbitrary local Blender files, and disabling Blender blocks past-job inspection. Existing Roblox Studio policy and publication safeguards remain intact.
- No automatic self-training or source-image ingestion is performed; any future learning pipeline must verify the license, ownership and independent evaluation.

## Open-source and technical research

- Official Blender docs / Python API: https://docs.blender.org/api/current/ and https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html
- Blender 5 EEVEE engine identifier change: https://developer.blender.org/docs/release_notes/5.0/python_api/
- Official Model Context Protocol Python SDK: https://github.com/modelcontextprotocol/python-sdk and https://py.sdk.modelcontextprotocol.io/advanced/low-level-server/
- Community Blender MCP (inspiration **only**, not installed in STAR): https://github.com/ahujasid/mcp-for-blender ; security-focused fork: https://github.com/soozs1/Blender-MCP . Both expose powerful Blender Python functions; integrating those by default would expand privileges.
- Roblox scene import and asset content: https://create.roblox.com/docs/studio/importer and https://create.roblox.com/docs/art/blender
- Existing STAR art reference research and future comparisons: docs/STAR_VISUAL_CRAFT_RESEARCH_2026.md ; environment craft proposal PR #110, https://github.com/oncoursemail/Star-AI/pull/110 .

## Acceptance checklist

**Automated:** \`python -m compileall -q star\`; \`python -m pytest -q\`; \`cd frontend && npm test\`, TypeScript typecheck/build and packaged smoke tests. The new tests exercise a real SDK MCP memory session with fake Blender subprocess outputs, malicious arguments, isolation, disabled write, status and UI toggles. These do not prove Blender rendered.

**Manual Windows/Blender:** test actual official Blender 4.x/5.x binary; verify nonempty editable .blend, .glb geometry and PNG; inspect exported meshes in the Studio Importer; measure job wall time, memory, output size and rendered quality, including failure and timeout cases. Test installer upgrade preservation and the packaged executable path. Before any version is described as released or production-ready, attach screenshot and native device evidence.

**Future work (not shipped):** full Blender modeling and texture-baking graph, skinned and physics foliage, camera-lock reference matching with perceptual and semantic scoring, animation strip validation, visual artifact preview UI, imported Roblox mesh reconciliation and artist-reviewed self-improvement gated by held-out benchmarks. These should be separate small audited PRs, not unbounded powers granted to Brain 2.

## Update 2026-10-13: the Blender that runs ON brain 2 (live GUI, official Blender Lab MCP)

The sections above describe the local, headless, recipe-only connector. A second, opt-in route lets STAR work in the real
Blender 5.2 GUI that runs on brain 2 (the second STAR server), look at it like a person (viewport screenshots from set camera
angles, quick renders) and export GLB/FBX for Roblox. Setting `blender_brain2` (needs `blender_enabled`; `blender_edit` for
anything that changes a scene or starts Blender); off by default. The tool is `star_blender` (`star/blender_brain2.py`); it reaches the
official Blender Lab MCP add-on through an operator-chosen ssh command, like the Studio connector, and model-written Python
(`run_bpy`) passes an AST allow-list first. Details, measurements, security model and the live demo evidence:
`docs/agents/blender-brain2-20261013.md` and `docs/agents/blender-brain2-20261013/`. Launcher and setup script: `server/brain2_blender/`.
