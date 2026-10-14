# Asahi Linux GPU (Apple AGX) — reverse-engineering case study (researched 2026-10-13)

Asahi Linux reverse-engineered Apple's undocumented M1/M2 "AGX" GPU. The work produced a Rust kernel driver and Mesa userspace drivers that Khronos certified as conformant for OpenGL, OpenGL ES, OpenCL and Vulkan. It is a model of black-box, trace-driven driver work checked against an external conformance oracle. The people who did it have since largely moved on.

## 1. What it is and its 2026 state

- An open graphics stack for Apple Silicon. It has a Rust DRM kernel driver (started by Asahi Lina) and Mesa drivers by Alyssa Rosenzweig and others: Gallium OpenGL and "Honeykrisp" Vulkan.
- Milestones:
  - Conformant OpenGL 4.6 / ES 3.2 announced 2024-02-14 (Rosenzweig blog).
  - Conformant Vulkan 1.3 announced 2024-06-05, after about a month of work (Rosenzweig blog).
  - Wikipedia says the August 2025 farewell post listed finished, upstreamed OpenGL 4.6, GLES 3.2, OpenCL 3.0 and Vulkan 1.4 implementations.
- People and leadership:
  - Project lead Hector Martin resigned in February 2025.
  - Asahi Lina paused GPU work indefinitely on 2025-03-18 (The Register).
  - Leadership passed to a group of seven contributors.
  - Rosenzweig stepped away in August 2025 (Wikipedia). Search snippets say she joined Intel; I did not fetch that report, so treat it as unverified.
- Upstream status as of February 2026 (LWN summary of the 6.19 progress report):
  - The GPU driver is about 21,000 lines, not counting the Rust abstractions the project still carries downstream.
  - "Upstreaming work has now begun."
  - In March 2025 only a UAPI header was proposed upstream.
- As of the 26 April 2026 (Linux 7.0) progress report:
  - M3 support is "roughly the same level as the first Asahi Linux alpha for M1."
  - The report says nothing about the GPU.
  - I found no fetched source showing M3 GPU acceleration working.

## 2. How the original was reversed

- Userspace first. Rosenzweig reverse-engineered the macOS userspace-to-kernel GPU interface well enough to submit her own command buffers. That let her write the Mesa driver before any Linux kernel driver existed. Dougall Johnson documented the shader ISA (Asahi blog, "Tales of the M1 GPU").
- Hypervisor tracing:
  - m1n1 is Asahi's "bootloader and experimentation playground."
  - Lina wrote a GPU tracer for m1n1's hypervisor and ran macOS on top of it, logging how Apple's kernel driver talked to the GPU.
  - It turned out the macOS driver never touches GPU hardware directly. It talks only through shared-memory structures to an RTKit firmware coprocessor, which handles scheduling, power and fault recovery.
- Python prototype:
  - Lina first wrote the driver in Python on m1n1's proxy, using its structure definitions and driving the Mac over USB.
  - The structures started out hard-coded and were generalised until a triangle rendered.
  - Python made the reboot-per-test loop cheap.
- Bridging to real apps: Lina embedded a Python interpreter in Mesa's drm-shim, which mocks the kernel interface. Real Mesa and real apps could then push work through the prototype to the hardware.

## 3. Workflow: matching, non-matching or clean-room

- This was black-box interface reverse engineering, not decompilation. The team observed inputs and outputs of the firmware and driver and reimplemented the behaviour. No Apple code was carried over.
- The output does not try to match anything. Success means behavioural equivalence on the specification, judged by the Khronos conformance suite.
- Code reuse within open source was heavy. Honeykrisp started as a fork of NVK (the open NVIDIA Vulkan driver): M1 code was added and NVIDIA code removed as work went on. It also shares kernel-interface and state-translation code with the AGX OpenGL driver.

## 4. Testing and verification

- The Khronos CTS is the oracle:
  - Vulkan conformance means passing roughly half a million tests, submitting the results, and a 30-day review.
  - Rosenzweig's log went from 149,770 passes / 7,741 fails / 2,396 crashes on 8 April 2024 to "Pass: 686930, Fail: 0" on 27 April.
- GL 4.6 / ES 3.2 conformance needs "over 100,000 tests."
- Robustness tests exposed undocumented hardware behaviour. Out-of-bounds mip levels returned nonzero values, so the team added a workaround that pushes the coordinate out of bounds to force zero. The fix itself relied on reverse engineering.
- Hardware gaps were emulated: geometry shaders, tessellation and transform feedback run as compute shaders, and clip control is a vertex-shader epilogue (GL 4.6 post).

