# Offline Windows smoke test for STAR's Discord setup wizard.
# Uses a dummy token, temporary LOCALAPPDATA and no Discord/network requests.
$ErrorActionPreference = 'Stop'
$helper = Join-Path $PSScriptRoot 'star_discord_windows.ps1'
if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) {
    throw 'Discord setup helper is missing'
}
$testRoot = Join-Path $env:TEMP ('star-discord-ci-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
$before = $env:LOCALAPPDATA
$beforeHelper = $env:STAR_DISCORD_TEST_HELPER
$env:LOCALAPPDATA = $testRoot
$env:STAR_DISCORD_TEST_HELPER = $helper
try {
    # Run the child in its own PowerShell 5.1 process because -Setup ends with exit.
    # The real user prompt is replaced only in this child process.
    $child = @'
$ErrorActionPreference='Stop'
function Read-Host {
    param([string]$Prompt,[switch]$AsSecureString)
    if ($AsSecureString) {
        return ConvertTo-SecureString 'DUMMY-NOT-A-DISCORD-BOT-TOKEN-1234567' -AsPlainText -Force
    }
    if ($Prompt -like 'Your own Discord User ID*') { return '123456789012345678' }
    if ($Prompt -like 'Private test server ID*') { return '234567890123456789' }
    return 'n'
}
& $env:STAR_DISCORD_TEST_HELPER -Setup
'@
    & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command $child
    if ($LASTEXITCODE -ne 0) { throw 'Discord setup helper failed its fake-token run' }
    $saved = Join-Path $testRoot 'STAR-Intelligence\discord\bot-settings.json'
    if (-not (Test-Path -LiteralPath $saved -PathType Leaf)) {
        throw 'Discord wizard did not create the expected configuration file'
    }
    $config = Get-Content -LiteralPath $saved -Raw | ConvertFrom-Json
    if ($config.format -ne 'star-discord-windows-v1') { throw 'Invalid generated config format' }
    if ($config.owner_id -ne '123456789012345678') { throw 'Wizard recorded wrong owner' }
    if ($config.guild_id -ne '234567890123456789') { throw 'Wizard recorded wrong test guild' }
    if ($config.dm_chat -ne $true -or $config.dm_images -ne $false -or
        $config.dm_learning_candidates -ne $false) { throw 'Incorrect opt-in defaults' }
    if ($config.encrypted_token -match 'DUMMY|DISCORD-BOT-TOKEN') {
        throw 'Secret appears unencrypted in settings'
    }
    if ($config.encrypted_token.Length -lt 80) {
        throw 'Protected token output is unexpectedly short'
    }
    Write-Output 'Windows Discord setup passed with dummy token and DPAPI encryption'
} finally {
    $env:LOCALAPPDATA = $before
    if ($null -eq $beforeHelper) {
        Remove-Item Env:\STAR_DISCORD_TEST_HELPER -ErrorAction SilentlyContinue
    } else {
        $env:STAR_DISCORD_TEST_HELPER = $beforeHelper
    }
    Remove-Item -LiteralPath $testRoot -Recurse -Force -ErrorAction SilentlyContinue
}
