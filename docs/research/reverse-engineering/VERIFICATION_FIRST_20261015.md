# STAR REA research: verification-first reverse engineering and native ports

**Research date:** 2026-10-15 (America/Chicago). **Status:** sourced engineering blueprint plus a bounded real STAR gateway addition. This document does **not** establish that a native Windows binary, Ghidra, REA, any game, or Roblox Studio was actually run or ported.

## Executive decision

STAR should adopt **independent verification** rather than collect unsupported claims or auto-install decompilers. Every AI-produced source fragment or inferred behavior is a hypothesis until a separate verifier proves a precisely stated property. Preserve FAIL, NOT_RUN and INCONCLUSIVE—not only PASS.

The provided [awesome-rea](https://github.com/yibie/awesome-rea) is a **curated reading list**, not a decompiler, an installed MCP provider, a ROM archive, or a guarantee of legality. At this research snapshot it contains **26 items**: 3 game matching-decompilation projects, 5 static-recompilation/native ports, 3 tools and MCP projects, and 15 practices/discussions. Projects are listed with stated acceptance gates; discussions convey lessons without reproducible tests. Inclusion is **not** an independent audit or endorsement.

The separate [REA: Reverse Engineer Anything](https://github.com/morluto/rea) project offers local agent CLI/MCP workflows over several analysis engines and application formats. It reports evidence and limitations; it does not automatically recover exact original source or prove a reconstructed game works. Treat mirrors, package labels, supported hosts and external tool versions as independent supply-chain questions.

## Existing STAR capability (checked before this change)

- STAR already has an **opt-in, workspace-confined** Python reverse-engineering gateway at [star/reverse_engineering.py](../../../star/reverse_engineering.py): magic/header identification, strings, PE imports, optional capstone disassembly, local radare2/rizin, Ghidra headless, ILSpy and crash dump triage. External tools are conditional, bounded and not bundled.
- [star/binary_evidence.py](../../../star/binary_evidence.py) provides read-only single-file identification and SHA-256. [LOCAL_RE_TOOLS.md](LOCAL_RE_TOOLS.md) and [INDEX.md](INDEX.md) already document the toolchain and twenty-one earlier case studies. There are bundled opt-in skills, including re-methodology and re-decomp-lessons.
- **Added by this PR:** re_compare_artifacts in STAR's **existing guarded RE gateway**, using [star/re_artifact_verifier.py](../../../star/re_artifact_verifier.py). It compares whole files (maximum 128 MiB each) or selected regions of at most 1 MiB at different file offsets, calculates both SHA-256 values and reports the first differing offset. It optionally checks a caller-provided reference digest. It neither executes nor changes targets. Existing workspace restrictions and forbidden-intent gating remain.
- **Not added:** automatic REA installation, arbitrary shell tools, new trusted MCP transports, process injection, anti-cheat workarounds, original asset extraction, ROM acquisition, or unsupported native-port claims.

### Exactly what the new verifier proves

The result PASS means **only that the selected bytes were equal**. When a reference digest is supplied, it means that *caller-supplied* digest also matched. STAR cannot authenticate its source. Every record says reference_provenance = not_authenticated and runtime_verified = false. Exact bytes do not demonstrate a whole game boots, gameplay works, audio and graphics match, code is safe, or the input is legal to redistribute. File offsets are not virtual addresses or relocation-aware code matches.

The tool refuses identical source/target file handles, empty files, invalid ranges, unsupported arguments and paths escaping the owner's selected workspace. Hashes are streamed, with ordinary file-modification detection. Trusted original-file digests and oracle fixtures must ultimately be anchored outside all agent-writable locations.

## The 26 awesome-rea entries: what to transfer

### A. Matching game decompilation (3 entries)

1. [500+ Billion Tokens Later](https://momo5502.com/posts/2026-10-09-game-decompilation/) reports high recovered-function coverage, a smaller independently byte-matched share, and lessons about compaction and task parallelism. **Lesson:** always report candidates, builds and verified matches separately. Any token-use and speedup figures are author-reported, not reproduced by STAR.
2. [sm64ds-decomp](https://github.com/tangosdev/sm64ds-decomp) describes per-function byte comparisons, relocation audits, source review and independent PC-port smoke builds. **Lesson:** a decomp match, a successful build and a running port are *three* different gates.
3. [Xenosaga Episode I decomp](https://scientia.godsibb.net/t/xenosaga-ep-i-decompilation-project/1496) describes independent byte checks over partial progress. **Lesson:** publish a truthful unmatched remainder; do not turn an incomplete coverage ratio into "finished".

### B. Static recompilation and native ports (5 entries)

1. [goldeneye-pc-port](https://github.com/jkdansereau/goldeneye-pc-port): make repeatable bug classes and porting notes part of the acceptance process. Multi-agent output must feed shared regression cases, not repetitive guesses.
2. [BattleShip](https://github.com/vinvirile/BattleShip): pin the user's authorized reference to a known digest/version; an input digest is not a guarantee of behavioral accuracy or a license to distribute copyrighted assets.
3. [ssbu-recomp](https://github.com/Denkishi/ssbu-recomp): track compatibility **by game mode and revision**, labeling scripted-only and untested conditions, and measure frame times on declared hardware. Treat performance claims as upstream reports.
4. [VandalHearts-decomp](https://github.com/HalmyLyseas/VandalHearts-decomp-SLPM-86007): reuse the matching-decomp oracle, but add a distinct native-port acceptance gate.
5. [KartPad](https://github.com/chrissotraidis/kartpad): original-input provenance, exact game revision, device-specific builds/tests, and a list of still-unsupported targets matter more than promotional screenshots.

### C. Tooling and MCP (3 entries)

- [Hex-Rays official IDA MCP](https://github.com/HexRaysSA/ida-mcp): official structured analysis interface. Current README specifies IDA 9.4+, idalib and Python 3.11+; **not** a free IDA Pro license.
- [mrexodia/ida-pro-mcp](https://github.com/mrexodia/ida-pro-mcp): alternative bridge to IDA. Avoid registering multiple redundant tool servers by default; review any tool that writes to an analysis database.
- [decomp-compat-kit](https://github.com/LinuxJessi/decomp-compat-kit): independently compare reconstructed machine code rather than trusting the agent's claim. This is project-specific tooling, not code copied into STAR.

### D. Fifteen discussion/practice signals

The curation includes: machine-readable PASS/FAIL as the target; skepticism about "software is solved"; legal concerns about live commercial games; careful accounting for human expertise in accelerated decompilation; the hard long tail after easy functions match; early agent-workflow lessons; game-preservation arguments; a conference decomp agent case study; dissent about inflated port speedups; criticism of low-quality generated C; the still-unsolved general decompiler question; community recompilation technique exchange; criticism of unverified "slopcomps"; what a completed byte-matching decomp actually means; and symbol-free debugging after reconstruction.

These entries are **arguments and practices, not standalone validated projects**. Read original links in [related practices](https://github.com/yibie/awesome-rea/blob/main/categories/related-practices-discussions.md) before treating a claim as fact.

## Further research: tools beyond the list

| Source | What it really offers | STAR decision |
|---|---|---|
| [REA](https://github.com/morluto/rea) | CLI and MCP evidence-oriented native/JS/Electron/.NET/app investigation; provider support varies by platform and release | Future reviewed, operator-installed adapter only; no automatic npx or model-controlled setup |
| [Ghidra](https://github.com/NationalSecurityAgency/ghidra) | Free native decompiler, headless scripting | STAR's existing narrow Windows gateway is the near-term choice; check exact Ghidra/JDK compatibility |
| [objdiff](https://github.com/encounter/objdiff) | Per-object and function difference exploration | Human/CI debugging aid; non-identical byte output is not "matched" |
| [decomp-permuter](https://github.com/simonlindholm/decomp-permuter) | Candidate C variations for improving compiler matches | Proposal engine; the independent comparator judges |
| [splat](https://github.com/ethteck/splat) | Binary-section splitting, decomp project preparation | Only authorized files, no extraction or redistributing copyrighted game assets |
| [N64Recomp](https://github.com/N64Recomp/N64Recomp) | N64 binary instruction translation into compilable C | Study compiler/runtime separation; not an arbitrary-console one-click port |
| [Zelda64Recomp](https://github.com/Zelda64Recomp/Zelda64Recomp) | Example of native static recompilation plus graphics/runtime integration | Its project policy **forbids generative-AI contributions**; do not open STAR-generated PRs there |
| [ps3recomp](https://github.com/sp00nznet/ps3recomp) | PS3-specific runtime and translation research; platform tests and limitations documented | Research only until proven on an authorized, pinned test program; no blanket "PS3 games supported" claim |
| [Dolphin hwtests](https://github.com/dolphin-emu/hwtests) / [FifoCI](https://github.com/dolphin-emu/fifoci) | Hardware and captured GPU-command regression oracles | Copy the engineering pattern for owner's original games, not their datasets |
| [Wine conformance](https://gitlab.winehq.org/wine/wine/-/wikis/Conformance-Tests) | API behavior tests run against real reference implementations | External-oracle approach; honor Wine's clean-room and no-LLM-source contribution rules |

### Windows and supply-chain caveats

REA's public instructions document supported Node.js major/minor lines and optional Ghidra, Hopper or IDA integrations. Native PE support on Windows is recent and limited/experimental in some provider paths; static Electron/managed work has different prerequisites. Do **not** mistake a README from a fork for the published npm package. The owner may have Node 24, but STAR must **probe the actual installed version, provider capabilities and permissions** before claiming a tool is ready.

STAR's generic MCP connector code and native Roblox Studio MCP are distinct permission boundaries; neither is permission for an AI model to spawn and configure arbitrary local stdio servers. Introducing REA later requires a reviewed dedicated broker with fixed executable identity, user approval, scoped file access, limits, cancellation semantics and allowlisted tool operations. Native REA runtime features may execute/interact with the selected app: keep them separately gated and **off by default**.

## STAR's evidence-first architecture

    Owner-authorized scope and input revision
      -> source/version/hash inventory
      -> bounded static analysis and hypothesis graph
      -> candidate reconstruction in disposable branch
      -> fixed independent build/diff/replay oracle
      -> external skeptical review and reproducible failure minimization
      -> PASS / FAIL / NOT_RUN / INCONCLUSIVE receipt
      -> owner review -> draft PR; never unreviewed publication

The future evidence record should contain: task and artifact identities; owner-approved baseline provenance and digest; candidate revision; target architecture and compiler flags/digest; provider version; exact code region/offset/relocations; harness authority and run ID; actual stdout/stderr or artifact reference; deterministic test inputs/seed; verdict per gate; unknowns and legal/contribution review. Keep test fixtures and verifier code outside agent-write access. Never turn missing logs into success.

Separately track: **candidate source coverage**, **compile success**, **byte-exact match**, **behavioral replay match**, **per-mode game compatibility**, **performance**, and **native user-testing status**. Illustrative figures (not measurements): 200/300 candidates written, 150 compiled, 112 byte matched, 8/20 gameplay scenarios passed, Windows smoke NOT_RUN.

### Five supervised agent roles

- *Investigator*: maps strings, imports, symbols, functions, and observations; uncertain names stay uncertain.
- *Mapper*: produces a structured dependency/call graph with file offsets and citations.
- *Reconstructor*: writes candidate original implementation to a disposable branch; cannot mutate reference fixtures or verdicts.
- *Independent oracle runner*: compiles/compares against protected originals and returns receipt/logs from a separate trust domain.
- *Skeptical reviewer*: tries counterexamples, checks claimed coverage, performance, licenses and provenance before the merge gate.

Parallelize only independent function/section work with file ownership, bounded memory/CPU, cancellation and deduplication. More model calls without trusted verification just increase confidently incorrect output.

## Verifier selection and acceptance matrix

| Task | Required oracle | Further acceptance |
|---|---|---|
| Matching decompilation | Exact reference revision/digest and per-function/object byte comparison by independent tool | Relocation audit and matched/unmatched report |
| Proprietary-format interoperability | Legal sample fixtures, round-trip identity and malformed-file rejection | Version migration and cross-version compatibility |
| Native recompilation | Compiles, boots, controls/audio/graphics per-mode replay matrix | Long-run stability, frame-time histograms with hardware metadata |
| Original game reconstruction | Deterministic gameplay reference behaviors where permitted | Original code/assets/IP boundaries and visual/playtest review |
| Roblox Luau project | STAR Luau analyzer, isolated sandbox and permitted Studio Lab assertions | Real native Studio execution, server security and playable UX |
| STAR desktop UI | Build/type/a11y tests, reference screenshots and human visual gates | Native Windows package, interaction and latency tests |

The new re_compare_artifacts implements **only** the byte comparison gate. It cannot perform relocation-aware object diff, original game execution, semantic equivalence, asset authorization, compatibility tests or a live REA integration.

## Reproducible offline regression cases

1. Different local files with equal nonempty bytes => PASS, hashes agree, runtime_verified is false.
2. Single-byte change and 64 KiB block-boundary change => FAIL with precise first difference.
3. Matching prefix but different file sizes => FAIL at first extra byte.
4. Same function bytes at different file offsets => bounded range PASS; do not equate file offsets with RVAs.
5. Caller-supplied wrong expected digest => FAIL even when files match.
6. Refuse identical file, unsupported paths, sensitive files, missing/out-of-bounds ranges, oversized files and unknown arguments.
7. Prove the verifier does not invoke subprocess or need external decompilers.
8. Separately enforce installed-host permission, allowed RE intent, workspace selection and tool-name policy.

Run the new offline tests with the existing RE gateway suite and full CI; **test presence is not a test pass**. Do not publish compatibility, speed or functional claims without executed external evidence.

## Phased roadmap, with status

**P0 — code submitted in this PR, pending checks:** bounded read-only whole-file/function-range comparator, fail-closed argument validation and sourced architecture notes. It does not install third-party apps.

**P1 — not implemented:** trusted owner-pinned reference manifest outside agent-controlled files, separate verifier service/permission boundary, versioned evidence schema, sealed run receipts, verified per-function progress ledger and a regression fixture zoo.

**P2 — not implemented:** reviewed optional local REA CLI/MCP transport adapter (exact binary, chosen provider, permissions, capability probes, no arbitrary shell), with Windows release/version smoke tests and hard resource ceilings.

**P3 — not implemented:** function-level objdiff integration, compiler/version pinning, deterministic behavioral replay, image/audio/graphics comparisons, per-mode compatibility matrix, profiler evidence, and symbol-free debugging triage.

**P4 — research only:** synthetic permitted practice binaries and open-source toy games to train/evaluate investigator → reconstructor → independent checker. Reward *verified correct outputs*, including true negative/failure detection, not tool-call volume.

## Legal/ethical boundaries and provenance

The curated list does not provide ROMs, game asset archives, proprietary sources, bypass methods or keys. Some listed projects have restrictive AI contribution policies. Interoperability and preservation may be legitimate objectives but do not automatically authorize copying protected code/assets, bypassing DRM or anti-cheat, or recreating a proprietary live service. Follow each target's license and terms, avoid leaked source, prefer your own binaries and unambiguously licensed toy programs, and get professional legal review for proposed distribution. STAR's existing RE intent denials remain unchanged.

**Directly read:** the awesome-rea README and category inventory, STAR's current reverse-engineering module, binary triage, knowledge index and skill packs, upstream Ghidra/IDA/REA/N64Recomp/ps3recomp/objdiff/splat READMEs.

**Not independently reproduced:** upstream percentages, claimed AI time savings, performance FPS, total function progress and claimed support for any commercial title.

**Not run:** REA installer, target binaries, Ghidra, an original console game, Windows native test build or Roblox Studio. GitHub CI (where available) is the separate source of truth for this change's automated regressions.

**Final criterion:** STAR should explain exactly what was measured and refuse to fill an evidence gap with a plausible-looking answer.
