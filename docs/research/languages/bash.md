# Bash for STAR (research, checked 2026-10-13)

Status: GNU Bash **5.3** is the current release line (announced 2025-07-05 by Chet Ramey [1][2]); distributions ship 5.2 or 5.3 (Debian packaged 5.3 by early 2026 [3]). A local Git for Windows install observed on 2026-10-13 reports `GNU bash, version 5.3.15(2)-release`. A bash 5.4 is only visible as distro "alpha snapshots"; **no upstream 5.4 release is verified as of 2026-10-13**. macOS still ships bash **3.2** as `/bin/bash` (GPLv3 licensing), with zsh as the login shell; the Homebrew bash is current.

---

## 1. Mental model

- Bash is a **command language**: every line is parsed into words, expanded, then executed as a command. Data is **strings** (plus indexed and associative arrays of strings). Integers exist only in arithmetic contexts `(( ))`, `$(( ))`, `let`, `declare -i`.
- The order of expansions decides almost every bug [4]:
  1. brace expansion `{a,b}` `{1..5}`
  2. tilde expansion `~`
  3. parameter and variable expansion `$x` `${x:-d}`, command substitution `$(...)`, arithmetic `$((...))`, process substitution `<(...)` (left to right)
  4. **word splitting** (on `$IFS`, only on results of unquoted expansions)
  5. **pathname expansion** (globbing) on unquoted results
  6. quote removal
