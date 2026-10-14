# ReactOS — reverse-engineering case study (researched 2026-10-13)

ReactOS is a GPL operating system that aims to run Windows NT-family applications and drivers. Its kernel and drivers are written independently, and most of its user-mode DLLs come from Wine. Its 2006 self-imposed halt and code audit, triggered by an allegation of disassembly-derived code, is the canonical example of a reimplementation project formalising a clean-room policy under pressure.

## 1. What it is and its 2026 state

- **Latest release: 0.4.16, 2026-08-29.** It was forked from master on 2026-04-28 and comprises 2,808 commits and 381 resolved Jira issues. Highlights:
  - a new graphical installer and a unified boot/live CD;
  - a new HD-audio bus driver with KMDF support;
  - a new ATA driver replacing UniATA, aimed at the 0x7B boot failure;
  - a new network adapter driver and asynchronous connection APIs;
  - a "Server Core" install type;
  - the Wine fork moved toward Wine 10.0, and WineVDM included for 16-bit apps.
- The previous release was 0.4.15 (2025-03-21). Per Wikipedia (as of 2026-10-13), 0.4.17 is in development and 0.5.0 is planned with NTFS read/write and WDM support.
- Still "Alpha quality" (README). It targets Windows Server 2003 compatibility, and release images export the 2003 API set by default. Vista+ exports are opt-in through a build flag.
- **Licence:** GPL-2.0 (some parts LGPL/BSD). Since 2023 the German association has employed a developer full time (Hermès Bélusca-Maïto) on setup and GUI work.

## 2. How the original was reversed

- The method is **interface-level reimplementation from public documentation, observed behaviour, and conformance tests** run against real Windows. CONTRIBUTING says tests check that ReactOS APIs "behave correctly" compared with Windows.
- Contributors must affirm that they have never seen Windows source code under an incompatible licence. The affirmation names the leaked NT 3.5/NT 4/2000 sources and the Windows Research Kernel. Documentation contributions must "respect clean room reverse engineering".
- User-mode coverage is largely inherited from Wine, which had already reverse-engineered Win32 behaviour through test-driven black-box methods.

## 3. Workflow: matching, non-matching or clean-room

- **Clean-room, non-matching.** There is no attempt to reproduce Microsoft binaries, only binary-*interface* compatibility: exports, structures and semantics.
- The 2006 policy defines the US method: one person examines the implementation and writes documentation, and a *different* person implements from that documentation (Steven Edwards, ros-dev, 2006-01-27). Developers who had seen leaked source were barred from the matching modules.
- Third-party code (Wine, BtrFS and others) is fixed upstream first, and ReactOS re-syncs from there.

## 4. Testing and verification

