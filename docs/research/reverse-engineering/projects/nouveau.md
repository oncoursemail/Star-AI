# Nouveau (open NVIDIA driver stack) — reverse-engineering case study (researched 2026-10-13)

Nouveau is the community open-source driver for NVIDIA GPUs. It was built for nearly two decades by clean-room tracing of the proprietary driver, using register databases and trace tools from envytools. Since 2023 the stack has moved toward NVIDIA's GSP firmware. That brought the conformant NVK Vulkan driver and the Rust "Nova" successor, which is partly NVIDIA-staffed. The story shows how a signed-firmware wall can block reverse engineering, and how a vendor-supplied firmware interface reopened the path.

## 1. What it is and its 2026 state

- Nouveau is an MIT-licensed driver: kernel DRM/KMS plus Mesa userspace. Stéphane Marchesin started it in 2005, it entered Linux 2.6.33 (2010) and was marked stable in 2012 (Wikipedia).
- GSP support was merged in Linux 6.7 (November 2023). Automatic reclocking on Turing and newer comes through GSP firmware (nouveau.freedesktop.org).
- NVK, the Mesa Vulkan driver (all dates from nouveau.freedesktop.org):
  - Became the default in Mesa in February 2024.
  - Became a conformant Vulkan 1.4 implementation in December 2024.
  - Extended to Maxwell, Pascal and Volta in April 2025, and to Blackwell and Kepler in Mesa 25.2 (August 2025).
- Collabora's February 2024 post reported conformant Vulkan 1.3 on Turing, Ampere and Ada, run "with the GSP firmware enabled." OpenGL is planned as Zink on top of NVK.
- Nova is a Rust driver pair, nova-core plus nova-drm, meant to "supersede" nouveau on GSP-based GPUs (kernel docs).
  - Danilo Krummrich posted the nova-core stub series in early 2025 (v5 and v6 in March 2025).
  - Search snippets claim NVIDIA engineers presented a 2026 roadmap at LPC to make Nova the replacement on Turing and newer. I could not fetch that report, so it is unverified.

## 2. How the original was reversed

- Register tracing (the classic method):
  - Run the proprietary driver and log every memory-mapped register access.
  - mmiotrace, built into the Linux kernel, records timestamped MMIO reads and writes and lets you insert markers.
  - The documented procedure: start the trace, load the blob, run a 3D workload, stop, and submit the log with driver and hardware details (MmioTrace page).
- REnouveau, the older tool, ran small OpenGL tests on the blob and diffed register dumps. It described itself as clean-room ("did not disassemble driver binaries") and was superseded by Valgrind-mmt.
- envytools ("Tools for people envious of nvidia's blob driver") supplies:
  - envydis/envyas, a disassembler and assembler for NVIDIA ISAs.
  - nvbios, which decodes VBIOS tables.
  - nva, for direct register poking.
  - hwtest, for checking hypotheses on real silicon.
  - demmio, which annotates mmiotrace logs against the register database (MmioTrace page).

## 3. Workflow: matching, non-matching or clean-room

- The method is clean-room behavioural reimplementation. Observe the blob's hardware interactions, write the knowledge into a neutral database or documentation, and then write independent driver code from that.
- There is no byte matching. The goal is behaviour, measured against specs and tests.
- The GSP era changed the model:
  - Newer GPUs run NVIDIA's own resource manager on a GPU System Processor, and the open driver talks to it through a firmware RPC interface.
  - NVIDIA's open-gpu-kernel-modules (Turing+) "must be used with GSP firmware," so the firmware/driver ABI is effectively vendor-defined (GitHub README).

## 4. Testing and verification

- The Khronos CTS is the conformance oracle for NVK. Collabora stresses that every test passed in the submitted runs "also passes on upstream Mesa," and that "there are no hacks this time" compared with the earlier 1.0 submission.
- envytools' hwtest checks reverse-engineered register semantics against real hardware, so the database is tested rather than assumed.
- Trace diffing is the regression tool: an annotated mmiotrace of a known-good blob run shows what the open driver failed to do.

## 5. Structuring a large legacy codebase

