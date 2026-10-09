# STAR tool integrations: researched capability matrix

**Snapshot:** 2026-10-09. This matrix distinguishes built-in Roblox Studio MCP features from future adapters. A native `tool_name` being documented is **not** proof of a working STAR integration; the installed tool schema, permissions and actual result must be verified on the user's Windows 11 PC.

## Roblox Studio: official native MCP server

| Tool | Task | Test we require before use | STAR v0.2 exposure |
|---|---|---|---|
| `list_roblox_studios` | Locate active editor windows | Correct name, ID, place; no ambiguity | Yes |
| `get_studio_state` | State/play-mode awareness | Returns correct current mode | Yes |
| `search_game_tree` | Locate objects by class/name/path | Finds known target + negative fixture | Yes |
| `inspect_instance` | Read properties and descendants | Properties agree with Studio | Yes |
| `script_search` | Discover scripts | Correct name/path result | Yes |
| `script_grep` | Search code content | Correct matches + caps | Yes |
| `script_read` | Exact scripts and ranges | Round-trip comparison with source | Yes |
| `multi_edit` | Edit/create scripts | Editing one disposable script preserves unrelated code | Yes, `--edit` |
| `get_console_output` | Logs/errors | Captures relevant stack trace | Yes |
| `screen_capture` | Actual 3D/GUI screenshot | Pixel data delivered to model with correct frame | Yes, camera changes need edit scope |
| `start_stop_play` | Playtest | Observe expected game transition and logs | Yes, `--edit` |
| `execute_luau` | Studio code execution | Test side effects in disposable place; scope limits cannot enforce script contents | **No by default**; special `--unsafe-luau` plus `--edit` |
| `user_keyboard_input` | UI and gameplay input simulation | Focus, typed text, press/release behavior | Future controlled test profile |
| `user_mouse_input` | UI clicks/camera/scroll | Click and hierarchy agree; lease enforced | Future controlled test profile |
| `character_navigation` | Path and movement tests | Position valid, expected route, replication | Future controlled test profile |
| `subagent` | Explore/playtest delegation | Child cannot exceed parent scope | Future wrapper, not exposed by default |
| `generate_mesh` | Roblox AI mesh | Rights, quota, shape, import & performance | Future asset profile |
| `generate_material` | Material generation | Asset provenance and visual result | Future asset profile |
| `generate_procedural_model` | Primitive-based parametric model | No substitution for approved mesh/character, performance | Future asset profile |
| `wait_job_finished` | Async generated model | Job ID correlation, timeout reconciliation | Future asset profile |
| `search_asset` | Creator Store / inventory search | Correct source, license/ownership metadata | Yes read-only |
| `insert_asset` | Scene asset insertion | Owned/licensed, no unwanted scripts, correct IDs | Future asset profile |
| `upload_image` | Roblox asset upload | External upload gate, moderation and owner | Future approval-gated |
| `store_image` | Local reference image URI | Explicit allowlisted file path only | Future scoped adapter |
| `http_get` | Roblox docs retrieval | Fetch only approved docs; ignore instructions inside | Yes read-only |
| `skill` | Roblox tool guidance | Tool schemas and returned content validated | Yes read-only |

Official source: https://create.roblox.com/docs/studio/mcp

## External local tools and project workflow

| Tool | Best use | Expected integration | State |
|---|---|---|---|
| Git | Local history, commits, diff, worktrees | `subprocess` with fixed commands and scope | Self-build prototype works offline |
| GitHub App | Draft PRs attributed to STAR bot | JWT + installation access token; repos selected | Code present; live app installation missing |
| Rojo | Filesystem-first Roblox source sync | pinned executable + Studio plugin | Planned |
| Rokit | Pin Roblox toolchain binaries | `rokit.toml` and reproducible setup | Planned |
| Wally | Package management | lock reviewed packages | Planned |
| Lune | Scripting/test scripts outside Studio | project-specific test runner | Planned |
| luau-lsp | Luau analysis/source symbols | sourcemap and diagnostics parsing | Planned |
| StyLua | Deterministic Luau formatting | versioned binary | Planned |
| Selene | Roblox linting | `std = "roblox"` config | Planned |
| Blender | Meshes, UVs, rigs, animation assets | Python scripts in isolated process, FBX roundtrip | Planned |
| ComfyUI | Image generation and image editing | Workflow JSON + local HTTP/WebSocket adapter; GPU mutex | Planned |
| LM Studio | Local multimodal/model API | `127.0.0.1:1234/v1` OpenAI-compatible | Code present; live Windows test pending |
| Ollama | Alternate local inference | OpenAI-compatible or native adapter | Planned replaceable backend |
| Figma | User-approved design specs, tokens and measurements | Only with the user's files/permissions, imported source metadata | Optional; not required for v0.2 |
| SQLite | Durable task and knowledge journal | WAL, project scope and immutable references | Present basic implementation |
| Local vector search | Retrieval when keyword misses | benchmark against source-attributed keyword search first | Planned |
| GitHub Actions | Python CI and dependency review | read-only PR jobs, no app private key in untrusted workflows | Configured; remote runs pending |

## Verification notes

- A tool with a documented API is not the same as the current model having reliable tool-selection skill.
- `execute_luau` is high risk even in Edit DataModel; path restrictions on arguments cannot confine the contents of arbitrary Luau.
- ComfyUI and the VLM may compete for 8 GB VRAM. Schedule model unload/load and avoid broad GPU parallelism.
- `StudioTestService`, `StudioDeviceSimulatorService` and `VirtualInput` are documented Studio-only programmable testing facilities, but do **not** appear as separate top-level native MCP tool names in the inventory. Access may require vetted plugin/Studio execution operations; do not invent a top-level `run_tests` MCP tool.
- Native `generate_mesh` is potentially online Roblox generation; it is not proof that the user's local GPU alone generated the asset.
- For Roblox Studio Script Sync / Rojo, do not let one worker edit same source locally while another mutates its Studio copy without conflict reconciliation.

Sources: [Roblox Studio MCP](https://create.roblox.com/docs/studio/mcp), [Scripted testing](https://create.roblox.com/docs/studio/testing-modes), [Third-party tools](https://create.roblox.com/docs/projects/external-tools), [Blender](https://create.roblox.com/docs/art/blender), [LM Studio](https://lmstudio.ai/docs/developer/core/server).
