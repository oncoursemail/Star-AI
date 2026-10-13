#!/usr/bin/env bash
# star-host-tune: host-level tuning for AI inference on the STAR brain machine (Ubuntu 24.04, AMD EPYC, 4 NUMA nodes).
#
#   sudo bash tune.sh apply [--dry-run]    record the current values, apply the tuning, make it persistent
#   sudo bash tune.sh rollback [--dry-run] put the recorded values back and remove everything apply installed
#   bash   tune.sh status                  read-only report (works without root)
#   bash   tune.sh lxc-notes               print (never run) the optional lxc commands for the container
#   sudo bash tune.sh uninstall            rollback, then remove the installed script and the optional config file
#   (internal) boot                        re-applies the non-sysctl settings; started by star-host-tuning.service
#
# What it changes (every item is skipped, not failed, when the host does not expose it):
#   kernel.numa_balancing   1 -> 0       sysctl.d file     (llama.cpp warns about it on every start)
#   vm.swappiness           60 -> 10     sysctl.d file
#   CPU governor            -> performance                  only if cpufreq is exposed (it is NOT on brain 1)
#   transparent hugepages   untouched by default (madvise); THP_ENABLED/THP_DEFRAG in the config file change them
#   IRQ affinity            untouched by default; IRQ_AVOID_CPUS in the config file steers movable IRQs away
#   no hugetlbfs reservation: stock llama.cpp cannot use it (see README.md)
# What it never touches: Docker, Pterodactyl, LXD settings, containers, the network, the STAR brain service.
#
# Files it writes (root only):
#   /usr/local/sbin/star-host-tune                     copy of this script
#   /etc/sysctl.d/90-star-host-tuning.conf             persistent sysctl values
#   /etc/systemd/system/star-host-tuning.service       boot-time re-apply of the non-sysctl settings
#   /var/lib/star-host-tuning/state                    the values found before the first apply (for rollback)
# Optional input: /etc/star-host-tuning.conf (KEY=VALUE lines, owned by root, parsed - never sourced).
#
# Safe to run twice: the state file keeps the ORIGINAL values from the first apply, a second apply only re-asserts.
# Security: runs as root, so it takes no environment input, accepts only the arguments above,
# parses its config with fixed patterns, and refuses to run from /usr/local/sbin if the file or folder is writable by
# anyone but root.

set -u
umask 022
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
unset BASH_ENV ENV CDPATH IFS LD_PRELOAD LD_LIBRARY_PATH 2>/dev/null || true
LC_ALL=C; export LC_ALL

# ---------------------------------------------------------------------------------------------------------- paths
# STAR_TUNE_TEST_ROOT prefixes every path so the logic can be tested in a scratch folder. It is honoured ONLY when the
# caller is not root, so it can never redirect a privileged run.
R="${STAR_TUNE_TEST_ROOT:-}"
if [ -n "$R" ] && [ "$(id -u)" = 0 ]; then
  echo "star-host-tune: STAR_TUNE_TEST_ROOT is ignored for root; refusing to run with it set" >&2
  exit 2
fi
INSTALL_PATH=/usr/local/sbin/star-host-tune
P_INSTALL="$R$INSTALL_PATH"
P_STATEDIR="$R/var/lib/star-host-tuning"
P_STATE="$P_STATEDIR/state"
P_SYSCTL="$R/etc/sysctl.d/90-star-host-tuning.conf"
P_UNIT="$R/etc/systemd/system/star-host-tuning.service"
P_CONF="$R/etc/star-host-tuning.conf"
P_LOCK="$R/run/lock/star-host-tune.lock"
P_THP="$R/sys/kernel/mm/transparent_hugepage"
P_CPU="$R/sys/devices/system/cpu"
P_NUMABAL="$R/proc/sys/kernel/numa_balancing"
P_SWAPPINESS="$R/proc/sys/vm/swappiness"

# ------------------------------------------------------------------------------------------------ defaults + config
NUMA_BALANCING=0          # 0 or 1
SWAPPINESS=10             # 0..100
GOVERNOR=performance      # only used when cpufreq is exposed
THP_ENABLED=              # empty = leave alone; always | madvise | never
THP_DEFRAG=               # empty = leave alone; always | defer | defer+madvise | madvise | never
IRQ_AVOID_CPUS=           # empty = off; cpu list such as 0-1 or 0,24: movable IRQs are kept off these CPUs

