# Ryujinx and yuzu — reverse-engineering case study (researched 2026-10-13)

yuzu (C++, from the Citra team) and Ryujinx (C#, by gdkchan) were the two leading Nintendo Switch emulators. Both were ended by Nintendo in 2024: yuzu and Citra through the $2.4M Tropic Haze settlement in March, and Ryujinx through an out-of-court agreement in October. This file covers history and legal outcomes only. It contains no key, firmware or circumvention details.

## 1. What it is and its 2026 state
- **yuzu:** announced 14 Jan 2018 by the Citra developers, sharing much code with Citra. It added a Vulkan renderer (2019), multicore CPU emulation (2020), fastmem (2021), the "Project Hades" shader recompiler rewrite (2021) and Android (May 2023). Development and distribution stopped on 4 Mar 2024 (Wikipedia).
- **Citra** (3DS, 2014-2024) was dropped in the same settlement. Its forks Lime3DS and another merged into **Azahar** in late 2024. Azahar dropped support for encrypted ROM files, and Wikipedia lists release 2126.0 dated 10 Aug 2026.
- **Ryujinx:** first released Feb 2018. It was described as the first Switch emulator to boot commercial games and as aiming at "correctness" rather than "game-specific hacks". It moved to Avalonia UI in March 2024 and was removed from GitHub on 1 Oct 2024 (Wikipedia, VGC).
- **Forks:** Suyu (yuzu fork) was DMCA'd off GitLab in March 2024 and stopped in Feb 2025. Sudachi, Torzu, Eden, Citron and Ryubing (Ryujinx continuation) followed. A GitHub DMCA notice dated 12 Feb 2026 targeted Citron, Eden, Kenji-NX, MeloNX, Pine, Pomelo, Ryubing, Ryujinx, Skyline, Sudachi, Sumi, Suyu and yuzu repos. As of 2026-10-13 the forks continue mostly off-GitHub, but their current state is unverified.

## 2. How the original was reversed
- Both emulated the Switch's Arm CPU, Maxwell-class GPU and Horizon OS services, starting with homebrew and test programs before commercial games (Wikipedia, yuzu).
- Ryujinx's design is CPU recompilation plus high-level reimplementation of OS services. Its specific JIT internals are unverified, because the project's own blog and docs are gone.
- This file deliberately leaves out how users obtained console keys and firmware.

## 3. Workflow: matching, non-matching or clean-room
- Both were behavioural reimplementations, not decompilations. The legal fight was not about copied Nintendo code. It was about how the emulator interacted with encrypted games.
- Ryujinx's no-per-game-hacks stance (Wikipedia) kept the core generic and spec-driven.

## 4. Testing and verification
- Testing was mostly community game compatibility lists. Nintendo's complaint used this against yuzu: per Mondaq's summary, it alleged the site "tested thousands of games for compatibility" alongside guides and links the complaint tied to piracy. A compatibility list that names specific commercial titles, especially unreleased ones, became evidence.
- I could not verify any automated hardware test suite for either project.

## 5. Structuring a large legacy codebase
- yuzu reused Citra's codebase (shared core, frontends, renderer plumbing). The rewrite of its shader pipeline as "Project Hades" shows a subsystem being replaced while the rest kept shipping.
- Ryujinx was written in C#/.NET, which is unusual for an emulator. It swapped its GTK UI for Avalonia without touching the core, so the frontend and core were cleanly separated.

## 6. Engine architecture insights
- Fastmem (host virtual-memory mapping of guest memory) and multicore CPU emulation were yuzu's major performance steps.
- Ryujinx used Apple-silicon hypervisor execution on macOS (Nov 2022) and a Vulkan backend (2022, up to 413% faster in some titles) (Wikipedia).

## 7. Legal history and lessons
*Not legal advice; historical summary at public-record level only.*
- **Complaint (26 Feb 2024, D. Rhode Island):** Nintendo of America sued Tropic Haze LLC under DMCA §1201 (anti-circumvention and trafficking) and for copyright infringement. It alleged that yuzu decrypted games using "an illegally obtained copy of cryptographic keys" and was "primarily designed" to circumvent Switch encryption. It also alleged the site linked to key-distribution sites and gave hacking instructions (Mondaq summary).
- **Tears of the Kingdom:** Nintendo said the game was playable on yuzu before launch and pirated over a million times. Press reports that the complaint also said Patreon subscriptions doubled during the leak, with paid tiers offering early-access builds. Aftermath reported Patreon income near $30,000/month, but I could not confirm this in the filing itself (unverified).
- **Settlement (4 Mar 2024):** Tropic Haze agreed to pay $2.4M, accepted a permanent injunction, surrendered the domain, and admitted yuzu was "primarily designed to circumvent". The injunction also reached other circumventing software, so Citra ended too. The team said it had "always been against piracy" but acknowledged leaks of pre-release content (Aftermath, Mondaq).
- **Fork takedown:** a 29 Apr 2024 GitHub notice under §1201(a) removed a network of 8,535 repositories. Nintendo had reviewed only a "representative number" of forks (GitHub DMCA repo).
- **Ryujinx (Oct 2024):** no lawsuit was filed. gdkchan was "offered an agreement to stop working on the project", and the org and assets were deleted. The terms are unknown (VGC, Gigazine).
- **What it did not decide:** because yuzu settled, no court ruled on whether emulators that need user-supplied keys are lawful (Mondaq). The *Connectix* fair-use precedent still covers clean reimplementation. §1201 trafficking claims are the risk vector, and *Connectix* did not address them.
- **Contrast:** Dolphin was criticised for embedding a key yet survived without litigation. yuzu shipped no keys but combined circumvention-focused distribution, money from early access, and a highly visible pre-release piracy event. On the public record, the combination of those factors made the difference, not the key alone.

## 8. Transferable lessons for STAR
1. **Monetisation shapes how intent is read.** Paywalled early-access builds were cited as profit from infringement. STAR features must never sell or gate access to exploit-adjacent capability, such as Roblox executors or tools that defeat anti-cheat. STAR should refuse such requests.
2. **Public artifacts are evidence.** Compatibility lists, guides and Discord channels were all used in the complaint. STAR's docs, examples and commit messages must stay free of piracy or exploit instructions, and leaked Roblox internals must never be cited.
3. **Ship no secrets and require no secrets.** For Roblox, never embed Open Cloud API keys or webhook tokens in Luau. Read them server-side, as STAR's own standing rules already require.
4. **Keep the core generic.** Ryujinx's "correctness over per-game hacks" maps to Luau: fix the shared module (for example a remote validator) instead of adding place-specific branches.
5. **Plan for continuity.** Forks survived on self-hosted git while GitHub networks were removed in bulk. Keep STAR's research and knowledge base reproducible from local sources, not dependent on one host.
6. **Separate frontend from core**, as with Ryujinx's GTK-to-Avalonia swap. In Roblox, keep UI controllers thin over pure state modules so UI rewrites don't touch game logic.

## Sources
- [yuzu (emulator) — Wikipedia](https://en.wikipedia.org/wiki/Yuzu_(emulator))
- [Ryujinx — Wikipedia](https://en.wikipedia.org/wiki/Ryujinx)
- [Citra (emulator) — Wikipedia](https://en.wikipedia.org/wiki/Citra_(emulator))
- [Mondaq — Nintendo vs yuzu settlement explained](https://webiis08.mondaq.com/unitedstates/copyright/1445382/nintendo-vs-yuzu-lawsuit-settlement-explained)
- [Aftermath — yuzu and Citra shut down (4 Mar 2024)](https://aftermath.site/nintendo-yuzu-emulator-citra.md)
- [GitHub DMCA notice 2024-04-29 (yuzu network)](https://github.com/github/dmca/blob/master/2024/04/2024-04-29-nintendo.md)
- [GitHub DMCA notice 2026-02-12 (Switch emulator forks)](https://github.com/github/dmca/blob/master/2026/02/2026-02-12-nintendo.md)
- [VGC — Ryujinx taken down after Nintendo contact](https://videogameschronicle.com/news/switch-emulator-ryujinx-has-been-taken-down-after-nintendo-contacted-its-lead-developer)
- [Gigazine — Ryujinx suspended (Oct 2024)](https://gigazine.net/gsc_news/en/20241002-switch-emulator-ryujinx-shuts-down-nintendo)
- [Sony v. Connectix — Wikipedia](https://en.wikipedia.org/wiki/Sony_Computer_Entertainment,_Inc._v._Connectix_Corp.)
