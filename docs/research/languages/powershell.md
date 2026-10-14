# PowerShell for STAR (research, checked 2026-10-13)

Status (verified on Microsoft Learn, page updated 2026-09-09 [1][2]): **PowerShell 7.6 is the current LTS** (GA 2026-03-18, .NET 10, current patch 7.6.6, supported to 2028-11-14). PowerShell **7.5** (stable, .NET 9, 7.5.11) and **7.4** (previous LTS, .NET 8, 7.4.20) are both supported only until **2026-11-10**. **7.7 is in preview** (7.7-preview.3, .NET 11). **Windows PowerShell 5.1** (`powershell.exe`, .NET Framework 4.x) still ships in Windows and gets only servicing fixes. Pester: Gallery listings show **Pester 6.x** (6.1.0, 2026-08) next to the 5.9.x line; Pester 6 details beyond "it exists" are **unverified as of 2026-10-13** (gallery pages did not load) [9].

---

## 1. Mental model

- PowerShell is an **object shell**: commands (cmdlets, functions, scripts, native executables) emit .NET objects into a **pipeline**, not text. `Get-Process | Where-Object CPU -gt 100 | Sort-Object CPU -Descending | Select-Object -First 5 Name, CPU` passes `System.Diagnostics.Process` objects; formatting to text happens only at the end (`Out-Default`).
- Naming: `Verb-Noun` with approved verbs (`Get-Verb`). Parameters are named (`-Path`), positional, or bound from the pipeline (`ValueFromPipeline`, `ValueFromPipelineByPropertyName`).
- **Everything not captured is output.** A function returns *all* uncaptured values written in its body, not just the `return` value. `$list.Add(1)` on an `ArrayList` emits the index into the output; suppress with `$null = ...` or `[void]`.
- Two parsing modes: **expression mode** (`2 + 2`, `"a" -eq "b"`) and **argument mode** (`Write-Output 2 + 2` prints three tokens). The first token of a statement decides.
- Scopes: global, script, local, private, plus `$using:` for remote/parallel runspaces. Child scopes read parent variables; assignment creates a local copy unless you write `$script:x`.
- Comparison operators are words: `-eq -ne -gt -lt -ge -le -like -match -contains -in -is -as`; case-insensitive by default (`-ceq`, `-cmatch` for case-sensitive). `=`, `>`, `<` are assignment and **redirection** (`if ($a > 5)` writes a file named `5`).
- When the left operand is a collection, comparison operators **filter**: `@(1,2,3) -gt 1` returns `2,3`. Therefore always put `$null` on the left: `$null -eq $x`.

## 2. Type system

- Dynamically typed with optional .NET type constraints: `[int]$n = "42"` converts and keeps converting on later assignment; `[string[]]$names`, `[hashtable]`, `[pscustomobject]@{ Name = 'a' }`, `[ordered]@{}`.
- Type conversion is aggressive (`[int]"0x10"` is 16, `[bool]"false"` is `$true` because non-empty strings are truthy). `"10" -lt 9` converts the right side to the left side's type: string comparison.
- Falsy values: `$null`, `$false`, `0`, `""`, empty array, array of one falsy element. `if (@(0))` is false.
- Collections: `@()` arrays are fixed-size; `+=` copies the whole array (O(n^2) in loops). Use `[System.Collections.Generic.List[object]]::new()` and `.Add()`, or collect loop output: `$result = foreach ($x in $xs) { $x * 2 }`.
- Pipeline unrolling: a function that outputs an array of one element hands the caller a scalar; wrap with `@(...)` when you need an array (`@(Get-ChildItem *.txt).Count`). To return an array unrolled-proof use `,$array` or `Write-Output -NoEnumerate`.
- Classes (5.0+): `class Player { [string]$Name; [int]$Hp = 100; [void] Hit([int]$d) { $this.Hp -= $d } }`, enums, inheritance, interfaces. Class definitions are parsed at script-parse time; types used in them must be loaded before (`using module`, `using assembly`).
- `Set-StrictMode -Version Latest` makes reading uninitialized variables and non-existent properties an error.
- `[ValidateSet()]`, `[ValidateRange()]`, `[ValidatePattern()]`, `[ValidateNotNullOrEmpty()]` on parameters give declarative input checks.

