---
name: lang-shell
description: Bash 5.x and PowerShell 7.x scripting (also Windows PowerShell 5.1 and Git Bash on Windows). Use when writing, reviewing or debugging shell scripts, build or CI scripts, asset batch jobs, or shell error messages.
---
# Shell scripting: Bash and PowerShell
## Bash (5.3 current; macOS /bin/bash is 3.2)
- Quote every expansion: "$var", "$@", "$(cmd)". Unquoted values are word-split on IFS and globbed. Iterate arrays with "${arr[@]}"; never loop over `ls` output.
- Use `#!/usr/bin/env bash`. `#!/bin/sh` is POSIX sh (dash on Debian/Ubuntu): no arrays, no [[ ]].
- Prefer [[ ]] for strings and patterns, (( )) for numbers. `[[ "10" < "9" ]]` compares text; use -lt or (( )).
- `set -Eeuo pipefail` is a safety net, not error handling: -e is ignored inside if/while conditions, left of && or ||, after !, and in functions called from those contexts. `local x=$(cmd)` hides cmd's failure: declare first, assign second. `(( i++ ))` with i=0 returns status 1 and kills a -e script: write `i=$((i + 1))`. grep with no match exits 1.
- Loops: `while IFS= read -r line; do ...; done < file` (a pipe into while runs it in a subshell and loses variables). NUL-safe file lists: `find ... -print0` with `read -r -d ''` or `xargs -0`.
- Build commands as arrays: `args=(--out "$f"); tool "${args[@]}"`. Never eval user data; put `--` before user-supplied paths.
- Arithmetic contexts evaluate text as expressions: validate numbers with `[[ $x =~ ^[0-9]+$ ]]` before (( )), or input like a[$(cmd)] runs commands.
- Cleanup with `tmp=$(mktemp -d); trap 'rm -rf -- "$tmp"' EXIT`. Use printf '%s\n' instead of echo for data.
- Parameter expansion beats spawning tools: ${p##*/} basename, ${p%/*} dirname, ${v:-default}, ${v:?msg}, ${v//a/b}.
- For big inputs use one awk/sed/grep pass, not a bash loop that spawns a process per line (fork is very slow under Git Bash).
- Lint with ShellCheck (SC2086 quote, SC2164 cd || exit, SC2155 declare/assign) and format with shfmt; test with bats-core.
- `$'\r': command not found` or `bad interpreter: /bin/bash^M` means CRLF line endings: convert to LF and add `*.sh text eol=lf` to .gitattributes.
- Git Bash converts POSIX-looking arguments to Windows paths for native .exe programs; disable with MSYS_NO_PATHCONV=1 or use cygpath.
- Bash 5.3 adds `${ cmd; }` (capture without a subshell) and `${| cmd; }` (result in REPLY); do not use them when older bash must run the script.
## PowerShell (7.6 LTS current; 7.4 and 7.5 support ends 2026-11-10; 5.1 ships in Windows)
- The pipeline carries .NET objects. Filter and select properties; format only at the end. Return [pscustomobject] values, not formatted text.
- Every uncaptured value is function output, not just `return`. Silence side outputs with `$null = ...` or [void].
- Comparison operators are -eq -ne -gt -lt -like -match -contains -in; `>` is redirection. Put $null on the left: `$null -eq $x` (a collection on the left filters).
- try/catch only catches terminating errors. Add `-ErrorAction Stop` or set `$ErrorActionPreference = 'Stop'`. Native programs set $LASTEXITCODE and do not throw unless `$PSNativeCommandUseErrorActionPreference = $true` (7.4+).
- Use advanced functions: [CmdletBinding(SupportsShouldProcess)], typed and validated param() blocks, begin/process/end for pipeline input, $PSCmdlet.ShouldProcess for changes.
- Arrays from @() are fixed size; `+=` copies the array. Use [System.Collections.Generic.List[object]]::new() or assign loop output: `$r = foreach ($x in $xs) { ... }`. Wrap in @() when a command may return one item.
- ConvertTo-Json defaults to -Depth 2: pass -Depth 10. Use -LiteralPath for user paths. Use splatting (@params) for long calls.
- ForEach-Object -Parallel (7.0+) runs separate runspaces: use $using:var, a -ThrottleLimit, and thread-safe collections; it is slow for tiny items.
- 5.1 lacks &&, ||, ??, ?: and -AsHashtable, and writes UTF-16 or ANSI by default; 7.x writes UTF-8 without BOM. State the target version with #Requires -Version.
- Execution policy is not a security boundary; never suggest it as protection. Avoid Invoke-Expression; use the & operator with argument arrays.
- Store secrets with SecretManagement, not plaintext in scripts.
- Lint with PSScriptAnalyzer; test with Pester (put setup in BeforeAll: Pester 5+ runs a discovery phase first; Pester 6 exists, check its migration notes).
