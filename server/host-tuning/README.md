# Brain 1 host tuning for AI inference

Three files, reviewed and run by the owner once at the server console. **Nothing here has been applied to a real host.**
What was run: `tune.sh status`, `apply --dry-run` and `rollback --dry-run` (all read-only, piped over ssh without
sudo) against brain 1, the full apply/rollback logic in a scratch folder, and `visudo -cf` on `star-sudoers`. What was
only written: the real `apply`, the sudoers install and every performance claim below (no before/after numbers exist yet).

| File | What it is |
|---|---|
| `tune.sh` | `apply` / `status` / `rollback` (plus `lxc-notes`, `uninstall`). Idempotent; records the old values; persistent through `/etc/sysctl.d` and a systemd unit; rollback removes both. |
| `star-sudoers` | `/etc/sudoers.d/` file: passwordless `tune.sh status|apply|rollback` and `lxc restart starai`, nothing else. |
| `README.md` | this page |

Placeholders: `<brain1-host>` is the server's address, `<owner-account>` your normal login there, `<container-ip>` the
STAR container, `starops` the example name of the new dedicated account. Do not put real values in this repository.

## 1. What the host looks like (read without sudo, 2026-10-13, uptime 4 weeks)

Ubuntu 24.04, kernel 6.8, EPYC 7451 (24 cores / 48 threads, 4 NUMA nodes, each with one DDR4 channel), 125 GB RAM,
Docker + Pterodactyl wings + MariaDB + LXD (snap) on the same machine. STAR lives in the unprivileged LXC container
`starai` (llama-server router, `numactl --interleave=all`, `--numa distribute`, `-t 24 -tb 48`).

| Setting | Found | Note |
|---|---|---|
| `kernel.numa_balancing` | 1 | since boot (4 weeks): 117 M NUMA hint faults, 26 M pages migrated (about 99 GiB of 4 KiB pages) |
| `vm.swappiness` | 60 | 8 GB swapfile, 3.3 GiB swapped out since boot (`pswpout` 865 k pages), only 11 MB in use now |
| THP `enabled` / `defrag` | `madvise` / `madvise` | `AnonHugePages` 0 kB, `HugePages_Total` 0 |
| cpufreq governor | **not exposed** | no `/sys/devices/system/cpu/cpu*/cpufreq`; cpuidle driver is `none`. There is nothing to set. |
| irqbalance / tuned | inactive / absent | NIC and RAID IRQs are spread over all CPUs; the RAID queues are kernel-managed |
| container limits | none | `starai` sees all 48 threads and all memory |

## 2. What each setting does, the expected effect, and what we decided

Honest expectations: these are small, low-risk changes. Token generation on this machine is limited by memory bandwidth
and cross-die thread sync, not by anything below, so do not expect more than a few percent, and keep the change only if
the measurement in section 4 shows no loss.

**`kernel.numa_balancing` 1 -> 0 (applied).** The kernel periodically unmaps pages to see which node touches them
("hint faults") and then migrates them. llama.cpp pins its threads (`--numa distribute`) and the weights are interleaved
on purpose, so the migrations are pure overhead and can undo the placement; llama.cpp itself prints a warning on every
start when it is on (`ggml-cpu.c`: "has been observed to impair performance"). Expected effect: no more hint-fault stalls
in the generation threads; steadier tok/s. Risk: Docker/Pterodactyl game servers and MariaDB lose automatic page
migration, which matters only for multi-node workloads; they are small. Measure: `numa_hint_faults` and
`numa_pages_migrated` in `tune.sh status` should stop growing.

**`vm.swappiness` 60 -> 10 (applied).** Makes the kernel drop page cache before swapping out process memory. STAR's
anonymous memory (KV cache, prompt cache of 24 GB, compute buffers) is what hurts if it is swapped; 3.3 GiB has been swapped
out since boot already. Expected effect: no swap-in stalls after idle periods. Limit: it does not stop the kernel from
evicting memory-mapped weights from the page cache under pressure (that is file cache, not swap). Not set to 0, so
Docker/game servers can still use the swapfile in an emergency. Measure: `pswpin`/`pswpout` stop growing.

