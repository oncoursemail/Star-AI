# Host tuning for brain 1 (Claude, board item #85 host-tuning-20261013)

Status: FILES WRITTEN, PR #269 open (board #85); owner steps pending. Branch `star/host-tuning-20261013`, worktree `worktrees/host-tuning`.
Task: write reviewable files the owner runs once at the brain-1 console (tune.sh and README; the star-sudoers allowlist was dropped in a46575c at the owner's request). Nothing was
run with sudo and no host setting was changed by this item.

## What was read on the host (read-only, no sudo, 2026-10-13)
- Kernel 6.8.0-139, Ubuntu 24.04.2, EPYC 7451 (4 NUMA nodes, 12 threads each, interleaved numbering), 125 GB.
- THP: enabled=madvise, defrag=madvise, AnonHugePages 0 kB, HugePages_Total 0.
- kernel.numa_balancing=1, vm.swappiness=60, 8 GB swapfile with 11 MB used, irqbalance inactive, no tuned/cpufrequtils.
- NO cpufreq directory (no scaling governor is exposed), cpuidle driver "none": the governor step cannot do anything
  on this host (it is skipped by the script; BIOS power profile is an owner decision).
- vmstat since boot: numa_hint_faults 117 M, numa_pages_migrated 26 M (about 99 GiB of 4 KiB pages moved): this is the
  cost numa_balancing=1 adds, and the number `tune.sh status` prints for before/after.
- LXD is the snap (5.21); container `starai` is unprivileged with no CPU/hugepage limits (profile `starai`).
- Other host services: Docker, Pterodactyl wings, MariaDB, two more LXC containers. The tuning does not touch them.
- Operator account is in groups sudo + lxd (lxd is root-equivalent, see README risk model).

## Research: can llama.cpp use hugepages?
- llama.cpp master (1b70350c, 2026-10-13): `src/llama-mmap.cpp` maps the model with `mmap(MAP_SHARED[|MAP_POPULATE])`
  plus `posix_madvise(WILLNEED/RANDOM)`; `ggml.c` allocates with `posix_memalign`. grep for MADV_HUGEPAGE, MAP_HUGETLB,
  hugetlb over llama-mmap.cpp, ggml.c, ggml-alloc.c, ggml-backend.cpp, ggml-cpu.c, ggml-cpu.cpp: no match. Only the
  optional HBM allocator (GGML_USE_CPU_HBM) differs.
  => with THP=madvise (the current setting) llama.cpp never asks for THP, so it gets none; hugetlbfs cannot be used by
  stock llama.cpp. discussion #12289 (ggml-org/llama.cpp) only works with an out-of-tree NUMA-mirror patch, root and
  model files copied into /dev/hugepages: not done here.
- Our own measurement (docs/agents/server-research.md, s12): a THP tunable "hurt". Phoronix (Linux 6.18) found `always`
  faster for generation, `madvise` faster for prompt processing, small differences.
  => tune.sh keeps THP at madvise by default and offers `THP_ENABLED=always` only as an A/B option. No hugetlbfs
  reservation is written.
- llama.cpp itself warns on every start when numa_balancing is on (ggml-cpu.c: "has been observed to impair performance").

## Status log
- 19:30Z claim added (board #85), worktree from origin/star/next (3916c5a). Read host state over ssh (no sudo).
- 19:45Z written: `server/host-tuning/tune.sh` (apply|status|rollback|lxc-notes|uninstall|boot, --dry-run),
  `star-sudoers`, `README.md`.
  RAN (all read-only on the real host, nothing changed): `tune.sh status`, `apply --dry-run`, `rollback --dry-run`
  piped over ssh without sudo (output as expected: numa_balancing 1->0, swappiness 60->10, governor skipped because no
  cpufreq, THP kept, IRQ off); `visudo -cf /dev/stdin` on the host: "parsed OK".
  RAN locally (Git Bash, scratch folder via STAR_TUNE_TEST_ROOT, which tune.sh ignores for root): apply, apply twice,
  status, rollback incl. governors, THP, IRQ affinity and conf parsing: state restored exactly. In that test the fake THP
  file had no `[x]` bracket, so the THP read-back reported a (test-only) failure; rollback still restored it.
  NOT RUN: the real `apply` / `rollback` as root, the sudoers install, `systemctl enable`, any before/after measurement.
  No sudo was used and no host setting was changed.
- Next step (owner): README section 3 (scp, `sudo bash tune.sh apply`, create account, `visudo -cf`, install). Then a
  measurement session under the quiet lock with `--holder hosttune` (README section 4) and a decision to keep or roll back.
- Open questions: (1) whether to also set a BIOS power profile (owner, maintenance window). (2) THP=always A/B: only
  worth doing if llama.cpp ever allocates anonymous memory for weights (`-lm dio` does) and only with the lock.
- 19:55Z PR #269 opened against star/next (ready); full pytest 6336 passed, 243 skipped. Claim marked done.
- 2026-10-14 cloud review (Claude): no sudoers file is in the PR any more (dropped in a46575c); lock file moved from the
  world-writable /run/lock to /run (root-only). Re-ran apply/apply/status/rollback in a scratch root (Git Bash): restored.