DRY=0
BOOT=0
FAILS=0
declare -A ST=()

say()  { printf '%s\n' "$*"; }
note() { printf '%s\n' "$*"; if [ -z "$R" ]; then logger -t star-host-tune -- "$*" 2>/dev/null || true; fi; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }
die()  { printf 'star-host-tune: %s\n' "$*" >&2; exit 1; }
fail() { printf 'FAILED: %s\n' "$*" >&2; FAILS=$((FAILS + 1)); }

usage() {
  cat >&2 <<'EOF'
usage: star-host-tune status | apply [--dry-run] | rollback [--dry-run] | lxc-notes | uninstall
EOF
  exit 2
}

need_root() {
  if [ "$DRY" = 1 ] || [ -n "$R" ]; then return 0; fi
  [ "$(id -u)" = 0 ] || die "this mode needs root (run it with sudo)"
}

# Refuse a root-run copy of this script that someone other than root could have edited.
check_self_trust() {
  [ -z "$R" ] || return 0
  local self dir
  self=$(readlink -f -- "${BASH_SOURCE[0]}" 2>/dev/null) || return 0
  [ "$self" = "$INSTALL_PATH" ] || return 0
  dir=$(dirname -- "$self")
  local m u
  read -r u m < <(stat -c '%u %a' -- "$self")
  [ "$u" = 0 ] || die "$self is not owned by root; refusing to run"
  [ $(( 8#$m & 8#022 )) -eq 0 ] || die "$self is writable by group/others; refusing to run"
  read -r u m < <(stat -c '%u %a' -- "$dir")
  [ "$u" = 0 ] || die "$dir is not owned by root; refusing to run"
  [ $(( 8#$m & 8#022 )) -eq 0 ] || die "$dir is writable by group/others; refusing to run"
}

# ------------------------------------------------------------------------------------------------------- cpu lists
# expand "0-2,5" -> "0 1 2 5" ; invalid input returns 1
expand_cpulist() {
  local item out="" a b i
  local IFS=,
  for item in $1; do
    if [[ $item =~ ^([0-9]+)-([0-9]+)$ ]]; then
      a=${BASH_REMATCH[1]}; b=${BASH_REMATCH[2]}
      [ "$a" -le "$b" ] && [ "$b" -lt 4096 ] || return 1
      for ((i = a; i <= b; i++)); do out+="$i "; done
    elif [[ $item =~ ^[0-9]+$ ]] && [ "$item" -lt 4096 ]; then
      out+="$item "
    else
      return 1
    fi
  done
  printf '%s' "$out"
}

load_conf() {
  [ -f "$P_CONF" ] || return 0
  if [ -z "$R" ]; then
    local u m
    read -r u m < <(stat -c '%u %a' -- "$P_CONF")
    [ "$u" = 0 ] && [ $(( 8#$m & 8#022 )) -eq 0 ] || die "$P_CONF must be owned by root and not writable by others"
  fi
  local line key val
  while IFS= read -r line || [ -n "$line" ]; do
    line=${line%%#*}
    line=${line//[[:space:]]/}
    [ -n "$line" ] || continue
    if [[ ! $line =~ ^([A-Z_]+)=([A-Za-z0-9_.,+-]*)$ ]]; then die "$P_CONF: cannot parse line '$line'"; fi
    key=${BASH_REMATCH[1]}; val=${BASH_REMATCH[2]}
    case $key in
      NUMA_BALANCING) [[ $val =~ ^[01]$ ]] || die "$P_CONF: NUMA_BALANCING must be 0 or 1"; NUMA_BALANCING=$val ;;
      SWAPPINESS)     [[ $val =~ ^[0-9]+$ ]] && [ "$val" -le 100 ] || die "$P_CONF: SWAPPINESS must be 0..100"; SWAPPINESS=$val ;;
      GOVERNOR)       [[ $val =~ ^[a-z_]+$ ]] || die "$P_CONF: bad GOVERNOR"; GOVERNOR=$val ;;
      THP_ENABLED)    case $val in ''|always|madvise|never) THP_ENABLED=$val ;; *) die "$P_CONF: bad THP_ENABLED" ;; esac ;;
      THP_DEFRAG)     case $val in ''|always|defer|defer+madvise|madvise|never) THP_DEFRAG=$val ;; *) die "$P_CONF: bad THP_DEFRAG" ;; esac ;;
      IRQ_AVOID_CPUS) if [ -n "$val" ]; then expand_cpulist "$val" >/dev/null || die "$P_CONF: bad IRQ_AVOID_CPUS"; fi; IRQ_AVOID_CPUS=$val ;;
      *) warn "$P_CONF: unknown key $key ignored" ;;
    esac
  done < "$P_CONF"
}