**CPU governor `performance` (skipped on this host).** `tune.sh` sets it only if cpufreq exists and offers it. Brain 1
exposes none (the firmware owns frequency scaling), so `apply` prints "skip". The equivalent here is a BIOS/UEFI choice
(power profile "maximum performance", disable deep C-states): an owner decision at the next maintenance window, not scripted.

**Transparent hugepages: leave at `madvise` (default); `always` is an A/B option only.** Research, with sources:
- llama.cpp never asks for huge pages. On master (`1b70350c`, 2026-10-13) a search of `src/llama-mmap.cpp`,
  `ggml/src/ggml.c`, `ggml-alloc.c`, `ggml-backend.cpp` and `ggml-cpu/ggml-cpu.c` finds no `MADV_HUGEPAGE`,
  `MAP_HUGETLB` or `hugetlb`; weights are `mmap(MAP_SHARED)` file mappings with `posix_madvise(WILLNEED/RANDOM)`, other
  buffers come from `posix_memalign`. With `THP=madvise` that means llama.cpp gets no THP at all (measured:
  `AnonHugePages` 0 kB with the router up).
- `always` would give THP to the anonymous buffers (KV cache, compute buffers, weights loaded with `-lm dio`). Phoronix's
  Linux 6.18 test found `always` faster for llama.cpp text generation and `madvise` faster for prompt processing, with
  small differences. Our own llama-bench sweep (`docs/agents/server-research.md`, s12) found a THP tunable "hurt". So the
  default stays `madvise`; to test: put `THP_ENABLED=always` in `/etc/star-host-tuning.conf` and re-run `apply`.
  Risk of `always`: latency spikes from compaction (`defrag`) and extra memory use for the game servers.
- Sources: <https://github.com/ggml-org/llama.cpp/blob/master/src/llama-mmap.cpp>,
  <https://github.com/ggml-org/llama.cpp/blob/master/ggml/src/ggml-cpu/ggml-cpu.c>,
  <https://www.phoronix.com/review/thp-madvise-always/4> (magnitudes not verified by us),
  <https://docs.kernel.org/admin-guide/mm/transhuge.html>.

