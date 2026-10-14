# Ghidra, IDA and Binary Ninja plugin ecosystems — reverse-engineering case study (researched 2026-10-13)

Interactive disassemblers and decompilers are the workbench of game and legacy-code RE. Ghidra (NSA, Apache-2.0), IDA Pro with the Hex-Rays decompilers, and Binary Ninja each add scripting, similarity databases, collaboration and, by 2025-2026, Model Context Protocol (MCP) bridges that let LLM agents drive them. Decomp projects use these tools for exploration and annotation. The final authority stays with compilers and diff tools.

## 1. What it is and its 2026 state

- Ghidra:
  - An Apache-2.0 suite for disassembly, assembly, decompilation, graphing and scripting.
  - It runs interactively or in automated mode, and supports scripts and extensions in Java or Python (PyGhidra) (GitHub README).
  - As of 2026-10-13, GhidraMCP's README targets Ghidra 12.1.4.
- IDA Pro / Hex-Rays (product page):
  - Hex-Rays decompilers do type inference and structure recovery.
  - Automation comes from IDAPython and a C++ SDK, and idalib runs IDA headless.
  - Lumina shares function metadata by hash, with a self-hostable Private Lumina. A Teams add-on supports shared work.
  - "IDA MCP" lets you "Drive IDA from an AI assistant."
- Binary Ninja: decompiles to C or to its BNIL intermediate language, has C++/Python/Rust APIs, offers a "Sidekick" AI add-on, and supports Enterprise-server collaboration with synchronized commits (binary.ninja).
- LLM bridges:
  - LaurieWired's GhidraMCP (Apache-2.0) has two parts: a Ghidra plugin exposing an HTTP API, and a Python MCP server. It can decompile, rename functions and data, and list classes, imports and exports. It also has a headless PyGhidra mode.
  - mrexodia's ida-pro-mcp (MIT) exposes decompile, xrefs, rename, type, patch and search tools. Its README now recommends the official Hex-Rays MCP server.

## 2. How the original was reversed

- Loaders turn console images into analysable programs:
  - N64LoaderWV corrects ROM byte order, maps RAM/ROM/boot segments, and seeds names from signature or symbol files. It also accepts an RDRAM dump so overlay code loaded at runtime can be disassembled.
  - Ghidra-GameCube-Loader (Apache-2.0) loads DOL/REL files, apploaders and RAM dumps. It can import symbol maps, creates namespaces automatically and demangles names.
- Function identification:
  - BSim indexes functions by features from the decompiler's p-code data-flow graph, not raw instructions. That makes queries "tolerant of variations in the compilation of the function." Backends are H2, PostgreSQL or Elasticsearch (BSim overview).
  - IDA does the equivalent with FLIRT and Lumina.
- Porting knowledge across builds: Ghidra Version Tracking runs correlators between two binaries and scores the matches. Accepting a match ports markup (names, comments, data types, parameter names) and adds implied matches for callees (Version Tracking help).

## 3. Workflow: matching, non-matching or clean-room

- In matching-decomp projects, the tools serve to understand code, recover types and name things. The answer is decided by the original compiler plus objdiff/asm-differ, not by the decompiler's pseudocode.
- Ghidra can also cut a binary into pieces. The ghidra-delinker-extension (Apache-2.0) exports parts of a program as relocatable object files with symbols and relocations. That allows "Ship of Theseus"-style rewrites, where one object file at a time is replaced with source while the rest stays original.
- Non-matching or behavioural projects use decompiler output as a reading aid. They then write fresh code verified by behaviour tests.

## 4. Testing and verification

- Decompiler output is a hypothesis.
  - Version Tracking makes the user review conflicting associations, and only one-to-one matches can be accepted.
  - BSim returns similarity scores, not proofs.
- ida-pro-mcp's README warns that LLMs "are prone to hallucinations," especially integer/byte conversions, and offers a conversion tool instead of model arithmetic. It also says models do poorly on obfuscated code. Its suggested prompts ban brute forcing and require conclusions grounded in disassembly plus a written report.
- Headless modes (PyGhidra, idalib) make analyses scriptable and repeatable in CI rather than one-off clicks.

