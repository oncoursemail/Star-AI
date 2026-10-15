# Wine and Proton — reverse-engineering case study (researched 2026-10-13)

Wine reimplements the Win32 API on Unix through clean-room black-box testing, with no disassembly, no Microsoft source and (since recently) no LLM code. Its conformance suite runs against real Windows to define "correct". Proton is Valve's gaming distribution of Wine, bundled with the DXVK and vkd3d-proton translation layers that turn Direct3D into Vulkan, and it powers the Steam Deck.

## 1. What it is and its 2026 state
- Wine was started in 1993. Alexandre Julliard has led it since 1994, and CodeWeavers (CrossOver) is its main sponsor. It is LGPL-2.1+, having moved from MIT in 2002 so proprietary forks would have to share changes (Wikipedia).
- Wikipedia lists stable 11.0 (13 Jan 2026) and development 11.19, as of 2026-10-13. A single build can run 32- and 64-bit apps (WoW64).
- Proton (announced 21 Aug 2018) bundles a Valve Wine fork with DXVK, vkd3d-proton, DXVK-NVAPI, FFmpeg/GStreamer, FEX (for Arm), and Steam/OpenVR/OpenXR bridges. The current branch is `proton_11.0`, and `PROTON_NO_ESYNC` is obsolete as of 11.0, which points to ntsync (README).
- DXVK (Zlib) implements D3D8-11 over Vulkan. vkd3d-proton (LGPL-2.1) is a performance-focused fork of WineHQ's vkd3d for D3D12, which needs Vulkan 1.3 and explicitly does not aim at standalone vkd3d API compatibility.

## 2. How the original was reversed
- The Developer FAQ admits Microsoft documentation is "often bad, nonexistent, and even misleading". Wine therefore uses black-box testing, and its developers have sometimes sent corrections back to Microsoft's docs.
- The method is to write a test program that calls the API on real Windows, record what happens, add it to the suite, then make Wine match. The test becomes both the specification and the regression check.

## 3. Workflow: matching, non-matching or clean-room
The strictest clean-room policy among the projects studied (Clean-Room-Guidelines wiki).
- **Allowed:** write test programs, read MSDN "with a grain of salt", and prefer a test to any Microsoft docs or headers. Ask on wine-devel when unsure.
- **Forbidden:**
  - disassembling Microsoft code
  - viewing any Microsoft source, even "public" source; MIT/LGPL-compatible code is the exception
  - test programs that dump internal tables
  - tracing native DLLs with `+relay`
  - Microsoft debug symbols
  - ReactOS code, even its headers
  - LLM-generated code, because training data may break the guidelines and the licence status is unclear
- Anyone who has seen Windows source (leaked, under NDA or disassembled) cannot contribute. People who have seen ATL/MFC/msvcrt source may contribute everywhere except those components (Developer FAQ). Henri Verbeet's quoted rule is "simply avoid unnecessary risk".

## 4. Testing and verification
- The conformance tests exist to "document the behavior of the Windows API", check Wine conforms, and prevent regressions. Tests use `ok()`, `todo_wine`, `skip()` and `broken()`. `broken()` accepts odd behaviour from old Windows versions, and `todo_wine` marks known gaps without failing the run (Conformance-Tests wiki).
- **Two gates:** Julliard will not commit a patch that causes test failures on his own machine. Every MR that changes a test runs on Windows VMs in the TestBot, and tests that fail on real Windows are rejected. This verifies the tests themselves against the reference implementation.
- **WineTest:** a single Windows executable built daily. Volunteers run it and upload results. `wt-daily` automates this on Unix, and submissions with ≥50 failures are refused.
- **Dashboard:** test.winehq.org/data shows per-commit error counts by Windows version (Win8 to Win11) and Linux. As of 2026-10-13 the latest commit showed a 4.0% failure rate (284 errors in 7,096 unit runs, 452 todos), with a roughly 3.9-5.2% band since August.
- **Social signal:** the FAQ's tongue-in-cheek "Julliard Rank" rewards contributors who send conformance tests first and small, clean patches.