## 5. Structuring a large legacy codebase

- The firmware ABI changes between firmware versions. Lina chose Rust partly because its macros could generate the many versioned structure layouts, and its ownership model could track GPU object lifetimes.
- Shared structure definitions live in m1n1's Python tooling. The same knowledge feeds the tracer, the prototype driver and the Rust port.
- The driver is layered: kernel UAPI, then shared Mesa "asahi" code, then the GL and Vulkan frontends.
- The project kept a downstream patch stack and measured shrinking it as a goal: 1,232 patches at 6.13.8 down to 858 at 6.18.8 (LWN).

## 6. Engine architecture insights

- The firmware does the real scheduling. Render commands are nested structures pointing to "microsequences" that the firmware interprets like a tiny VM.
- The firmware shares the GPU MMU page tables, so GPU memory is firmware memory. Userspace therefore cannot safely build these structures, and the kernel must validate everything (Tales of the M1 GPU).
- Gaming stack (Asahi blog, Oct 2024):
  - FEX for x86 emulation.
  - Wine, DXVK and vkd3d-proton on Vulkan.
  - muvm, a small VM that gives x86 games the 4K pages they expect on 16K-page hardware.

## 7. Legal history and lessons

- No vendor documentation was used. The knowledge came from observing a machine the developers owned, through a hypervisor, and was published as fresh open-source code.
- In the US, 17 U.S.C. §1201(f) allows analysis "for the sole purpose" of interoperability of an independently created program, under conditions (Cornell LII). Sega v. Accolade (9th Cir. 1992) held disassembly for access to functional elements to be fair use.
- Licensing: m1n1 was MIT up to v1.9.9 and is GPL-2.0-or-later from v2.0.0 (GitHub README). Licences on RE tools can change, so record which version you depend on.
- Human lesson: maintainer burnout and harassment, rather than legal threats, are what stalled the project in 2025 (The Register).

## 8. Transferable lessons for STAR

1. Treat an external test suite as the definition of done. STAR should report pass/fail counts from a real runner, never "should work." Rosenzweig's daily CTS tallies are the pattern.
2. Prototype in a fast language against the real system, then port. If the user is unsure about engine behaviour, STAR should suggest a small Luau probe script run in Studio to observe actual values before writing the production module.
3. Observe the interface, don't guess it. STAR should ask for logs, traces or printed values when behaviour is undocumented, and label inferred behaviour as unverified.
4. Keep one shared source of truth for structure layouts, as m1n1's definitions fed the tracer, the prototype and the driver. For Roblox, keep one typed `--!strict` shared types module used by both client and server remotes.
5. Reuse a working sibling and delete what doesn't apply, as Honeykrisp did by forking NVK. STAR should start from a proven module pattern rather than a blank file.
6. Roblox/Luau parallel: when engine behaviour is undocumented (replication timing, physics ownership), write a minimal repro place with assertions. That is a small, local conformance suite.

## Sources

- [Asahi Linux — Tales of the M1 GPU](https://asahilinux.org/2022/11/tales-of-the-m1-gpu/)
- [Rosenzweig — Vulkan 1.3 on the M1 in 1 month](https://alyssarosenzweig.ca/blog/vk13-on-the-m1-in-1-month.html)
- [Rosenzweig — Conformant OpenGL 4.6 on the M1](https://alyssarosenzweig.ca/blog/conformant-gl46-on-the-m1.html)
- [Asahi Linux — AAA gaming on Asahi Linux](https://asahilinux.org/2024/10/aaa-gaming-on-asahi-linux/)
- [The Register — Asahi Lina pauses GPU work (2025-03-20)](https://www.theregister.com/2025/03/20/asahi_linux_asahi_lina/)
- [Wikipedia — Alyssa Rosenzweig](https://en.wikipedia.org/wiki/Alyssa_Rosenzweig)
- [LWN — Asahi 6.19 progress report summary](https://lwn.net/Articles/1059339/)
- [Asahi Linux — Progress report Linux 7.0 (April 2026)](https://asahilinux.org/2026/04/progress-report-7-0/)
- [m1n1 GitHub README](https://github.com/AsahiLinux/m1n1)
- [Cornell LII — 17 U.S.C. §1201](https://www.law.cornell.edu/uscode/text/17/1201)
- [Wikipedia — Sega v. Accolade](https://en.wikipedia.org/wiki/Sega_v._Accolade)
