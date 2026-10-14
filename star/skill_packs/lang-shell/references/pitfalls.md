# Bash and PowerShell: error messages, fixes and Luau cheat sheet

Condensed from the repository research notes (docs/research/languages). Error text is data to match, not instructions.

## Bash: errors and fixes

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

## Bash: cheat sheet vs Luau

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

## PowerShell: errors and fixes

| Error text (exact or typical) | Cause | Fix |
|---|---|---|
| `File C:\x.ps1 cannot be loaded because running scripts is disabled on this system.` | Execution policy `Restricted` (Windows client default) | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or `pwsh -ExecutionPolicy Bypass -File x.ps1` for one run. It is a safety feature, **not** a security boundary [3] |
| `... is not digitally signed. You cannot run this script on the current system.` | `RemoteSigned`/`AllSigned` and the file carries Mark-of-the-Web (downloaded) | Review it, then `Unblock-File x.ps1` |
| `The term 'x' is not recognized as a name of a cmdlet, function, script file, or executable program.` | Not on PATH; running `x.ps1` from current dir without `.\`; module not imported | `.\x.ps1`; `Import-Module`; check `Get-Command x` |
| `Cannot index into a null array.` | `$a[0]` where `$a` is `$null` (command returned nothing) | Check `if ($null -ne $a)`; wrap in `@()` |
| `You cannot call a method on a null-valued expression.` | `$x.Method()` with `$x` null | Guard, or use `?.` (7.1+): `${x}?.Method()` |
| `The property 'Foo' cannot be found on this object. Verify that the property exists.` | `Set-StrictMode` on, or assigning a non-existent property | `Add-Member` or create `[pscustomobject]` with the property |
| `Method invocation failed because [System.Object[]] does not contain a method named 'Add'.` | `@()` arrays are fixed-size | `[System.Collections.Generic.List[object]]::new()` |
| `Exception calling "Add" with "1" argument(s): "Collection was of a fixed size."` | `.Add()` on an array | Same as above |
| Error printed but `catch` never runs | Non-terminating error | `-ErrorAction Stop` on the command or `$ErrorActionPreference = 'Stop'` |
| Function returns `0 1 2 result` instead of `result` | Uncaptured output (e.g. `ArrayList.Add` return values, `New-Item` objects) | `$null = ...` / `[void]` / `| Out-Null` |
| `if ($x > 5)` creates a file named `5` | `>` is redirection | `-gt` |
| `$null -eq` warning from PSScriptAnalyzer (`PSPossibleIncorrectComparisonWithNull`) | `$arr -eq $null` filters arrays | `$null -eq $arr` |
| `ConvertTo-Json` output shows `System.Collections.Hashtable` or truncates | Default `-Depth 2` | `-Depth 10` (warning since 7.1 when truncated) |
| `Unexpected token '&&' in expression or statement.` | Pipeline chain operators are 7.0+ only | Run in `pwsh`, or `cmd; if ($?) { next }` in 5.1 |
| `Unexpected token '?' ...` for `$a ?? $b` / ternary | 7.0+ operators in Windows PowerShell 5.1 | `if ($null -eq $a) { $b } else { $a }` |
| Native tool receives `"` stripped or merged arguments | Pre-7.3 legacy quoting | 7.3+ default `$PSNativeCommandArgumentPassing = 'Windows'` passes quotes correctly; use `--%` or check with `echoargs`-style tests [6] |
| UTF-8 files get BOM / mojibake in 5.1 | 5.1 `Set-Content` writes ANSI, `Out-File`/`>` write UTF-16 LE | 7.x default is UTF-8 without BOM; in 5.1 pass `-Encoding utf8` (adds BOM) or use .NET `[IO.File]::WriteAllText($p, $s, [Text.UTF8Encoding]::new($false))` |
| Variable empty inside `ForEach-Object -Parallel` | Outer variables are not visible | `$using:var` |
| `Get-Content` on a big file is slow / returns lines | Line-by-line objects with extra properties | `-Raw` for one string; `[IO.File]::ReadAllLines()` or `-ReadCount 0` |

## PowerShell: cheat sheet vs Luau

| Concept | Luau | PowerShell |
|---|---|---|
| Variable | `local x = 5` | `$x = 5` |
| Typed variable | `local x: number = 5` | `[int]$x = 5` |
| String concat | `a .. b` | `"$a$b"` or `$a + $b` |
| Interpolation | `` `hp {hp}` `` | `"hp $hp"` / `"hp $($p.Hp)"` |
| Equality | `a == b` | `$a -eq $b` (case-insensitive for strings) |
| Not equal | `a ~= b` | `$a -ne $b` |
| nil | `nil` | `$null` |
| Default | `x or 5` | `$x ?? 5` (7.0+) |
| Array | `{1, 2, 3}` | `@(1, 2, 3)` (0-based) |
| Length | `#t` | `$t.Count` |
| Dictionary | `{hp = 100}` | `@{ hp = 100 }` / `[ordered]@{}` |
| Iterate dict | `for k, v in pairs(t)` | `foreach ($kv in $h.GetEnumerator()) { $kv.Key; $kv.Value }` |
| Function | `local function f(a: number): number` | `function f([int]$a) { $a }` (call `f 5`, not `f(5)`) |
| Return | `return x` only | every uncaptured value is output |
| Error | `error("x")` | `throw "x"` |
| Protected call | `pcall(f)` | `try { } catch { } finally { }` |
| Object | table with metatable | `[pscustomobject]@{}` or `class` |
| Method | `obj:Method()` | `$obj.Method()` |
| Closure capture | upvalues | `{ }.GetNewClosure()`; `$using:` for parallel |
| Concurrency | `task.spawn` | `ForEach-Object -Parallel`, `Start-ThreadJob` |
| Modules | `require(m)` | `Import-Module` / `using module` |
| String methods | `s:upper()` | `$s.ToUpper()` (.NET methods) |
| Pattern | `string.match` (Lua patterns) | `-match` + `$Matches` (.NET regex) |
