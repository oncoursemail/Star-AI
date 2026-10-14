# Sources for lang-shell

Official documentation checked by web research on 2026-10-13. Not verified with the STAR knowledge service, which indexes only Roblox and Luau documentation.

| Claim in the skill | Documentation page |
|---|---|
| Expansion order, word splitting, pathname expansion, quoting | https://www.gnu.org/software/bash/manual/bash.html#Shell-Expansions |
| set -e / pipefail semantics and exceptions | https://www.gnu.org/software/bash/manual/bash.html#The-Set-Builtin |
| set -e caveats (BashFAQ 105) and common pitfalls | https://mywiki.wooledge.org/BashFAQ/105 |
| Bash 5.3 features (current-shell command substitution, GLOBSORT, source -p, read -E) | https://lists.gnu.org/archive/html/bug-bash/2025-07/msg00005.html |
| ShellCheck rule texts (SC2086, SC2164, SC2155) | https://www.shellcheck.net/wiki/SC2086 |
| bats-core testing | https://bats-core.readthedocs.io/en/stable/ |
| MSYS2 path conversion on Windows | https://www.msys2.org/docs/filesystem-paths/ |
| PowerShell versions and end-of-support dates (7.6 LTS, 7.4/7.5 end 2026-11-10) | https://learn.microsoft.com/en-us/powershell/scripting/install/powershell-support-lifecycle |
| PowerShell 7.6 changes (ThreadJob module rename, PSWhere/PSForEach) | https://learn.microsoft.com/en-us/powershell/scripting/whats-new/what-s-new-in-powershell-76 |
| Execution policy is not a security boundary | https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies |
| Terminating vs non-terminating errors, try/catch | https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_try_catch_finally |
| $ErrorActionPreference, $PSNativeCommandUseErrorActionPreference | https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_preference_variables |
| ForEach-Object -Parallel, $using:, ThrottleLimit | https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/foreach-object |
| Native argument passing | https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_parsing |
| Windows PowerShell 5.1 differences | https://learn.microsoft.com/en-us/powershell/scripting/whats-new/differences-from-windows-powershell |
| PSScriptAnalyzer | https://learn.microsoft.com/en-us/powershell/utility-modules/psscriptanalyzer/overview |
| Pester discovery and run phases | https://pester.dev/docs/usage/discovery-and-run |

Full research notes: docs/research/languages/bash.md and docs/research/languages/powershell.md in the repository.