## 5. Structuring a large legacy codebase
- Wine is one DLL per directory (`dlls/<name>/` with `tests/`), written in C89-ish C. C++ is banned, and the code must compile with MSVC (FAQ).
- It only reimplements DLLs that ship with Windows, and APIs nobody uses are low priority.
- Apps should not detect Wine. The policy is to detect features, not the platform, and to file a bug with a minimal test.
- Proton holds what upstream won't take: Valve's Wine fork carries patches "that upstream Wine doesn't accept" (Wikipedia). Per-game behaviour lives in data, through Steam-provided `STEAM_COMPAT_CONFIG`, `PROTON_*` environment flags and `user_settings.py`. vkd3d-proton keeps app workarounds behind `VKD3D_CONFIG`, including a `skip_application_workarounds` switch for debugging.

## 6. Engine architecture insights
- Wine runs PE binaries natively on the host CPU (FEX handles Arm in Proton) and implements the APIs. It is a compatibility layer, not an emulator.
- Graphics are translated at the API level: D3D calls become Vulkan, and DXBC/DXIL shaders become SPIR-V, cached on disk. DXVK exposes `DXVK_SHADER_CACHE`, `DXVK_HUD=compiler` and `dxvk.conf`.
- Sync primitives moved from esync/fsync to kernel ntsync by Proton 11.0, with `PROTON_NO_NTSYNC` as a fallback.

## 7. Legal history and lessons
*Not legal advice; historical summary only.*
- Wine has run for 30+ years without a Microsoft lawsuit. In January 2020 Microsoft cited Wine favourably as API reimplementation in its *Google v. Oracle* amicus brief, and in August 2024 it donated Mono to the Wine project (Wikipedia).
- Why it survived (inference from the sources): a strict, written clean-room provenance policy; no Microsoft binaries, keys or circumvention shipped; reimplementation of interfaces rather than code; and corporate stewardship (CodeWeavers, then Valve).
- Contrast with the emulators: Wine never needed a decryption key, so DMCA §1201 never applied. *Sony v. Connectix* covered intermediate copying for interoperability, yet Wine forbids even that, choosing a margin of safety beyond what the case law requires.

## 8. Transferable lessons for STAR
1. **Write the test before the fix, and validate the test against the reference.** For Roblox, run a behaviour spec in real Studio or a throwaway place first, which is STAR's "Windows". Only then implement against it, and reject specs that fail on the reference.
2. **Make "known gap" a first-class result.** Add `todo`/`broken` states to STAR's Luau test runner (TestEZ `itSKIP`-style with a reason) so the dashboard counts todos separately from failures, like Wine's 452 todos next to 284 errors.
3. **Keep a published per-commit dashboard.** Track failure percentage by environment (Studio version, server versus client) over time. A steady 4% band with no spikes is the goal, not a one-time 0%.
4. **Write down provenance rules.** Adopt a short clean-room list for STAR: no decompiled Roblox client internals, no leaked engine source, no exploit-community code, and record where AI was used. Wine's "avoid unnecessary risk" is the default.
5. **Detect features, not platforms.** In Luau, check for an API before using it (`pcall` around a new service method) instead of branching on a version string.
6. **Keep hacks in config.** Like `PROTON_*` and `VKD3D_CONFIG`, put per-place quirks in a config ModuleScript with a global "disable all workarounds" flag for debugging.
7. **Write small patches with tests first.** That is what earns trust under Julliard Rank, and STAR's PRs should follow it.

## Sources
- [Wine wiki — Developer FAQ (via GitLab wiki API)](https://gitlab.winehq.org/api/v4/projects/wine%2Fwine/wikis/Developer-FAQ)
- [Wine wiki — Clean Room Guidelines (via GitLab wiki API)](https://gitlab.winehq.org/api/v4/projects/wine%2Fwine/wikis/Clean-Room-Guidelines)
- [Wine wiki — Conformance Tests (via GitLab wiki API)](https://gitlab.winehq.org/api/v4/projects/wine%2Fwine/wikis/Conformance-Tests)
- [WineTest results dashboard](https://test.winehq.org/data/)
- [Wine (software) — Wikipedia](https://en.wikipedia.org/wiki/Wine_(software))
- [ValveSoftware/Proton README](https://github.com/ValveSoftware/Proton)
- [DXVK README](https://github.com/doitsujin/dxvk)
- [vkd3d-proton README](https://github.com/HansKristian-Work/vkd3d-proton)
- [Sony v. Connectix — Wikipedia](https://en.wikipedia.org/wiki/Sony_Computer_Entertainment,_Inc._v._Connectix_Corp.)