# ------------------------------------------------------------------------------------------------------- state file
load_state() {
  ST=()
  [ -f "$P_STATE" ] || return 0
  local k v
  while IFS='=' read -r k v || [ -n "$k" ]; do
    [[ $k =~ ^[a-z0-9_.-]+$ ]] || continue
    ST[$k]=$v
  done < "$P_STATE"
}

# record <key> <value>: keeps the FIRST value ever seen (the true original).
record() {
  local k=$1 v=$2
  [ "$BOOT" = 1 ] && return 0
  [ -z "${ST[$k]+x}" ] || return 0
  ST[$k]=$v
  if [ "$DRY" = 1 ]; then return 0; fi
  mkdir -p -- "$P_STATEDIR" && chmod 755 -- "$P_STATEDIR"
  printf '%s=%s\n' "$k" "$v" >> "$P_STATE" || die "cannot write $P_STATE"
}

write_val() { # path value
  if [ "$DRY" = 1 ]; then say "  [dry-run] would write '$2' to $1"; return 0; fi
  printf '%s' "$2" > "$1" 2>/dev/null
}

svc() { # svc <is-active|is-enabled> <unit>: one word, never two lines
  local v
  v=$(systemctl "$1" "$2" 2>/dev/null | head -1)
  printf '%s' "${v:-n/a}"
}

thp_cur() { sed -n 's/.*\[\([^]]*\)\].*/\1/p' "$1" 2>/dev/null; }

# ----------------------------------------------------------------------------------------------------- the settings
apply_scalar() { # key label path want [thp]
  local key=$1 label=$2 path=$3 want=$4 kind=${5:-plain} cur
  if [ ! -e "$path" ]; then say "  skip  $label: $path not present on this host"; return 0; fi
  if [ "$kind" = thp ]; then cur=$(thp_cur "$path"); else cur=$(cat -- "$path" 2>/dev/null); fi
  [ -n "$cur" ] || { say "  skip  $label: cannot read $path"; return 0; }
  record "$key" "$cur"
  if [ "$cur" = "$want" ]; then say "  ok    $label already $want"; return 0; fi
  if ! write_val "$path" "$want"; then fail "$label: cannot write $path"; return 0; fi
  if [ "$DRY" = 1 ]; then return 0; fi
  if [ "$kind" = thp ]; then cur=$(thp_cur "$path"); else cur=$(cat -- "$path" 2>/dev/null); fi
  if [ "$cur" = "$want" ]; then say "  set   $label: was ${ST[$key]:-?}, now $want"; else fail "$label: wrote $want but reads back $cur"; fi
}

apply_governor() {
  local f any=0 cur cpu avail
  for f in "$P_CPU"/cpu[0-9]*/cpufreq/scaling_governor; do
    [ -e "$f" ] || continue
    any=1
    cpu=${f#"$P_CPU"/}; cpu=${cpu%%/*}
    avail=$(cat -- "$(dirname -- "$f")/scaling_available_governors" 2>/dev/null)
    case " $avail " in *" $GOVERNOR "*) ;; *) say "  skip  governor $cpu: '$GOVERNOR' not offered (available: $avail)"; continue ;; esac
    cur=$(cat -- "$f")
    record "gov.$cpu" "$cur"
    if [ "$cur" = "$GOVERNOR" ]; then continue; fi
    write_val "$f" "$GOVERNOR" || fail "governor $cpu: cannot write"
  done
  if [ "$any" = 0 ]; then
    say "  skip  CPU governor: this host exposes no cpufreq (nothing to set; power profile is a BIOS/UEFI choice)"
  else
    say "  done  CPU governor -> $GOVERNOR (per-CPU originals are in the state file)"
  fi
}