- Rule of thumb: **quote every expansion** (`"$var"`, `"$@"`, `"$(cmd)"`) unless you explicitly want splitting and globbing. Steps 4 and 5 are why `rm $file` deletes the wrong things.
- Exit status is the boolean: `0` = success/true, non-zero = failure/false. `if`, `&&`, `||`, `while` test **commands**, not expressions. `[` is a command (`test`); `[[ ]]` is shell syntax.
- Each pipeline element runs in a **subshell** (except the last one when `shopt -s lastpipe` and job control is off). Variables set inside `cmd | while read ...; do x=1; done` vanish afterwards.
- Functions share the global scope unless variables are declared `local` (dynamic scoping: a callee sees the caller's locals).
- A script is a program; an interactive shell is a REPL with aliases, history and job control. Aliases are not expanded in scripts unless `shopt -s expand_aliases`.

## 2. Type system

- No static types. Attributes via `declare`:
  - `declare -i n=5` integer (assignments are evaluated arithmetically)
  - `declare -a arr=(a b c)` indexed array; `declare -A map=([k]=v)` associative array (bash 4.0+, not in macOS bash 3.2)
  - `declare -r CONST=1` / `readonly`; `declare -x` export; `declare -l` / `-u` lowercase/uppercase on assignment; `declare -n ref=name` nameref (4.3+)
  - `local` inside functions takes the same flags.
- Everything else is a string. `"10" < "9"` inside `[[ ]]` compares **lexically**; use `(( 10 < 9 ))` or `-lt` for numbers.
- Unset vs empty differ: `${x-default}` (only if unset) vs `${x:-default}` (unset or empty). `[[ -v name ]]` tests "is set" (4.2+; for array elements 4.3+).
- Arrays:
  ```bash
  files=()                      # empty array
  files+=("a b.txt")            # append, keeps the space
  echo "${#files[@]}"           # length
  for f in "${files[@]}"; do printf '%s\n' "$f"; done   # each element one word
  echo "${files[*]}"            # joined with first char of IFS (one word)
  echo "${!files[@]}"           # indices
  declare -A hp=([alice]=100 [bob]=80)
  for k in "${!hp[@]}"; do echo "$k=${hp[$k]}"; done   # order is unspecified
  ```
- Arrays cannot be nested or exported to child processes. Pass arrays to functions as `"$@"` or by nameref.

## 3. Runtime, concurrency and async model

- Every external command is `fork` + `exec`. Builtins (`echo`, `printf`, `read`, `cd`, `test`, `[[`) run in-process. On Windows (Git Bash / MSYS2 / Cygwin) `fork` is emulated and **very slow**; a loop that calls `sed` 10,000 times can take minutes there. Prefer builtins and parameter expansion.
- Subshells: `( ... )`, `$( ... )`, pipelines, `&` background jobs. Changes to variables or `cd` inside them do not escape.
- Bash 5.3 adds **non-forking command substitution** [1][2]: `${ cmd; }` runs `cmd` in the current shell and captures stdout; `${| cmd; }` runs it in the current shell and expands to the value of `REPLY`. Not portable to older bash.
- Concurrency: background jobs with `&`, `wait` (with `wait -n` for "any job", 4.3+; `wait -p var` records which PID, 5.1+), `$!` last PID. `jobs`, `kill %1`. For fan-out with a limit:
  ```bash
  max=4
  for f in *.png; do
    convert "$f" "${f%.png}.webp" &
    while (( $(jobs -rp | wc -l) >= max )); do wait -n; done
  done
  wait
  ```
  Or delegate to `xargs -P 4 -0` / GNU `parallel`.
- Signals: `trap 'cleanup' EXIT` runs on any exit (including `set -e` aborts); `trap 'echo int' INT TERM`; `trap - EXIT` clears. Use `EXIT` for temp-file cleanup.
- Coprocesses: `coproc NAME { cmd; }` gives two FDs in `${NAME[0]}`/`${NAME[1]}`; rarely needed.
- There is no event loop, no threads, no async/await.

## 4. Tooling and package management

- No package manager for bash itself. Reuse is `source lib.sh` (5.3: `source -p PATH file` searches a given path [1]). Distribute scripts with the OS package manager or as plain files.
- Shebang: `#!/usr/bin/env bash` (finds Homebrew bash on macOS). `#!/bin/sh` means POSIX sh (dash on Debian/Ubuntu): no arrays, no `[[ ]]`, no `$'...'`.
- **ShellCheck** is the essential linter [5]: catches unquoted expansions (SC2086), `cd` without error handling (SC2164), useless `cat`, `read` without `-r` (SC2162), etc. Run in CI and in editors (bash-language-server uses it).
- **shfmt** formats (`shfmt -i 2 -ci -w .`).
- Debugging: `bash -n script` (syntax only), `bash -x script` or `set -x` (trace; set `PS4='+ ${BASH_SOURCE}:${LINENO}: '` for file:line), `set -v`.
- Version check inside a script: `(( BASH_VERSINFO[0] >= 4 )) || { echo "need bash 4+" >&2; exit 1; }`.

## 5. Testing

- **bats-core** (Bash Automated Testing System) is the de-facto unit test runner [6]:
  ```bash
  #!/usr/bin/env bats
  setup() { source "$BATS_TEST_DIRNAME/../lib/slug.sh"; }
  @test "slugify lowercases and dashes" {
    run slugify "Hello World"
    [ "$status" -eq 0 ]
    [ "$output" = "hello-world" ]
  }
  ```
  Helpers: bats-support, bats-assert (`assert_output`, `assert_success`), bats-file.
- Make scripts testable: put logic in functions, guard the entry point:
  ```bash
  main() { ... }
  if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then main "$@"; fi
  ```
- Alternatives: shellspec (BDD), shunit2 (older). Always run ShellCheck as a "test".

## 6. Idiomatic patterns (code)

### Script header

```bash
#!/usr/bin/env bash
set -Eeuo pipefail          # see section 7 for the caveats
shopt -s inherit_errexit 2>/dev/null || true   # make $(...) honour -e (bash 4.4+)
IFS=$'\n\t'                 # optional: safer default splitting
trap 'echo "error at ${BASH_SOURCE[0]}:${LINENO}: $BASH_COMMAND" >&2' ERR

tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT

die() { printf '%s\n' "$*" >&2; exit 1; }
```

### Arguments

```bash
usage() { echo "usage: ${0##*/} [-v] [-o out] file..." >&2; exit 2; }
verbose=0 out=
while getopts ':vo:h' opt; do
  case $opt in
    v) verbose=1 ;;
    o) out=$OPTARG ;;
    h) usage ;;
    :) die "-$OPTARG needs a value" ;;
    \?) die "unknown option -$OPTARG" ;;
  esac
done
shift $((OPTIND - 1))
(( $# > 0 )) || usage
```

### Reading lines and files safely

```bash
while IFS= read -r line; do
  printf '%s\n' "$line"
done < input.txt                     # not: cat input.txt | while ... (subshell)

mapfile -t lines < input.txt         # whole file into an array (bash 4+)

# NUL-delimited file lists survive spaces and newlines in names
while IFS= read -r -d '' f; do
  echo "found: $f"
done < <(find . -name '*.lua' -print0)
```

### Parameter expansion instead of external tools

```bash
path=/a/b/file.tar.gz
echo "${path##*/}"     # file.tar.gz   (basename)
echo "${path%/*}"      # /a/b          (dirname)
echo "${path%%.*}"     # /a/b/file     (strip longest suffix)
echo "${path%.gz}"     # /a/b/file.tar
echo "${path/file/x}"  # replace first match; ${v//a/b} replaces all
echo "${#path}"        # length
echo "${name^^} ${name,,}"  # upper / lower (bash 4+)
: "${PORT:=8080}"      # assign default if unset or empty
: "${TOKEN:?TOKEN must be set}"   # fail with message
```

### Conditionals

```bash
[[ -f $cfg && -r $cfg ]] || die "missing $cfg"
[[ $name == *.lua ]]               # glob match (right side unquoted)
[[ $ver =~ ^([0-9]+)\.([0-9]+)$ ]] && major=${BASH_REMATCH[1]}
(( count > 10 )) && echo many
case $os in linux*) ... ;; msys*|cygwin*) ... ;; esac
```

### Running commands built at runtime

```bash
args=(--output "$out" --level 3)
[[ $verbose == 1 ]] && args+=(--verbose)
tool "${args[@]}" -- "$@"          # never build a string and eval it
```

### printf over echo

`echo` treats `-n`/`-e` and backslashes inconsistently across shells; use `printf '%s\n' "$x"`. `printf -v var '%05d' "$n"` assigns without a subshell.

### Locking and idempotence

```bash
exec 9>/var/lock/myjob.lock
flock -n 9 || die "already running"
mkdir -p -- "$dir"                 # idempotent
```

### Here-documents

```bash
cat <<'EOF' > config.toml      # quoted delimiter: no expansion
name = "$literal"
EOF
cat <<-EOF                     # <<- strips leading TABS (not spaces)
	hello $USER
	EOF
```

## 7. Top pitfalls and error-message fixes

| Error text (exact or typical) | Cause | Fix |
|---|---|---|
| `bash: [: too many arguments` | Unquoted variable with spaces or empty inside `[ ]`: `[ $x = y ]` | Quote: `[ "$x" = y ]` or use `[[ $x == y ]]` |
| `bash: [: =: unary operator expected` | Variable expanded to nothing in `[ $x = y ]` | Quote it or use `[[ ]]` |
| `bash: x: unbound variable` | `set -u` and an unset variable / `$1` with no args | `${x:-}` / `${1:-}` / `[[ -v x ]]`; on bash < 4.4 `"${arr[@]}"` of an empty array also triggers it: use `${arr[@]+"${arr[@]}"}` |
| `$'\r': command not found` / `syntax error near unexpected token $'do\r'` | CRLF line endings (file edited on Windows) | `dos2unix script.sh` or `sed -i 's/\r$//'`; add `*.sh text eol=lf` to `.gitattributes` |
| `bad interpreter: /bin/bash^M: no such file or directory` | CRLF on the shebang line | Same as above |
| `syntax error near unexpected token 'fi'` | Missing `then`, or `;` before `then` on one line, or `]` without space | `if [[ ... ]]; then` with spaces around `[[`/`]]` |
| `command not found` for `x =1` / `x= 1` | Spaces around `=` in assignment | `x=1` (no spaces) |
| `declare: -A: invalid option` | macOS `/bin/bash` 3.2 | Install a modern bash, use `#!/usr/bin/env bash` |
| `ambiguous redirect` | Unquoted variable in redirect target that is empty or has spaces | `> "$out"` |
| `Argument list too long` | Glob expands to more than ARG_MAX bytes | `find ... -exec cmd {} +` or `xargs -0` |
| `integer expression expected` | `-lt`/`-eq` with a non-number (often `$x` contains `\r` or spaces) | Validate with `[[ $x =~ ^[0-9]+$ ]]`, strip `\r` |
| `bad substitution` | Running bash syntax under `sh` (dash) or with an old bash | Run with `bash`, fix shebang |
| `ShellCheck SC2086: Double quote to prevent globbing and word splitting` | Unquoted `$var` | Quote it [5] |
| `SC2164: Use 'cd ... \|\| exit' in case cd fails` | `cd` failure continues in the wrong directory | `cd -- "$d" \|\| exit` |
| `SC2155: Declare and assign separately to avoid masking return values` | `local x=$(cmd)` hides `cmd`'s failure from `set -e` | `local x; x=$(cmd)` |
| `SC2002 Useless cat` / variables lost after loop | `cat f \| while read` runs the loop in a subshell | `while ...; done < f` or `shopt -s lastpipe` |
| Script "silently" exits | `set -e` triggered by `(( i++ ))` when `i` was 0: an arithmetic command whose value is 0 has exit status 1 | Use the assignment form `i=$((i + 1))`, which always succeeds |
| `grep` with no match kills a `set -e -o pipefail` script | grep exits 1 for "no match" | `grep ... \|\| true` or test status explicitly |

### The `set -euo pipefail` caveats (BashFAQ 105 [7])

- `-e` is **ignored** in: conditions of `if`/`while`/`until`, commands followed by `&&`/`||` (except the last), negated commands `!`, and **inside functions called from such contexts**. `f() { false; echo still runs; }; f || echo x` prints "still runs".
- Command substitution does not inherit `-e` before 4.4 unless `shopt -s inherit_errexit`.
- `local x=$(failing)` returns the status of `local` (0).
- `-u` breaks on empty arrays in bash < 4.4 and on optional positional args.
- `pipefail` makes `producer | head -1` fail when `producer` gets SIGPIPE (exit 141).
- Conclusion: use them as a safety net, but still check important commands explicitly (`cmd || die "cmd failed"`).

### Git Bash / MSYS2 on Windows quirks

- Path conversion: MSYS converts arguments that look like POSIX paths into Windows paths when calling native `.exe`s. `/c/Users` becomes `C:\Users`; an argument like `/opt` or `//server` can be mangled. Disable per command with `MSYS_NO_PATHCONV=1` (Git for Windows) or `MSYS2_ARG_CONV_EXCL='*'` (MSYS2) [8].
- `cygpath -w "$p"` / `cygpath -u 'C:\x'` to convert explicitly.
- CRLF: configure `git config core.autocrlf false` for repos with shell scripts, or `.gitattributes`.
- `fork` is slow: avoid subshell-heavy loops.
- Native Windows console programs may need `winpty` for interactive use in mintty.
- `/tmp` maps into the Git install; `$HOME` is the Windows profile.
- Executable bit: Git tracks `+x` via `git update-index --chmod=+x script.sh` because NTFS does not.

## 8. Performance

- Builtins and parameter expansion are 100-1000x faster than spawning `sed`/`awk`/`cut` per line; but for **large files** a single `awk`/`sed`/`grep` pass beats a bash `while read` loop by orders of magnitude. Rule: one external process for the whole stream, never one per line.
- `read` is slow (byte-by-byte on pipes). `mapfile` is much faster for loading files.
- Avoid `$(...)` in tight loops; use `printf -v` and 5.3's `${ ...; }` where available.
- `[[ ]]` and `(( ))` are faster and safer than `[ ]` / `expr`.
- `LC_ALL=C` speeds up `sort`/`grep` on ASCII data.
- Measure with `time` / `TIMEFORMAT`, and `hyperfine` for comparisons.

## 9. Security

- **Never `eval` untrusted data.** Build commands as arrays.
- Quote everything; use `--` before user-supplied filenames (`rm -- "$f"`) so names starting with `-` are not options.
- Arithmetic injection: `(( x == $input ))` or `[[ $a -eq $b ]]` evaluate their operands as arithmetic expressions, so `input='a[$(id)]'` **executes `id`**. Validate numeric input with a regex before arithmetic [7].
- Temp files: `mktemp`, never predictable `/tmp/foo.$$`. Set `umask 077` for secrets.
- Do not put secrets on the command line (visible in `ps`); pass via env vars or files with restricted permissions; `set +x` around secret handling.
- `curl ... | bash` executes unreviewed remote code; download, verify a checksum or signature, then run.
- `IFS` and `PATH` can be attacker-controlled in setuid-ish or sudo contexts; set `PATH` explicitly in privileged scripts. Bash ignores setuid bits on scripts anyway.
- Shellshock (CVE-2014-6271) is long fixed, but it is the classic example of why exporting functions via environment variables is dangerous.
- `find -exec sh -c '... "$1"' _ {} \;` instead of interpolating `{}` into the string.

## 10. Game-dev usage

- Build and CI glue: running Rojo/Wally/StyLua/Selene, Godot headless exports (`godot --headless --export-release "Windows Desktop" out.exe`), Unity/Unreal command-line builds, asset pipelines (ImageMagick, ffmpeg, Blender `--background --python`).
- Dedicated server operations on Linux: start scripts, log rotation, systemd units calling bash wrappers, backups with `flock` and timestamps.
- Asset batch conversion with bounded parallelism (section 3).
- On Windows dev boxes, Git Bash runs these scripts but with path conversion and speed caveats; PowerShell 7 is often the better native choice (see powershell.md).
- Example: verify a Roblox project in CI.
  ```bash
  set -Eeuo pipefail
  stylua --check src
  selene src
  rojo build default.project.json -o build.rbxl
  ```

## 11. Cheat sheet vs Luau

| Concept | Luau | Bash |
|---|---|---|
| Variable | `local x = 5` | `x=5` (global) / `local x=5` (in function) |
| String concat | `a .. b` | `"$a$b"` |
| Number compare | `a < b` | `(( a < b ))` or `[[ $a -lt $b ]]` |
| String compare | `a == b` | `[[ $a == "$b" ]]` |
| nil / unset | `nil` | unset variable; test `[[ -v x ]]` |
| Default value | `x or 5` | `${x:-5}` |
| Array | `{1, 2, 3}` | `arr=(1 2 3)` |
| Array length | `#t` | `${#arr[@]}` |
| Index | `t[1]` (1-based) | `${arr[0]}` (0-based) |
| Dictionary | `{a = 1}` | `declare -A m=([a]=1)` |
| Iterate | `for i, v in ipairs(t)` | `for v in "${arr[@]}"` |
| Function | `local function f(a) return a end` | `f() { local a=$1; echo "$a"; }` (output is the "return value") |
| Return value | any value | exit status 0-255 only; data via stdout or nameref |
| Error | `error("x")` / `pcall` | `exit 1` / `cmd \|\| handle`; `trap ... ERR` |
| Truthiness | `nil`/`false` are false | exit status 0 is true |
| String length | `#s` | `${#s}` |
| Substring | `s:sub(2, 4)` | `${s:1:3}` (offset, length) |
| Pattern match | `s:match("%d+")` | `[[ $s =~ ([0-9]+) ]]; ${BASH_REMATCH[1]}` |
| Formatting | `string.format("%d", n)` | `printf '%d' "$n"` |
| Concurrency | `task.spawn` / coroutines | `cmd &` and `wait` (separate processes) |
| Modules | `require(module)` | `source file.sh` |
| Comments | `-- x` | `# x` |

## 12. Recent changes and version notes

- **5.3 (2025-07)** [1][2]: `${ cmd; }` and `${| cmd; }` current-shell command substitution; `GLOBSORT` variable controls glob result ordering; `compgen -V var` stores completions in a variable; `read -E` uses readline with programmable completion; `source -p PATH`; the `test` builtin parses parenthesised sub-expressions differently with more than four arguments; interactive shells defer job notifications until a sourced script finishes; source moved to C23 (no K&R compilers); Readline 8.3.
- **5.2 (2022-09)**: `shopt -s patsub_replacement` (on by default: `&` in `${v/pat/rep}` replacement means the match, which can break replacements containing `&`; quote it as `\&`), `globskipdots` default on, `varredir_close`, `BASH_COMPAT` cleanup.
- **5.1 (2020)**: `wait -p`, `SRANDOM`, `${var@U}`/`@u`/`@L`/`@K` transformations.
- **5.0 (2019)**: `EPOCHSECONDS`, `EPOCHREALTIME`, `BASH_ARGV0`.
- 5.4: only distro development snapshots seen; **unverified as of 2026-10-13**.

## Sources

1. https://lwn.net/Articles/1029079/ (bash-5.3 release announcement mail, 2025-07-05)
2. https://lists.gnu.org/archive/html/bug-bash/2025-07/msg00005.html (bug-bash announcement)
3. https://packages.debian.org/source/sid/bash
4. https://www.gnu.org/software/bash/manual/bash.html (Bash Reference Manual: Shell Expansions, Bash Builtins, The Set Builtin)
5. https://www.shellcheck.net/wiki/ (ShellCheck wiki: SC2086, SC2164, SC2155, SC2162)
6. https://bats-core.readthedocs.io/en/stable/
7. https://mywiki.wooledge.org/BashFAQ/105 and https://mywiki.wooledge.org/BashPitfalls
8. https://www.msys2.org/docs/filesystem-paths/
9. https://git.savannah.gnu.org/cgit/bash.git/tree/NEWS
10. https://www.gnu.org/software/bash/
