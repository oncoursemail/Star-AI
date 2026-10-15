# local-re-tools: local reverse-engineering capability

Branch `feature/local-re-tools` off `origin/star/next`. Draft PR to `star/next`.
Owner: claude. Board item #114.

## Goal
Let STAR use free/open reverse-engineering tools LOCALLY on the owner's Windows
PC for defensive, owner-permitted uses only (own builds, crash dumps, file
formats, interoperability, CTFs, malware-analysis learning, open-source
decompilation). Hard guardrails: no Roblox client/anti-cheat bypass, no game
cheats/exploits, no DRM/licence cracking, no malware creation.

## What was added (RE-only files + minimal registration hooks)
- `star/reverse_engineering.py` — the capability. A `ReverseEngineering`
  gateway (same shape as `LocalIntelligence`: `owns` / `definitions(prompt)` /
  `call`), plus pure-Python analysers (identify, strings, minimal PE reader),
  capstone disassembly, and guarded `shell=False` wrappers for radare2/rizin,
  ilspycmd, Detect-It-Easy, Ghidra headless and cdb. Guardrails: `check_intent`
  + prompt-gated `definitions` (forbidden intents get no tools); workspace path
  confinement; proxies stripped; timeouts; size/output caps.
- `star/re_scripts/DecompileOne.py` — Ghidra headless post-script (one function).
- `star/skill_packs/re-methodology/` — bundled Agent Skill teaching the method
  and ethics (discoverable via `star_skill_*`; NOT added to the Roblox
  `TRIGGERS`, so Roblox pack selection/tests are unchanged).
- `docs/research/reverse-engineering/LOCAL_RE_TOOLS.md` — researched tool matrix.
- `tests/test_reverse_engineering.py` — guardrails, path confinement, PE parsing
  (built-in minimal PE fixture), strings, status, gateway plumbing, and honest
  "not installed" behaviour.

Registration hooks (minimal):
- `star/agent.py`: new `reverse_engineering=None` param; definitions, permission
  branch and dispatch mirroring `document_tools`.
- `star/desktop_core.py`: `reverse_engineering_enabled` setting (default False,
  opt-in) + validation + construction in `run_task` + pass-through to `execute`.

## Status
Tests + compile run locally (see PR). `react_shell.py` path intentionally not
wired (keeps surface minimal; desktop_core is the main run path).

## Must install manually (optional; tools degrade gracefully)
JDK 21 + Ghidra (`GHIDRA_INSTALL_DIR`), radare2/rizin, .NET 10 + ilspycmd,
Detect-It-Easy, Debugging Tools for Windows (cdb), `pip install capstone`.
`re_tool_status` reports what is present.