- rnndb is the key idea. It is a machine-readable XML ("rules-ng-ng") database of MMIO registers, FIFO methods and memory structures. Tools, header generators and trace annotators all read the same source of truth (envytools README).
- Hardware knowledge is kept apart from driver code. envytools' docs cover chips, PFIFO command submission, PGRAPH, falcon microcontrollers and power (envytools readthedocs).
- Nova starts as a small stub that grows upstream, so the Rust abstractions and the driver co-evolve. This avoids a huge out-of-tree fork (nova-core cover letter).

## 6. Engine architecture insights

- Commands reach the GPU through FIFO channels (PFIFO) into engines such as PGRAPH. Many side engines run on falcon microcontrollers.
- Signed firmware broke the old model. On GM20x, GP10x and GV100, "firmware now needs to be signed by NVIDIA" for the access needed to reclock, so manual reclocking there is "unlikely" (nouveau site). Performance stayed capped for years. Re-clocking arrived only in 2014, and only on older chips (Wikipedia).
- GSP moves power management and much hardware setup into firmware. Nova's docs reflect this: VBIOS, devinit, FSP/Secure Boot, FWSEC, Falcon and TLV firmware images are first-class topics (kernel docs).

## 7. Legal history and lessons

- Clean-room tracing kept the project defensible. REnouveau explicitly avoided disassembling the blob. Knowledge flowed through traces and documentation, not copied code.
- Firmware redistribution:
  - Open drivers need vendor firmware that only the vendor can sign. That makes redistribution licences the bottleneck, not code.
  - Search results attribute to Phoronix that NVIDIA relaxed its licence (R535) so GSP binaries could ship in linux-firmware, with about 62 MB added in November 2023. I could not fetch that page, so this is unverified.
- 17 U.S.C. §1201(f) permits analysis for interoperability under conditions (Cornell LII). That is relevant to trace-based work, though signed firmware is a technical barrier, not just a legal one.
- Vendor cooperation changes everything. NVIDIA released some documentation in 2019, and former lead Ben Skeggs rejoined NVIDIA in 2024 (Wikipedia). Nova is co-developed with NVIDIA engineers.

## 8. Transferable lessons for STAR

1. Keep a register-database-style knowledge file. One machine-readable source of facts (like rnndb) should feed code generation, docs and log annotation. For Roblox, keep a single typed table of RemoteEvent names and payload schemas that both server validation and client callers import.
2. Annotate raw evidence before reasoning. demmio turns raw traces into named events. STAR should first map raw logs or stack traces to known symbols, then reason, and say which items it could not map.
3. Test the hypothesis on the real system (hwtest). When STAR infers undocumented engine behaviour, it should propose a minimal on-device check before building on it.
4. Separate observation from implementation (clean room). STAR should summarise behaviour and interfaces in its own words and never paste proprietary or decompiled code into the user's project.
5. Respect hard walls. Where a vendor signature or a licence blocks access, STAR should say so and suggest supported routes. In Roblox, use official Open Cloud APIs and server-authoritative logic, never client-side tampering.
6. Grow from a stub upstream. Like nova-core, STAR should land a small, reviewed skeleton that builds, then add features behind tests, instead of one large unreviewable patch.

## Sources

- [nouveau.freedesktop.org — project home](https://nouveau.freedesktop.org/)
- [nouveau — MmioTrace](https://nouveau.freedesktop.org/MmioTrace.html)
- [nouveau — REnouveau (historical)](https://nouveau.freedesktop.org/REnouveau.html)
- [envytools GitHub README](https://github.com/envytools/envytools)
- [envytools documentation](https://envytools.readthedocs.io/en/latest/)
- [Collabora — NVK is now ready for prime time](https://www.collabora.com/news-and-blog/news-and-events/nvk-is-now-ready-for-prime-time.html)
- [Linux kernel docs — Nova](https://docs.kernel.org/gpu/nova/index.html)
- [LKML — Initial Nova Core series v5](https://lkml.iu.edu/hypermail/linux/kernel/2503.0/05057.html)
- [LWN — nova-core v6 series](https://lwn.net/Articles/1013279/)
- [NVIDIA open-gpu-kernel-modules README](https://github.com/NVIDIA/open-gpu-kernel-modules)
- [Wikipedia — Nouveau (software)](https://en.wikipedia.org/wiki/Nouveau_(software))
- [Cornell LII — 17 U.S.C. §1201](https://www.law.cornell.edu/uscode/text/17/1201)
