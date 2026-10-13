# Windows package-data completeness audit — 2026-10-13

## Method and measured scope

Review of GitHub star/next covered 195 Python files under star/.
The test parses the real Python AST and inventories all 20 modules referencing
__file__. Twelve modules use package-root locations for static runtime or
optional resources; eight anchor the source path for developer-only work,
safety checks, or external content. Reads of owner-selected projects and
private runtime data are deliberately not bundled.

Tests parse both real PyInstaller commands in scripts/build_windows.ps1 and
.github/workflows/windows-desktop.yml into --add-data, --hidden-import,
--collect-all, and --collect-submodules sets. They require data/hidden/submodule
sets to match and explicitly allow local-only --collect-all pypdf, docx, pptx,
openpyxl. A metamorphic test removes a real flag from each category and proves
the comparison rejects new drift. The existing inert PowerShell builder harness
checks that the actual local builder passes star/data to PyInstaller.

The change here adds --add-data 'star/data;star/data' to the local builder,
matching CI. No protected workflow or evals files are edited, and no local
installer, user profile, network connection or real Studio run is involved.

## Twelve reviewed static package-root reads

Yes means declared in the PyInstaller build command, not real installed-app
verification. The four missing non-evaluation resources are present in source
but absent from both build commands.

| Module | File or directory read | Runtime role | Local | CI | Verdict |
| --- | --- | --- | --- | --- | --- |
| star/react_shell.py | frontend/dist/index.html | React UI generated bundle | yes | yes | bundled |
| star/build_info.py | star/build-info.json | Generated source attribution | yes | yes | bundled |
| star/skill_packs/__init__.py | star/skill_packs/*/SKILL.md | Reviewed packs | yes | yes | bundled |
| star/blender_bridge.py | star/blender_worker.py | Worker script | yes | yes | bundled |
| star/design_db.py | star/data/design/ui-ux-pro-max/*.csv | Four design tables | yes (fixed) | yes | bundled |
| star/learned_week.py | optional star/skill_packs/learning_bundle.json | Learning import | parent yes | parent yes | parent bundled, optional file not present |
| star/lesson_import.py | star/skill_packs/lessons_bundled.json | Lessons import | yes | yes | bundled |
| star/character_lifecycle_lessons.py | docs/lessons/roblox-character-lifecycle.md | Optional Roblox lessons | no | no | missing |
| star/build_planner.py | examples/roblox-templates/** | Roblox starter source | no | no | missing |
| star/roblox_api_confusions.py | data/roblox_api_confusions.json | Optional API confusion evidence | no | no | missing |
| star/voice/catalog.py | star/voice/voices.json | Voice Settings | no | no | missing |
| star/studio_milestones.py | evals/studio/{obby,tycoon,rounds}.json | Optional build-plan checks | no | no | must extract only reviewed public runtime data |

Result: 12 read sites, seven bundled sites (five distinct package resource
paths), five missing or needing a separate safe extraction. The test does NOT
misrepresent the currently incomplete bundle as complete.

## Other eight reviewed package-root anchors

| Module | Why it is not a fixed resource to include |
| --- | --- |
| star/cli.py | Developer source checkout root |
| star/eval_gate.py | Developer-only evaluation result inputs |
| star/eval_runner.py | Developer-only held-out test suite and external files |
| star/failure_ledger.py | Development evaluation prelude |
| star/general_knowledge_benchmark.py | Benchmark source-code identity |
| star/github_app.py | Security check blocks loading private key files from repository |
| star/media_actions.py | Owner-installed ComfyUI is external, never bundled |
| star/shared_brain/improve.py | Development verifier source-file hash |

Additional read_text/read_bytes/open calls in the 195 files accept dynamic
project files, private profiles, uploads, downloads, temporary media or
operator-provided evaluations. They are runtime inputs, not fixed repository
assets. The AST inventory protects source-root anchors and is not a general
proof about every dynamically constructed filesystem path.

## Exact workflow change recommended to the lead

In .github/workflows/windows-desktop.yml, the "Package STAR.exe with vector
assets" PyInstaller command already contains --add-data
'star/data;star/data'. Immediately before the current
--add-data 'star/blender_worker.py;star', append these four pairs, preserving
the existing PowerShell line-continuation syntax:

~~~text
--add-data 'docs/lessons;docs/lessons'
--add-data 'examples/roblox-templates;examples/roblox-templates'
--add-data 'data/roblox_api_confusions.json;data'
--add-data 'star/voice/voices.json;star/voice'
~~~

Add the same four entries to scripts/build_windows.ps1 when the lead
authorizes a synchronized follow-up. Do not blindly package evals/studio:
instead review and extract only redistributable public milestone metadata
into star/data, update the loader, and test a real packaged build-plan flow.

Local PyInstaller additionally uses --collect-all for pypdf, docx, pptx,
openpyxl, unlike CI. The test explicitly records this known difference;
whether CI otherwise bundles every optional document component remains
unverified and needs separate installed-app QA.

## Verification boundary

AST and source-command checks exercise source-reader discovery, actual
frontend and build-info root resolution, the two build command sources and
the inert PowerShell build harness. A green GitHub CI result validates this
contract, not the five missing shipped resources or installed upgrades.
No local real executable build, owner account access, GPU or Studio run is
claimed here.