apply_irq() {
  [ -n "$IRQ_AVOID_CPUS" ] || { say "  skip  IRQ affinity: IRQ_AVOID_CPUS is empty (off by default)"; return 0; }
  if [ -z "$R" ] && command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet irqbalance 2>/dev/null; then
    say "  skip  IRQ affinity: irqbalance is running and would undo it (stop it first if you want this)"; return 0
  fi
  local avoid cur new d n c moved=0 locked=0 keep dropped
  avoid=" $(expand_cpulist "$IRQ_AVOID_CPUS") "
  for d in "$R"/proc/irq/[0-9]*; do
    [ -r "$d/smp_affinity_list" ] || continue
    n=${d##*/}
    cur=$(cat -- "$d/smp_affinity_list" 2>/dev/null) || continue
    keep=""; dropped=0
    for c in $(expand_cpulist "$cur"); do
      case "$avoid" in *" $c "*) dropped=$((dropped + 1)) ;; *) keep+="$c," ;; esac
    done
    keep=${keep%,}
    [ -n "$keep" ] || continue                       # the IRQ is only allowed on avoided CPUs: leave it
    [ "$dropped" -gt 0 ] || continue                 # already off the avoided CPUs
    new=$keep
    record "irq.$n" "$cur"
    if [ "$DRY" = 1 ]; then say "  [dry-run] would move irq $n: $cur -> $new"; moved=$((moved + 1)); continue; fi
    if printf '%s' "$new" > "$d/smp_affinity_list" 2>/dev/null; then moved=$((moved + 1)); else locked=$((locked + 1)); fi
  done
  say "  done  IRQ affinity: $( [ "$DRY" = 1 ] && printf 'would move' || printf 'moved') $moved, $locked kernel-managed IRQs cannot be moved (normal for NVMe/RAID queues)"
}

write_sysctl_file() {
  local body
  body="# Written by star-host-tune (server/host-tuning). Remove with: sudo $INSTALL_PATH rollback
kernel.numa_balancing = $NUMA_BALANCING
vm.swappiness = $SWAPPINESS
"
  if [ "$DRY" = 1 ]; then say "  [dry-run] would write $P_SYSCTL:"; printf '%s' "$body" | sed 's/^/      /'; return 0; fi
  mkdir -p -- "$(dirname -- "$P_SYSCTL")"
  printf '%s' "$body" > "$P_SYSCTL.tmp" && mv -f -- "$P_SYSCTL.tmp" "$P_SYSCTL" || fail "cannot write $P_SYSCTL"
  say "  wrote $P_SYSCTL"
}

write_unit() {
  local body="[Unit]
Description=STAR host tuning for AI inference (re-applies THP, governor and IRQ settings at boot)
Documentation=file://$INSTALL_PATH
After=local-fs.target sysinit.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=$INSTALL_PATH boot

[Install]
WantedBy=multi-user.target
"
  if [ "$DRY" = 1 ]; then say "  [dry-run] would write $P_UNIT and enable it"; return 0; fi
  mkdir -p -- "$(dirname -- "$P_UNIT")"
  printf '%s' "$body" > "$P_UNIT.tmp" && mv -f -- "$P_UNIT.tmp" "$P_UNIT" || { fail "cannot write $P_UNIT"; return 0; }
  say "  wrote $P_UNIT"
  if [ -z "$R" ]; then
    systemctl daemon-reload && systemctl enable star-host-tuning.service >/dev/null 2>&1 \
      && say "  enabled star-host-tuning.service" || fail "systemctl enable star-host-tuning.service"
  fi
}

install_self() {
  local self
  self=$(readlink -f -- "${BASH_SOURCE[0]}" 2>/dev/null)
  if [ ! -f "$self" ]; then
    [ "$DRY" = 1 ] && { say "  [dry-run] would install this script as $INSTALL_PATH (not possible from a pipe; run it from the file)"; return 0; }
    die "run this from the file (sudo bash tune.sh apply), not from a pipe"
  fi
  if [ "$self" = "$P_INSTALL" ]; then return 0; fi
  if [ "$DRY" = 1 ]; then say "  [dry-run] would install this script as $INSTALL_PATH (root:root 0755)"; return 0; fi
  mkdir -p -- "$(dirname -- "$P_INSTALL")"
  if [ -n "$R" ]; then
    cp -- "$self" "$P_INSTALL" && chmod 755 -- "$P_INSTALL"
  else
    install -o root -g root -m 0755 -- "$self" "$P_INSTALL"
  fi || { fail "cannot install $INSTALL_PATH"; return 0; }
  say "  installed $INSTALL_PATH"
}