## 5. Structuring a large legacy codebase

- Typed data-type archives and structure definitions are the shared knowledge layer. Once a struct is defined, every decompiled function that uses it reads better.
- Shared projects:
  - Ghidra Server repositories (check-in/check-out) can feed BSim ingestion (BSim overview).
  - IDA Teams and Binary Ninja Enterprise give multi-user sync.
  - Lumina and BSim act as cross-project function-knowledge databases.
- Symbol maps imported by loaders, plus Version Tracking between regional or revision builds, let one annotated build seed all the others.

## 6. Engine architecture insights

- Ghidra's p-code IR is what makes BSim robust to instruction scheduling and register differences. Similarity is computed on data-flow, not bytes.
- Overlays and runtime-loaded code on consoles need RAM dumps or segment maps (N64LoaderWV). Static images alone can miss them.
- MCP bridges are thin RPC layers: plugin, then local HTTP, then the MCP server. They inherit the tool's full power. ida-pro-mcp flags its arbitrary-Python tool as sensitive and hides debugger tools by default.

## 7. Legal history and lessons

- Licences:
  - Ghidra, GhidraMCP, the GameCube loader and the delinker are Apache-2.0.
  - ida-pro-mcp is MIT.
  - IDA and Binary Ninja are commercial. Check their EULAs before automated or shared use (licence terms not reviewed here; unverified).
- US case law: Sega v. Accolade (9th Cir. 1992) held that disassembly to reach functional elements can be fair use, and Sony v. Connectix (2000) followed it. 17 U.S.C. §1201(f) adds a narrow interoperability exemption.
- Sharing annotations and symbol maps is a different act from sharing the original binary. Decomp communities share the former, not the latter.

## 8. Transferable lessons for STAR

1. Treat decompiler or LLM output as a claim and verify with an oracle. STAR should never present inferred types, names or values as fact without a compile, test or diff result attached.
2. Offload exact arithmetic to tools. As ida-pro-mcp advises, STAR should compute offsets, hex/decimal conversions and bit masks with code execution, not mental arithmetic.
3. Prefer type recovery first. Defining one struct improves every use site. In Luau, adding `export type` definitions and `--!strict` to a shared module removes whole classes of errors across scripts.
4. Port knowledge, don't redo it. Like Version Tracking, when a Roblox place or package is updated, STAR should diff the old and new module trees and carry over notes and renames instead of re-analysing from scratch.
5. Gate powerful tool calls. MCP bridges expose rename, patch and eval. STAR should keep write tools behind explicit confirmation and log every mutation, as ida-pro-mcp hides its debugger by default.
6. Demand a written trail. Require a findings report listing evidence (addresses, xrefs, test output) for every conclusion, so a human can audit the agent's work.

## Sources

- [Ghidra GitHub README](https://github.com/NationalSecurityAgency/ghidra)
- [Ghidra BSim overview (help source)](https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/Features/BSim/src/main/help/help/topics/BSim/BSimOverview.html)
- [Ghidra Version Tracking intro (help source)](https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/Features/VersionTracking/src/main/help/help/topics/VersionTrackingPlugin/Version_Tracking_Intro.html)
- [LaurieWired GhidraMCP](https://github.com/LaurieWired/GhidraMCP)
- [mrexodia ida-pro-mcp](https://github.com/mrexodia/ida-pro-mcp)
- [Hex-Rays IDA Pro product page](https://hex-rays.com/ida-pro)
- [Binary Ninja](https://binary.ninja/)
- [N64LoaderWV](https://github.com/zeroKilo/N64LoaderWV)
- [Ghidra-GameCube-Loader](https://github.com/Cuyler36/Ghidra-GameCube-Loader)
- [ghidra-delinker-extension](https://github.com/boricj/ghidra-delinker-extension)
- [Wikipedia — Sega v. Accolade](https://en.wikipedia.org/wiki/Sega_v._Accolade)
- [Cornell LII — 17 U.S.C. §1201](https://www.law.cornell.edu/uscode/text/17/1201)
