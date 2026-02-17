# Claude Code Telegram Bot - Windows Restart Script

param(
    [switch]$Debug,
    [switch]$NoAutoRestart,
    [string]$LogPath = "..\..\logs\bot.log"
)

$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Colors
$Green = "`e[32m"
$Yellow = "`e[33m"
$Reset = "`e[0m"

function Write-Status {
    param([string]$Message, [string]$Status = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    switch ($Status) {
        "SUCCESS" { Write-Host "${Green}[$timestamp] ✓ $Message${Reset}" }
        "WARNING" { Write-Host "${Yellow}[$timestamp] ⚠ $Message${Reset}" }
        default { Write-Host "[$timestamp] ℹ $Message" }
    }
}

Write-Status "Restarting Claude Code Telegram Bot..."

# Stop bot
$StopScript = Join-Path $ScriptDir "stop_bot.ps1"
if (Test-Path $StopScript) {
    & $StopScript
    Start-Sleep -Seconds 2
}

# Start bot
$StartScript = Join-Path $ScriptDir "start_bot.ps1"
if (Test-Path $StartScript) {
    $params = @{
        LogPath = $LogPath
    }
    if ($Debug) { $params['Debug'] = $true }
    if ($NoAutoRestart) { $params['NoAutoRestart'] = $true }

    & $StartScript @params
} else {
    Write-Error "start_bot.ps1 not found!"
    exit 1
}