# ------------------------------------------------------------------------------------------------------------ modes
do_apply() {
  need_root
  say "star-host-tune apply$( [ "$DRY" = 1 ] && printf ' (dry run: nothing is changed)')"
  load_conf
  load_state
  install_self
  apply_scalar orig.numa_balancing "kernel.numa_balancing" "$P_NUMABAL" "$NUMA_BALANCING"
  apply_scalar orig.swappiness "vm.swappiness" "$P_SWAPPINESS" "$SWAPPINESS"
  apply_governor
  if [ -n "$THP_ENABLED" ]; then apply_scalar orig.thp_enabled "THP enabled" "$P_THP/enabled" "$THP_ENABLED" thp
  else say "  keep  THP enabled: $(thp_cur "$P_THP/enabled") (THP_ENABLED not set; llama.cpp does not request THP)"; fi
  if [ -n "$THP_DEFRAG" ]; then apply_scalar orig.thp_defrag "THP defrag" "$P_THP/defrag" "$THP_DEFRAG" thp; fi
  apply_irq
  write_sysctl_file
  write_unit
  if [ "$DRY" = 1 ]; then say "dry run finished; nothing was changed"; return 0; fi
  [ "$FAILS" = 0 ] || die "$FAILS step(s) failed (see FAILED lines above); run 'status' and, if needed, 'rollback'"
  note "star-host-tune: apply finished. Undo with: sudo $INSTALL_PATH rollback"
}

restore_scalar() { # key label path [thp]
  local key=$1 label=$2 path=$3 kind=${4:-plain} want=${ST[$1]:-} cur
  [ -n "$want" ] || return 0
  [ -e "$path" ] || return 0
  if [ "$kind" = thp ]; then cur=$(thp_cur "$path"); else cur=$(cat -- "$path" 2>/dev/null); fi
  if [ "$cur" = "$want" ]; then say "  ok    $label already $want"; return 0; fi
  if ! write_val "$path" "$want"; then fail "$label: cannot restore $want"; return 0; fi
  [ "$DRY" = 1 ] || say "  restored $label -> $want"
}

