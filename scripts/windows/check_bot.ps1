# Claude Code Telegram Bot - Windows Status Check Script

$ErrorActionPreference = "SilentlyContinue"

# Colors
$Green = "`e[32m"
$Red = "`e[31m"
$Yellow = "`e[33m"
$Blue = "`e[34m"
$Reset = "`e[0m"

function Write-Status {
    param([string]$Message, [string]$Status = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    switch ($Status) {
        "SUCCESS" { Write-Host "${Green}[$timestamp] ✓ $Message${Reset}" }
        "ERROR" { Write-Host "${Red}[$timestamp] ✗ $Message${Reset}" }
        "WARNING" { Write-Host "${Yellow}[$timestamp] ⚠ $Message${Reset}" }
        "INFO" { Write-Host "${Blue}[$timestamp] ℹ $Message${Reset}" }
        default { Write-Host "[$timestamp] $Message" }
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Claude Code Telegram Bot Status" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check Python processes
$pythonProcesses = Get-Process | Where-Object {
    $_.ProcessName -like "*python*" -and
    $_.CommandLine -like "*main.py*"
}

$wrapperProcesses = Get-Process | Where-Object {
    $_.ProcessName -eq "powershell" -and
    $_.CommandLine -like "*claude_bot_wrapper*"
}

# Display status
if ($pythonProcesses) {
    Write-Status "Bot is RUNNING" "SUCCESS"
    foreach ($proc in $pythonProcesses) {
        $cpu = if ($proc.CPU) { "{0:N1}" -f $proc.CPU } else { "N/A" }
        $mem = "{0:N1}" -f ($proc.WorkingSet64 / 1MB)
        Write-Status "  PID: $($proc.Id) | CPU: $cpu s | Memory: $mem MB" "INFO"
    }
} else {
    Write-Status "Bot is NOT RUNNING" "ERROR"
}

if ($wrapperProcesses) {
    Write-Status "Auto-restart wrapper is active" "SUCCESS"
    foreach ($proc in $wrapperProcesses) {
        Write-Status "  Wrapper PID: $($proc.Id)" "INFO"
    }
}

# Check log file
$LogPath = "..\..\logs\bot.log"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$FullLogPath = Resolve-Path (Join-Path $ScriptDir $LogPath) -ErrorAction SilentlyContinue

if ($FullLogPath -and (Test-Path $FullLogPath)) {
    $logSize = (Get-Item $FullLogPath).Length / 1KB
    Write-Status "Log file: $FullLogPath ({0:N1} KB)" "INFO"

    # Show last 5 lines
    Write-Host "`nLast 5 log entries:" -ForegroundColor Yellow
    Get-Content $FullLogPath -Tail 5 | ForEach-Object {
        Write-Host "  $_"
    }
} else {
    Write-Status "Log file not found" "WARNING"
}

# Check environment
Write-Host "`nEnvironment:" -ForegroundColor Yellow
$envVars = @("TELEGRAM_TOKEN", "ALLOWED_USER_ID", "ANTHROPIC_API_KEY")
foreach ($var in $envVars) {
    $value = [Environment]::GetEnvironmentVariable($var)
    if ($value) {
        $masked = if ($value.Length -gt 8) { $value.Substring(0, 4) + "****" + $value.Substring($value.Length - 4) } else { "****" }
        Write-Status "  $var = $masked" "SUCCESS"
    } else {
        Write-Status "  $var = NOT SET" "WARNING"
    }
}

Write-Host "`n========================================`n" -ForegroundColor Cyan