**Explicit hugetlbfs reservation: not done, because stock llama.cpp cannot use it.** A reservation
(`vm.nr_hugepages`) only helps a program that maps `MAP_HUGETLB` memory or files on a hugetlbfs mount. llama.cpp does
neither. The one known way to run it on hugepages is an out-of-tree "NUMA mirror" patch that copies the model into
files on `/dev/hugepages` per node, needs root and leaves stale files behind
(<https://github.com/ggml-org/llama.cpp/discussions/12289>); that is a research project (see `docs/agents/ramforge-20261013.md`),
not host tuning. Reserving pages anyway would only take 2 MiB pages away from the game servers and the page cache.
If that ever changes, `tune.sh lxc-notes` prints the container side (`limits.hugepages.2MB`).

**IRQ affinity away from the AI cores (optional, off).** Set `IRQ_AVOID_CPUS=<cpu list>` in the config file and
re-run `apply`; movable IRQs lose those CPUs, kernel-managed ones (the RAID controller's queues here) are skipped, and
`irqbalance` is respected (skipped while it runs). It is off because there are no "AI cores" to move away from: prompt
reading uses all 48 threads, generation 24 threads spread by `--numa distribute`, and the device IRQ rate on this host is
tiny (the busiest sources, SATA and the NIC queues, average about 3 interrupts per second each over 4 weeks of uptime;
the NIC queues are already confined to one NUMA node). Expected gain: about zero. Use it only to experiment.

**Container notes (owner steps, never run by the script).** `./tune.sh lxc-notes` prints them. In short: the container
already sees all CPUs and memory, so no pinning is needed; do **not** shrink `limits.cpu` or `limits.cpu.nodes`
(one node = one memory channel = about 3.9 tok/s, four nodes = about 9.5); hugepage limits only matter if hugepages are
ever reserved; all keys can be changed live. Reference:
<https://canonical.com/lxd/docs/en/stable-5.21/reference/instance_options/>.

## 3. Exact owner steps (about five minutes, no reboot, no restart of STAR)

Review the three files first. Then, from the PC (Git Bash), in the repository folder:

```bash
ssh <owner-account>@<brain1-host> 'mkdir -p ~/host-tuning'       # your home, not /tmp (never sudo a file others can write)
scp server/host-tuning/tune.sh server/host-tuning/star-sudoers <owner-account>@<brain1-host>:host-tuning/
```

At the server console (or in that ssh session), in `~/host-tuning`:

```bash
cd ~/host-tuning
bash tune.sh status                      # read-only: what is set today, VERDICT: not applied
sudo bash tune.sh apply --dry-run        # shows every write, changes nothing
sudo bash tune.sh apply                  # applies, installs /usr/local/sbin/star-host-tune, writes sysctl.d + unit
bash tune.sh status                      # VERDICT: applied
```

Then the dedicated account and the allowlist (only after `apply`, which installs the script path the allowlist names):

```bash
sudo adduser --disabled-password --gecos "STAR host operator" starops   # no password, in no other group
sudo install -d -m 700 -o starops -g starops /home/starops/.ssh
echo '<one public key line, the .pub of the key STAR uses>' | sudo tee /home/starops/.ssh/authorized_keys >/dev/null
sudo chown starops:starops /home/starops/.ssh/authorized_keys && sudo chmod 600 /home/starops/.ssh/authorized_keys
sudo visudo -cf star-sudoers && sudo install -o root -g root -m 440 star-sudoers /etc/sudoers.d/star
sudo -l -U starops                       # must list exactly the five commands in star-sudoers, nothing else
```

Checks (from the PC, with the key above; each "must fail" line must say a password is required):

```bash
ssh starops@<brain1-host> sudo -n /usr/local/sbin/star-host-tune status          # works
ssh starops@<brain1-host> sudo -n /usr/local/sbin/star-host-tune boot            # must fail
ssh starops@<brain1-host> sudo -n /snap/bin/lxc exec starai bash                 # must fail
ssh starops@<brain1-host> id                                                     # groups: starops only
```

Optional hardening: prefix the key line in `authorized_keys` with `restrict,from="<pc-or-container-ip>" ` (restricts
forwarding and the source address; shell and sudo still work).

Using your existing account instead of a new one: change `starops` to that name in `star-sudoers` (two lines). That
account is in the `sudo` and `lxd` groups, so the allowlist adds convenience, not a boundary (see section 5).

Undo any time: `sudo /usr/local/sbin/star-host-tune rollback` (puts the recorded values back, removes the sysctl file, the
unit and the state), `sudo rm /etc/sudoers.d/star`, and `sudo /usr/local/sbin/star-host-tune uninstall` removes the script.

## 4. Measure before and after

Take the quiet lock for every timing run (<= 10 minutes each; background jobs pause while it exists), and wait for the
live slots to be idle (`server/brain/bench/waitidle.sh`). From the PC:

```bash
./star.cmd lock take --owner claude --holder hosttune --server 1        # release with: lock release ... --holder hosttune

# counters + settings (before)
ssh starops@<brain1-host> sudo -n /usr/local/sbin/star-host-tune status > status-before.txt

# 1. chat speed through the API: first-token time, tok/s, prompt tok/s, next-turn reuse, 2 parallel streams
python server/brain/bench/validate.py --base http://<container-ip>:8080 --models star-fast,star-voice --reps 3 --tag hosttune-before

# 2. first-token script (scripted conversation, cold and warm)
python scripts/measure_first_token.py --endpoint http://<container-ip>:8080/v1 --model star-fast \
   --key-file ~/.star/server_api_key --out ttft-before.json

# 3. raw engine speed, same flags as the live service (needs a free window: it loads the model a second time)
ssh <owner-account>@<brain1-host> "lxc exec starai --user 1001 --env LD_LIBRARY_PATH=/opt/star/bin -- \
  numactl --interleave=all /opt/star/bin/llama-bench -m /opt/star/models/qwen3.6-35b-a3b/Qwen3.6-35B-A3B-Q4_K_M.gguf \
  -lm none --numa distribute -t 24 -p 512 -n 64 -r 3" | tee llama-bench-before.txt
```

Then apply (section 3; no brain restart needed, both sysctls act on running processes), repeat the same four commands
with `-after` names, and compare: `python server/brain/bench/validate.py --compare validate-hosttune-before.json
validate-hosttune-after.json`. Run each side at least twice; identical runs here differ by about 1.5% (10.33 vs 10.48 tok/s
in `docs/agents/brain-performance-20261013.md`), so smaller differences are noise. Decision rule: keep the tuning if
tok/s, first-token time and prompt tok/s are not worse beyond noise **and** the counters in `status` (hint faults,
migrations, `pswpin`) stop growing; otherwise run `rollback`. Release the lock afterwards.

For the THP experiment, repeat the same procedure with `THP_ENABLED=always` in `/etc/star-host-tuning.conf` (root-owned,
`KEY=VALUE` lines; keys: `NUMA_BALANCING`, `SWAPPINESS`, `GOVERNOR`, `THP_ENABLED`, `THP_DEFRAG`, `IRQ_AVOID_CPUS`).
llama.cpp must be restarted (`star-brain`) for new allocations to see a changed THP mode, which is why this stays an
explicit, owner-run experiment.

## 5. Risk model of the sudo allowlist

The assumption to defend against: STAR (an LLM agent) can be prompt-injected through a web page, a file or a chat
message, and an attacker then controls whatever STAR's credentials can do. STAR's credential for the host is an ssh key.

| Layer | What it does |
|---|---|
| Dedicated account | `starops` has no password, is in no group (`sudo`, `lxd`, `docker`, `adm` are all absent) and owns nothing. |
| sudoers rules | Exactly five command lines run as root: `star-host-tune status`, `apply`, `rollback`, `lxc restart starai`, `lxc restart starai --force`. sudo matches the whole command line, so no extra arguments, no other subcommand (`exec`, `config`, `delete`, `stop`, `file push`), no other container. `!setenv` and `env_reset` strip the environment. |
| `star-host-tune` | Root-owned (`/usr/local/sbin`, 0755). It refuses to run if it or its folder is writable by anyone else. It takes no environment input, writes only the paths listed in its header, uses fixed bounded values (`numa_balancing` 0/1, `swappiness` 0..100, THP/governor enum values), and reads its optional config from a root-owned file with a strict KEY=VALUE parser (never `source`). `starops` cannot edit the script, the config or the state. |
| What `apply` can do | Set those two sysctls (and the enabled optional ones) to the values the root-owned config says. `rollback` puts back the recorded values. Neither can run a command of the caller's choosing. |
| What `lxc restart starai` can do | Restart STAR's own container: a few minutes of downtime for STAR itself (self-inflicted denial of service at worst). It cannot reach other containers or the game servers. |

So a prompt-injected STAR can, as root, only: read tuning status, re-apply or undo this tuning, and restart its own
container. It cannot get a root shell through sudo, change other settings, or touch Docker/Pterodactyl.

What this does **not** protect against, honestly:
- `starops` itself is a real login: whoever holds the key can run ordinary unprivileged commands on the host (read
  world-readable files, use the host's network). `restrict,from="..."` in `authorized_keys` narrows that. Keep the key
  in STAR's key store only.
- Your existing account is in the `lxd` group, which is root-equivalent by design (any member can start a privileged
  container with the host's disk mounted) and is also in `sudo`. If STAR connected as that account the allowlist would
  bound nothing. That is why the dedicated account is the default.
- A bug in `tune.sh` would run as root. It is about 500 lines of plain bash, has no `eval`, no external input beyond its
  fixed arguments and one root-owned file, and was run read-only against the real host and fully in a scratch folder;
  please still read it before the first `apply`.

## 6. Troubleshooting

- `apply` prints `FAILED:` lines: the value did not read back as written. Run `status`; `rollback` is safe at any time
  (it restores only what was recorded and keeps the state file if something could not be restored).
- `status` says `VERDICT: partial`: persistence files exist but a runtime value was changed afterwards (by hand or
  another tool). Re-run `apply`.
- After a reboot: `systemd-sysctl` re-applies the two sysctls; `star-host-tuning.service` re-applies THP/governor/IRQ
  settings (it does nothing when none are configured). `systemctl status star-host-tuning` shows the result.
- Nothing here restarts Docker, wings, LXD or any container, and nothing here needs a reboot.