do_rollback() {
  need_root
  say "star-host-tune rollback$( [ "$DRY" = 1 ] && printf ' (dry run: nothing is changed)')"
  load_state
  if [ ${#ST[@]} -eq 0 ]; then
    warn "no state file ($P_STATE): the original values were never recorded. Runtime values stay as they are; the"
    warn "files this tool installed are removed, so the kernel defaults return at the next reboot."
  fi
  restore_scalar orig.numa_balancing "kernel.numa_balancing" "$P_NUMABAL"
  restore_scalar orig.swappiness "vm.swappiness" "$P_SWAPPINESS"
  restore_scalar orig.thp_enabled "THP enabled" "$P_THP/enabled" thp
  restore_scalar orig.thp_defrag "THP defrag" "$P_THP/defrag" thp
  local k cpu irq
  for k in "${!ST[@]}"; do
    case $k in
      gov.*) cpu=${k#gov.}; [[ $cpu =~ ^cpu[0-9]+$ ]] && [ -e "$P_CPU/$cpu/cpufreq/scaling_governor" ] \
               && { write_val "$P_CPU/$cpu/cpufreq/scaling_governor" "${ST[$k]}" || fail "governor $cpu restore"; } ;;
      irq.*) irq=${k#irq.}; [[ $irq =~ ^[0-9]+$ ]] && [ -e "$R/proc/irq/$irq/smp_affinity_list" ] \
               && { write_val "$R/proc/irq/$irq/smp_affinity_list" "${ST[$k]}" || true; } ;;
    esac
  done
  if [ "$DRY" = 1 ]; then
    say "  [dry-run] would remove $P_SYSCTL, $P_UNIT and $P_STATEDIR"
    say "dry run finished; nothing was changed"
    return 0
  fi
  if [ -z "$R" ]; then
    systemctl disable star-host-tuning.service >/dev/null 2>&1 || true
  fi
  rm -f -- "$P_SYSCTL" "$P_UNIT"
  if [ -z "$R" ]; then systemctl daemon-reload 2>/dev/null || true; fi
  if [ "$FAILS" = 0 ]; then
    rm -f -- "$P_STATE"; rmdir -- "$P_STATEDIR" 2>/dev/null
    say "  removed $P_SYSCTL, $P_UNIT and the state file"
    note "star-host-tune: rollback finished (the script stays installed at $INSTALL_PATH; 'uninstall' removes it)"
  else
    die "$FAILS value(s) could not be restored; the state file was kept ($P_STATE) so you can retry"
  fi
}

do_uninstall() {
  need_root
  DRY=0
  do_rollback
  rm -f -- "$P_INSTALL" "$P_CONF"
  say "  removed $INSTALL_PATH and $P_CONF"
}

do_lxc_notes() {
  cat <<'EOF'
Optional commands for the STAR container (LXD 5.21). star-host-tune NEVER runs these: changing a container's limits is
the owner's decision. Replace <container> with the STAR container name. Every key below can be changed live; the
current value is printed by `lxc config get <container> <key>` and a key is undone with `lxc config unset <container> <key>`.

1. Hugepages for the container  (only relevant if you reserved hugetlbfs pages on the host: stock llama.cpp does not use
   them, so this is NOT needed today)
     lxc config set <container> limits.hugepages.2MB=<bytes, e.g. 64GiB>      # needs the host hugetlb cgroup
   Host side: echo <n> > /proc/sys/vm/nr_hugepages  (2 MiB pages; reserve while memory is unfragmented, i.e. at boot)

2. CPU pinning  (the container sees all 48 threads by default; the Pterodactyl game servers share them)
     lxc config set <container> limits.cpu 0-47                # explicit set, no change in behaviour (documents intent)
     lxc config set <container> limits.cpu.priority 10         # 10 is the maximum scheduling weight (the default)
     lxc config set <container> limits.cpu.nodes 0-3           # keep all four memory nodes (the model needs the bandwidth)
   Do NOT shrink the set (for example to one NUMA node): token generation is limited by memory bandwidth, and one
   node has one DDR4 channel (about 3.9 tok/s measured, against about 9.5 with four nodes).
   To protect the container from game-server load instead, lower THEIR weight: limits.cpu.priority on the other containers
   or --cpu-shares / cpuset on the Docker side. That is outside STAR's scope.

3. Swap behaviour of the container
     lxc config set <container> limits.memory.swap.priority 10   # least likely to be swapped (maximum)

Apply with `lxc restart <container>` only if the key you set says it needs one (the keys above do not).
EOF
}

# status is read-only and tolerant: it prints what it can read on this host.
do_status() {
  load_conf
  load_state
  local cur want f n
  say "star-host-tune status  ($(date -u +%Y-%m-%dT%H:%M:%SZ), kernel $(uname -r))"
  printf '%-26s %-14s %-14s %s\n' SETTING CURRENT TARGET NOTE
  stat_row() { # label path target [thp]
    local c
    if [ ! -e "$2" ]; then printf '%-26s %-14s %-14s %s\n' "$1" "n/a" "$3" "not exposed on this host"; return; fi
    if [ "${4:-}" = thp ]; then c=$(thp_cur "$2"); else c=$(cat -- "$2" 2>/dev/null); fi
    if [ "$3" = "(leave)" ]; then printf '%-26s %-14s %-14s %s\n' "$1" "$c" "$3" ""
    elif [ "$c" = "$3" ]; then printf '%-26s %-14s %-14s %s\n' "$1" "$c" "$3" "matches"
    else printf '%-26s %-14s %-14s %s\n' "$1" "$c" "$3" "DIFFERS"; fi
  }
  stat_row "kernel.numa_balancing" "$P_NUMABAL" "$NUMA_BALANCING"
  stat_row "vm.swappiness" "$P_SWAPPINESS" "$SWAPPINESS"
  stat_row "THP enabled" "$P_THP/enabled" "${THP_ENABLED:-(leave)}" thp
  stat_row "THP defrag" "$P_THP/defrag" "${THP_DEFRAG:-(leave)}" thp
  n=0; local govs=""
  for f in "$P_CPU"/cpu[0-9]*/cpufreq/scaling_governor; do
    [ -e "$f" ] || continue
    n=$((n + 1)); govs+="$(cat -- "$f") "
  done
  if [ "$n" = 0 ]; then printf '%-26s %-14s %-14s %s\n' "CPU governor" "n/a" "$GOVERNOR" "cpufreq not exposed; nothing to set"
  else printf '%-26s %-14s %-14s %s\n' "CPU governor" "$(printf '%s\n' $govs | sort | uniq -c | tr -s ' ' | tr '\n' ';')" "$GOVERNOR" "$n CPUs"; fi
  printf '%-26s %-14s %-14s %s\n' "IRQ affinity" "-" "${IRQ_AVOID_CPUS:-(off)}" "irqbalance: $(svc is-active irqbalance)"
  say
  say "Persistence:"
  [ -f "$P_SYSCTL" ] && say "  $P_SYSCTL present" || say "  $P_SYSCTL absent"
  if [ -z "$R" ] && command -v systemctl >/dev/null 2>&1; then
    say "  star-host-tuning.service: enabled=$(svc is-enabled star-host-tuning.service) active=$(svc is-active star-host-tuning.service)"
  fi
  if [ -f "$P_STATE" ]; then say "  state file present: originals recorded for ${#ST[@]} value(s):"; for n in $(printf '%s\n' "${!ST[@]}" | sort | head -8); do say "    $n=${ST[$n]}"; done
  else say "  no state file (the tuning has not been applied, or it was rolled back)"; fi
  say
  say "Evidence counters (compare two readings; they only grow):"
  if [ -r "$R/proc/vmstat" ]; then
    grep -E '^(numa_hint_faults|numa_hint_faults_local|numa_pages_migrated|numa_pte_updates|thp_fault_alloc|thp_fault_fallback|pswpin|pswpout) ' "$R/proc/vmstat" | sed 's/^/  /'
  fi
  if [ -r "$R/proc/meminfo" ]; then
    grep -E '^(AnonHugePages|HugePages_Total|HugePages_Free|SwapTotal|SwapFree|MemAvailable):' "$R/proc/meminfo" | sed 's/^/  /'
  fi
  if [ -z "$R" ] && command -v systemctl >/dev/null 2>&1; then
    say
    say "Other host services (this tool does not touch them): docker=$(svc is-active docker) wings=$(svc is-active wings) lxd=$(svc is-active snap.lxd.daemon)"
  fi
  # one machine-readable verdict line
  local ok=1
  [ ! -e "$P_NUMABAL" ] || [ "$(cat -- "$P_NUMABAL")" = "$NUMA_BALANCING" ] || ok=0
  [ ! -e "$P_SWAPPINESS" ] || [ "$(cat -- "$P_SWAPPINESS")" = "$SWAPPINESS" ] || ok=0
  [ -z "$THP_ENABLED" ] || [ "$(thp_cur "$P_THP/enabled")" = "$THP_ENABLED" ] || ok=0
  [ -z "$THP_DEFRAG" ] || [ "$(thp_cur "$P_THP/defrag")" = "$THP_DEFRAG" ] || ok=0
  if [ "$ok" = 1 ] && [ -f "$P_SYSCTL" ]; then say "VERDICT: applied (runtime values match the target and the persistence files exist)"
  elif [ "$ok" = 1 ]; then say "VERDICT: runtime values match the target but not persistent (no sysctl.d file)"
  elif [ -f "$P_SYSCTL" ]; then say "VERDICT: partial (persistence files exist but a runtime value differs)"
  else say "VERDICT: not applied"; fi
}

# boot: re-apply what sysctl.d cannot (THP, governor, IRQ). No state is recorded and nothing is installed.
do_boot() {
  need_root
  BOOT=1
  load_conf
  load_state
  [ -z "$THP_ENABLED" ] || apply_scalar orig.thp_enabled "THP enabled" "$P_THP/enabled" "$THP_ENABLED" thp
  [ -z "$THP_DEFRAG" ] || apply_scalar orig.thp_defrag "THP defrag" "$P_THP/defrag" "$THP_DEFRAG" thp
  apply_governor
  apply_irq
  note "star-host-tune: boot re-apply finished"
  return 0
}

# ------------------------------------------------------------------------------------------------------------ main
[ $# -ge 1 ] || usage
MODE=$1; shift
for a in "$@"; do
  case $a in
    --dry-run) case $MODE in apply|rollback) DRY=1 ;; *) usage ;; esac ;;
    *) usage ;;
  esac
done

case $MODE in
  status)     do_status; exit 0 ;;
  lxc-notes)  do_lxc_notes; exit 0 ;;
  apply|rollback|uninstall|boot) ;;
  *) usage ;;
esac

check_self_trust
# one run at a time
if [ "$DRY" = 0 ]; then
  mkdir -p -- "$(dirname -- "$P_LOCK")" 2>/dev/null
  if command -v flock >/dev/null 2>&1; then
    exec 9>"$P_LOCK" || die "cannot open $P_LOCK"
    flock -n 9 || die "another star-host-tune is running"
  fi
fi

case $MODE in
  apply)     do_apply ;;
  rollback)  do_rollback ;;
  uninstall) do_uninstall ;;
  boot)      do_boot ;;
esac
exit 0
