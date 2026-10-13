# STAR Discord: private, DPAPI-protected Windows setup and launcher.
# The bot token is NEVER passed as a CLI argument, printed, stored in Git,
# or saved unencrypted. Config is bound to the Windows user who created it.
# Commands: .\scripts\star_discord_windows.ps1 -Setup | -Doctor | -Run
[CmdletBinding()]
param(
    [switch]$Setup,
    [switch]$Doctor,
    [switch]$Run
)
$ErrorActionPreference = 'Stop'
if ((@($Setup, $Doctor, $Run) | Where-Object { $_ }).Count -ne 1) {
    throw 'Choose exactly one of -Setup, -Doctor or -Run'
}
if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') {
    throw 'Use this helper only on Windows. Linux uses a private systemd environment file.'
}
$home = Join-Path $env:LOCALAPPDATA 'STAR-Intelligence\discord'
$configPath = Join-Path $home 'bot-settings.json'
$repoRoot = Split-Path -Parent $PSScriptRoot

function Require-Snowflake([string]$value, [string]$label) {
    if ($value -notmatch '^[0-9]{1,20}$' -or $value -match '^0+$') {
        throw "$label needs a numeric Discord ID. Enable Discord Developer Mode and use Copy ID."
    }
    $parsed = [UInt64]::Zero
    if (-not [UInt64]::TryParse($value, [ref]$parsed) -or $parsed -eq 0) {
        throw "Invalid $label."
    }
    return $value
}
function Yes-No([string]$prompt, [bool]$defaultNo = $true) {
    $choice = Read-Host "$prompt (y/N)"
    if ($choice -eq '') { return (-not $defaultNo) }
    if ($choice -notin @('y','Y','yes','YES','n','N','no','NO')) {
        throw 'Answer y or n.'
    }
    return $choice -in @('y','Y','yes','YES')
}
function Get-RunPython {
    $venv = Join-Path $repoRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venv -PathType Leaf) { return @($venv) }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($null -ne $launcher) {
        foreach ($version in @('3.12','3.11')) {
            & $launcher.Source "-$version" -c 'import sys; assert (3, 11) <= sys.version_info[:2] <= (3, 12)' 2>$null
            if ($LASTEXITCODE -eq 0) { return @($launcher.Source, "-$version") }
        }
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -ne $python) { return @($python.Source) }
    throw 'Install Python 3.11 or 3.12 and STAR requirements first.'
}

if ($Setup) {
    New-Item -ItemType Directory -Path $home -Force | Out-Null
    Write-Host 'STAR Discord Setup (no token is sent to ChatGPT or printed)' -ForegroundColor Cyan
    Write-Host 'Open https://discord.com/developers/applications and create your STAR AI bot.'
    $ownerId = Require-Snowflake (Read-Host 'Your own Discord User ID') 'Owner ID'
    $guildInput = (Read-Host 'Private test server ID (Enter to skip slash-command sync)').Trim()
    $guildId = ''
    if ($guildInput) { $guildId = Require-Snowflake $guildInput 'Test server ID' }
    $dmImages = Yes-No 'Allow private image attachments for STAR vision?'
    $dmLessons = Yes-No 'Allow explicit "remember:" DMs to create REVIEW-ONLY learning candidates?'
    $secret = Read-Host 'Paste Discord Bot Token here (input will stay hidden)' -AsSecureString
    if ($null -eq $secret -or $secret.Length -lt 20) {
        throw 'Bot token is missing or unexpectedly short.'
    }
    # ConvertFrom-SecureString without an explicit key uses Windows user DPAPI.
    $ciphertext = ConvertFrom-SecureString -SecureString $secret
    $record = [ordered]@{
        format = 'star-discord-windows-v1'
        encrypted_token = $ciphertext
        owner_id = $ownerId
        guild_id = $guildId
        dm_chat = $true
        dm_images = [bool]$dmImages
        dm_learning_candidates = [bool]$dmLessons
    }
    $json = $record | ConvertTo-Json -Depth 3
    [System.IO.File]::WriteAllText($configPath, $json, (New-Object System.Text.UTF8Encoding($false)))
    $secret.Dispose()
    Write-Host 'Saved encrypted bot settings under your Windows user profile.' -ForegroundColor Green
    Write-Host 'Next: use -Doctor, then -Run. The bot will only run while that process is running.'
    exit 0
}

if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw 'No local Discord setup found. Run -Setup first.'
}
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
if ($config.format -ne 'star-discord-windows-v1') {
    throw 'Unrecognized Discord bot setup format.'
}
$ownerId = Require-Snowflake ([string]$config.owner_id) 'Owner ID'
$guildId = [string]$config.guild_id
if ($guildId) { $guildId = Require-Snowflake $guildId 'Test server ID' }
$secure = ConvertTo-SecureString -String ([string]$config.encrypted_token)
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $env:STAR_DISCORD_BOT_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    $secure.Dispose()
}
$env:STAR_DISCORD_OWNER_IDS = $ownerId
$env:STAR_DISCORD_GUILD_IDS = $guildId
$env:STAR_DISCORD_SYNC_COMMANDS = $(if ($guildId) { '1' } else { '0' })
if ($guildId) { $env:STAR_DISCORD_SYNC_GUILD_ID = $guildId }
$env:STAR_DISCORD_DM_CHAT = '1'
$env:STAR_DISCORD_DM_IMAGES = $(if ($config.dm_images -eq $true) { '1' } else { '0' })
$env:STAR_DISCORD_DM_LEARNING_CANDIDATES = $(if ($config.dm_learning_candidates -eq $true) { '1' } else { '0' })
$env:STAR_DISCORD_DM_PROJECT = 'STAR'

try {
    $command = @(Get-RunPython)
    $exe = $command[0]
    $args = @()
    if ($command.Count -gt 1) { $args = @($command[1..($command.Count - 1)]) }
    Push-Location $repoRoot
    try {
        if ($Doctor) {
            Write-Host 'STAR Discord readiness (no Discord API request):' -ForegroundColor Cyan
            & $exe @args -m star.discord_bot doctor
        } else {
            Write-Host 'Starting STAR Discord. Stop with Ctrl+C. Tokens remain private.' -ForegroundColor Cyan
            & $exe @args -m star.discord_bot
        }
        exit $LASTEXITCODE
    } finally {
        Pop-Location
    }
} finally {
    # Never leave the bot token in the parent's session after the run.
    Remove-Item Env:\STAR_DISCORD_BOT_TOKEN -ErrorAction SilentlyContinue
}