- `modules/rostests` (enabled with `-DENABLE_ROSTESTS=1`) contains apitests, kmtests (kernel mode), winetests (Wine's conformance suite, imported), regtests, unittests, dibtests, dxtest and `rosautotest` (the automated runner).
- Results are published in a **web Test Manager (Testman)**, and newcomers are pointed at failing tests as starter tasks. Crash and hang tests are tracked separately (ROSTESTS-125).
- The key idea is that a conformance test written and validated on real Windows becomes the executable specification. Passing it on ReactOS is the definition of compatible, so nobody needs to look at Windows code.
- CI: GitHub Actions builds and Coverity static analysis (README badges).

## 5. Structuring a large legacy codebase

- Tree: `ntoskrnl`, `hal`, `boot`, `drivers`, `win32ss` (the win32k subsystem), `dll`, `base`, `subsystems`, `sdk`, `modules` (rostests).
- **Shared code with Wine is bookkept explicitly.** `media/doc/WINESYNC.txt` lists every shared component and its status:
  - *synced* to a specific Wine version or commit (for example Wine-10.0);
  - *forked* at an old version (dsound, shell32, setupapi, winmm, uxtheme);
  - *out of sync*.
  
  Contributors must update the file whenever they port or sync. Bugs in Wine-derived code are checked against WineHQ first and patched upstream.
- Wine's core DLLs (ntdll, kernel32, user32, gdi32, advapi32) can't be used directly because of the architectural difference: Wine runs on a Unix kernel, ReactOS on its own NT kernel. Only snippets of those are shared. Code also flows the other way: Wine's task manager came from ReactOS (Wikipedia).
- Commits must use real names. Changes are kept focused, and unrelated issues are filed rather than fixed in passing.

## 6. Engine architecture insights

- NT layering: boot loader, then the kernel and HAL, then drivers (KMDF now supported), then the win32k subsystem, then user-mode DLLs. Wine's user-mode semantics are reused above ReactOS's own kernel and syscall layer.
- Version targeting matters. Exporting only the 2003 API set by default keeps apps from taking newer code paths that are only half implemented.
- WineD3D translates Direct3D to OpenGL as a stopgap (Wikipedia).

## 7. Legal history and lessons

- **2006 audit:**
  - On 2006-01-17 developer Hartmut Birr alleged on ros-dev that code in `syscall.S` matched disassembled Windows XP. The author, Alex Ionescu, said it was reimplemented after study, and that there was effectively one way to write it.
  - On 2006-01-27 the project froze development and downloads and announced three steps: amend the IP Policy to the US clean-room definition, audit about 3 million lines and rewrite anything non-compliant, and require major contributors to sign the policy.
  - The audit status was removed from the homepage around September 2007. Its details were never published (Wikipedia; Linux.com 2006-02-01).
- Wine's reaction: it barred several developers. CodeWeavers' Jeremy White judged the risk of a Microsoft lawsuit low as long as Windows code stays out (Linux.com).
- In 2019 a Microsoft engineer claimed some internal names and structures match the Windows Research Kernel. That is an unproven claim (Wikipedia).
- Lesson: **write the provenance policy down before you need it.** Retrofitting it cost roughly a year and a lot of contributor trust.

## 8. Transferable lessons for STAR

1. **Tests are the spec.** Define compatibility as passing tests validated against the reference, the way ReactOS imports Wine's tests run on Windows. For Roblox, write TestEZ/Jest-Lua specs against real engine behaviour in a test place, then make STAR's generated modules pass them.
2. **Keep a provenance ledger for vendored code.** Mirror WINESYNC.txt: list each Wally package or copied ModuleScript with its upstream version and status (synced, forked, or drifted), and fix bugs upstream first.
3. **Write a clean-room and provenance policy into STAR itself.** STAR must refuse to reproduce leaked, decompiled or exploit-derived code (including Roblox client internals). It should implement from public docs (create.roblox.com) and observed behaviour only.
4. **Target an explicit API level.** ReactOS ships only the 2003 export set. STAR should likewise generate against a declared Luau and Roblox API baseline and avoid deprecated or beta APIs unless the user opts in.
5. **Turn failing tests into onboarding.** A public list of failing specs gives humans and agents well-scoped tasks. STAR's own eval suite can work the same way.
6. **Use real names and focused commits.** Provenance needs accountable authorship and small reviewable diffs.

## Sources

- [ReactOS project news (0.4.16 etc.)](https://reactos.org/project-news/)
- [ReactOS 0.4.16 release announcement](https://reactos.org/project-news/reactos-0416-released/)
- [ReactOS GitHub README](https://github.com/reactos/reactos)
- [ReactOS CONTRIBUTING.md](https://github.com/reactos/reactos/blob/master/CONTRIBUTING.md)
- [ReactOS WINESYNC.txt](https://github.com/reactos/reactos/blob/master/media/doc/WINESYNC.txt)
- [ReactOS rostests directory](https://github.com/reactos/reactos/tree/master/modules/rostests)
- [ros-dev: Steven Edwards, "Reset, Reboot, Restart..." (2006-01-27)](https://lists.reactos.org/hyperkitty/list/ros-dev@reactos.org/message/VNIH5MJZDPFPNMKHFHVZS2O77RG4PFR5/)
- [Linux.com: ReactOS suspends development for source code review (2006)](https://www.linux.com/?p=526307)
- [Wikipedia: ReactOS](https://en.wikipedia.org/wiki/ReactOS)