## 3. Runtime, concurrency and async model

- Hosted on .NET (Core) for 7.x, .NET Framework for 5.1. Any .NET API is callable: `[System.IO.File]::ReadAllText($p)`, `[Math]::Round(2.5)` (banker's rounding: 2).
- Single-threaded per runspace. Concurrency options:
  - **`ForEach-Object -Parallel`** (7.0+) runs a script block in parallel runspaces; default `-ThrottleLimit 5`; outer variables must be referenced as `$using:var`; each iteration has a fresh runspace (no shared functions/modules unless re-imported). `-AsJob` returns a job. Overhead per item is high (runspace creation), so use it for slow I/O items, not tiny CPU work [5].
    ```powershell
    $urls | ForEach-Object -Parallel {
        $r = Invoke-WebRequest -Uri $_ -TimeoutSec 10
        [pscustomobject]@{ Url = $_; Status = $r.StatusCode }
    } -ThrottleLimit 8
    ```
    Shared state: use thread-safe types (`[System.Collections.Concurrent.ConcurrentDictionary[string,int]]::new()`) passed via `$using:`; never `+=` on a shared array.
  - **Thread jobs** `Start-ThreadJob` (module renamed to **Microsoft.PowerShell.ThreadJob** in 7.6 [2]), `Receive-Job -Wait -AutoRemoveJob`.
  - **Background jobs** `Start-Job` run in a separate **process** (slow, serialized objects).
  - Runspace pools for advanced cases.
- Serialization: objects crossing a process or remoting boundary are **deserialized property bags** (`Deserialized.System.Diagnostics.Process`) without methods.
- Error model [4]:
  - **Non-terminating** errors (most cmdlet errors, e.g. one missing file of many) write to the error stream and continue. `try/catch` does **not** catch them unless you add `-ErrorAction Stop` or set `$ErrorActionPreference = 'Stop'`.
  - **Terminating** errors (`throw`, .NET exceptions, `-ErrorAction Stop`) unwind to `catch`.
  - `$?` is the success of the last command; `$LASTEXITCODE` is the exit code of the last **native** program. Native non-zero exits do not throw unless `$PSNativeCommandUseErrorActionPreference = $true` (7.4+ mainstream) together with `$ErrorActionPreference = 'Stop'` [6].
  - `$Error[0]` is the latest error; `$_` inside `catch` is the `ErrorRecord`; `$_.Exception`, `$_.InvocationInfo.PositionMessage`, `$_.ScriptStackTrace`.
  - `trap {}` exists but `try/catch/finally` is preferred.
- Streams: 1 Success, 2 Error, 3 Warning, 4 Verbose, 5 Debug, 6 Information, plus Progress. `Write-Host` writes to Information (5.0+), so it can be captured with `6>&1`. Return data with `Write-Output` or bare values, diagnostics with `Write-Verbose`/`Write-Information`.

## 4. Tooling and package management

- Install: `winget install Microsoft.PowerShell` (Windows), MSI/ZIP, Homebrew on macOS (PKG now notarized and signed in 7.6 [2]), apt/rpm repositories, .NET global tool, Docker images.
- Side-by-side: `pwsh` (7.x) and `powershell` (5.1) coexist; module paths differ (`$env:PSModulePath`). 7.x can import many Windows-only 5.1 modules via the **Windows PowerShell Compatibility** layer (implicit remoting to a hidden 5.1 session).
- Packages: **PSResourceGet** (`Install-PSResource`, `Find-PSResource`; shipped 7.4+, v1.2.0 in 7.6 [2]) supersedes PowerShellGet v2 (`Install-Module`). Source: PowerShell Gallery. Pin versions: `Install-PSResource Pester -Version '[5.5,6.0)'`, or `#Requires -Modules @{ ModuleName='Pester'; ModuleVersion='5.5.0' }`.
- Modules: `.psm1` + manifest `.psd1` (`New-ModuleManifest`), `Export-ModuleMember` or `FunctionsToExport` in the manifest (explicit lists make autoloading fast).
- Linting: **PSScriptAnalyzer** (`Invoke-ScriptAnalyzer -Path . -Recurse -Settings PSGallery`) [8]; rules such as `PSAvoidUsingWriteHost`, `PSUseApprovedVerbs`, `PSAvoidUsingInvokeExpression`, `PSUseShouldProcessForStateChangingFunctions`, `PSAvoidUsingPlainTextForPassword`, `PSUseDeclaredVarsMoreThanAssignments`. Also does formatting (`Invoke-Formatter`).
- Editor: VS Code PowerShell extension (PowerShell Editor Services), with PSScriptAnalyzer built in. PSReadLine 2.4.x for the console (predictive IntelliSense).
- `#Requires -Version 7.4`, `#Requires -PSEdition Core`, `#Requires -RunAsAdministrator` at the top of a script make requirements explicit.

## 5. Testing

- **Pester** is the standard framework. Pester 5 introduced two phases: **Discovery** (runs the file to find `Describe`/`It`) and **Run**. Code at the top of the file or directly inside `Describe` outside `BeforeAll`/`It` runs during Discovery only; put setup in `BeforeAll` / `BeforeEach` [7].
  ```powershell
  BeforeAll {
      . $PSScriptRoot/../src/Get-Slug.ps1
  }
  Describe 'Get-Slug' {
      It 'lowercases and dashes <Text>' -ForEach @(
          @{ Text = 'Hello World'; Expected = 'hello-world' }
          @{ Text = '  A  B '; Expected = 'a-b' }
      ) {
          Get-Slug $Text | Should -Be $Expected
      }
      It 'throws on empty input' {
          { Get-Slug '' } | Should -Throw
      }
  }
  ```
  Run with `Invoke-Pester -Output Detailed`; configuration object `New-PesterConfiguration` for CI (`.Run.Path`, `.TestResult.Enabled`, `.CodeCoverage.Enabled`).
- Mocking: `Mock Invoke-RestMethod { @{ ok = $true } }` with `-ParameterFilter`; assert with `Should -Invoke Invoke-RestMethod -Times 1 -Exactly`. Mock commands **inside the module scope** with `-ModuleName`.
- `TestDrive:` gives a temporary filesystem; `InModuleScope` tests private functions.
- Pester 6 exists on the Gallery; check its migration notes before upgrading a Pester 5 suite (unverified details).

## 6. Idiomatic patterns (code)

### Advanced function template

```powershell
function Remove-OldBuild {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
    [OutputType([System.IO.FileInfo])]
    param(
        [Parameter(Mandatory, ValueFromPipeline, ValueFromPipelineByPropertyName)]
        [Alias('FullName')]
        [ValidateNotNullOrEmpty()]
        [string[]]$Path,

        [ValidateRange(1, 365)]
        [int]$OlderThanDays = 30
    )
    begin   { $cutoff = (Get-Date).AddDays(-$OlderThanDays) }
    process {
        foreach ($p in $Path) {
            Get-ChildItem -LiteralPath $p -File -ErrorAction Stop |
                Where-Object LastWriteTime -lt $cutoff |
                ForEach-Object {
                    if ($PSCmdlet.ShouldProcess($_.FullName, 'Remove')) {
                        Remove-Item -LiteralPath $_.FullName
                        $_
                    }
                }
        }
    }
}
Get-Item .\builds | Remove-OldBuild -OlderThanDays 7 -WhatIf
```

### Strict script header

```powershell
#Requires -Version 7.4
[CmdletBinding()]
param([Parameter(Mandatory)][string]$ProjectPath)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true   # native non-zero exit -> terminating error (7.4+)

try {
    git -C $ProjectPath status --porcelain
}
catch {
    Write-Error "git failed: $($_.Exception.Message)"
    exit 1
}
finally {
    Pop-Location -ErrorAction SilentlyContinue
}
```

### Output objects, not text

```powershell
Get-ChildItem -Recurse -Filter *.lua |
    ForEach-Object {
        [pscustomobject]@{
            File  = $_.FullName
            Lines = (Get-Content -LiteralPath $_.FullName).Count
        }
    } |
    Sort-Object Lines -Descending |
    Export-Csv lines.csv -NoTypeInformation   # or ConvertTo-Json -Depth 5
```

### Splatting

```powershell
$params = @{
    Uri         = 'https://example.invalid/api'
    Method      = 'Post'
    Body        = ($payload | ConvertTo-Json -Depth 10)
    ContentType = 'application/json'
    TimeoutSec  = 15
}
$response = Invoke-RestMethod @params
```

### Calling native programs

```powershell
& 'C:\Program Files\Tool\tool.exe' --out "$dir\a b.txt" @extraArgs
if ($LASTEXITCODE -ne 0) { throw "tool failed with $LASTEXITCODE" }
# Stop-parsing token for raw arguments:
icacls.exe C:\data --% /grant Users:(OI)(CI)R
```

### Hashtables and JSON

```powershell
$cfg = Get-Content config.json -Raw | ConvertFrom-Json -AsHashtable   # -AsHashtable is 6.0+, not in 5.1
$cfg['volume'] = 0.8
$cfg | ConvertTo-Json -Depth 10 | Set-Content config.json -Encoding utf8NoBOM
```

## 7. Top pitfalls and error-message fixes

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

## 8. Performance

- The pipeline has per-object overhead. For hot loops, `foreach ($x in $xs) {}` statement beats `ForEach-Object`, and `.Where({})`/`.ForEach({})` intrinsic methods (aliases `PSWhere`/`PSForEach` in 7.6 [2]) beat cmdlets.
- Never `$arr += $item` in a loop; use a `List[T]` or assign the loop output.
- String building: `-join`, `[System.Text.StringBuilder]`, not `+=`.
- Filter left: `Get-ChildItem -Filter *.lua` (provider-side) beats `| Where-Object Extension -eq '.lua'`; `Get-CimInstance -Filter`.
- `Measure-Command { ... }` for timing; `Trace-Command` for binding issues.
- Startup: keep `$PROFILE` lean; module autoloading is lazy when manifests list explicit exports.
- 7.x is substantially faster than 5.1 for most workloads (.NET runtime improvements).

## 9. Security

- **Execution policy is not a security boundary** [3]: it is a seatbelt against accidentally running scripts; any user can bypass it (`-ExecutionPolicy Bypass`, piping text to `Invoke-Expression`). Real controls: **WDAC/App Control and AppLocker**, which put PowerShell in **Constrained Language Mode**; script block logging; AMSI scanning.
- Avoid `Invoke-Expression` (`iex`) on any input; use `&` with argument arrays, splatting, or `[scriptblock]::Create` only on trusted text.
- Credentials: `Get-Credential`, `[pscredential]`, `SecureString` (not encrypted on non-Windows; it only avoids plaintext in memory dumps on Windows); use **Microsoft.PowerShell.SecretManagement** + a vault (SecretStore, Azure Key Vault) instead of plaintext in scripts. Never `ConvertTo-SecureString -AsPlainText` with a literal secret in source.
- Logging: enable Script Block Logging and Module Logging via Group Policy in managed environments; transcripts with `Start-Transcript` can capture secrets, so mind where they go.
- Remoting: prefer SSH-based remoting (7.x) or WinRM with HTTPS and Kerberos; never `TrustedHosts = '*'` on production machines.
- Path injection: use `-LiteralPath` with user-supplied paths (wildcards `[` `]` `*` in `-Path` are interpreted).
- Code signing: `Set-AuthenticodeSignature` with a code-signing certificate for `AllSigned` environments.

## 10. Game-dev usage

- Windows build automation: Unity (`Unity.exe -batchmode -quit -projectPath ... -executeMethod Build.Run -logFile -`), Unreal (`RunUAT.bat BuildCookRun`), Godot headless exports, Rojo/Wally/StyLua for Roblox projects, MSBuild/dotnet for C# tools.
- Asset pipeline scripts calling Blender, ImageMagick, ffmpeg with `ForEach-Object -Parallel -ThrottleLimit ([Environment]::ProcessorCount)`.
- Dedicated server management on Windows hosts: services (`New-Service`, `Get-Service`), scheduled tasks (`Register-ScheduledTask`), firewall rules (`New-NetFirewallRule`), log tailing (`Get-Content -Wait -Tail 50`).
- CI on GitHub Actions: `shell: pwsh` runs 7.x on all OSes, which removes bash/cmd differences on Windows runners.
- Example: zip a build with a version stamp.
  ```powershell
  $version = (git describe --tags --always).Trim()
  Compress-Archive -Path .\build\* -DestinationPath ".\dist\game-$version.zip" -Force
  Get-FileHash ".\dist\game-$version.zip" -Algorithm SHA256 | Select-Object Hash
  ```

## 11. Cheat sheet vs Luau

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

## 12. Recent changes and version notes

- **7.6 LTS (2026-03-18, .NET 10)** [2]: `Microsoft.PowerShell.ThreadJob` replaces the `ThreadJob` module name (breaking only for module-qualified calls); `Join-Path -ChildPath` is `string[]`; `WildcardPattern.Escape` escapes lone backticks; PSFeedbackProvider, PSNativeWindowsTildeExpansion, PSRedirectToVariable and PSSubsystemPluginModel became mainstream; `PSForEach`/`PSWhere` aliases for intrinsic methods; `Get-Command -ExcludeModule`; `Get-Clipboard -Delimiter`; `Register-ArgumentCompleter -NativeFallback`; `PipelineStopToken` for cmdlet authors; `-Debug` no longer triggers ShouldProcess prompts; PSResourceGet 1.2.0, PSReadLine 2.4.5; signed and notarized macOS PKG; experimental `PSSerializeJSONLongEnumAsNumber`.
- **7.5 (2025-01, .NET 9)**: `ConvertTo-CliXml`/`ConvertFrom-CliXml` and other cmdlet improvements (see its What's New page); end of support 2026-11-10 [1].
- **7.4 LTS (2023-11, .NET 8)**: `$PSNativeCommandUseErrorActionPreference` mainstream; PSResourceGet shipped; web cmdlet improvements; end of support 2026-11-10 [1].
- **7.3**: `$PSNativeCommandArgumentPassing` default changed (correct quoting of native arguments) [6].
- **7.0/7.1**: ternary `?:`, `??`, `??=`, `?.`, `?[]`, pipeline chain `&&`/`||`, `ForEach-Object -Parallel`.
- **7.7**: preview only (7.7-preview.3 on .NET 11) as of 2026-10-13.
- Windows PowerShell 5.1: frozen feature set; differences to remember: no `&&`/`??`/ternary, UTF-16/ANSI default encodings, `ConvertFrom-Json` lacks `-AsHashtable`, `Invoke-WebRequest` uses IE parsing unless `-UseBasicParsing`.

## Sources

1. https://learn.microsoft.com/en-us/powershell/scripting/install/powershell-support-lifecycle
2. https://learn.microsoft.com/en-us/powershell/scripting/whats-new/what-s-new-in-powershell-76
3. https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies
4. https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_try_catch_finally and https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_preference_variables
5. https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/foreach-object
6. https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_parsing
7. https://pester.dev/docs/quick-start and https://pester.dev/docs/usage/discovery-and-run
8. https://learn.microsoft.com/en-us/powershell/utility-modules/psscriptanalyzer/overview
9. https://www.powershellgallery.com/packages/Pester
10. https://devblogs.microsoft.com/powershell/announcing-powershell-7-6/
11. https://learn.microsoft.com/en-us/powershell/scripting/whats-new/differences-from-windows-powershell
