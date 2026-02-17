# Claude Code Telegram Bot - Windows Stop Script

param(
    [switch]$Force
)

$ErrorActionPreference = "SilentlyContinue"

# Colors
$Green = "`e[32m"
$Red = "`e[31m"
$Yellow = "`e[33m"
$Reset = "`e[0m"

function Write-Status {
    param([string]$Message, [string]$Status = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    switch ($Status) {
        "SUCCESS" { Write-Host "${Green}[$timestamp] [OK] $Message${Reset}" }
        "ERROR" { Write-Host "${Red}[$timestamp] [ERROR] $Message${Reset}" }
        "WARNING" { Write-Host "${Yellow}[$timestamp] [WARN] $Message${Reset}" }
        default { Write-Host "[$timestamp] [INFO] $Message" }
    }
}

Write-Status "Stopping Claude Code Telegram Bot..."

$stopped = $false

# Check for background job first (new method)
$jobInfoPath = Join-Path $env:TEMP "claude_bot_job.json"
if (Test-Path $jobInfoPath) {
    try {
        $jobInfo = Get-Content $jobInfoPath | ConvertFrom-Json

        # Stop the background job
        $job = Get-Job -Id $jobInfo.JobId -ErrorAction SilentlyContinue
        if ($job) {
            Stop-Job -Id $jobInfo.JobId
            Remove-Job -Id $jobInfo.JobId
            Write-Status "Stopped background job (ID: $($jobInfo.JobId))"
            $stopped = $true
        }

        # Also stop the parent PowerShell process if it's still running
        $parentProcess = Get-Process -Id $jobInfo.ProcessId -ErrorAction SilentlyContinue
        if ($parentProcess) {
            Stop-Process -Id $jobInfo.ProcessId -Force
            Write-Status "Stopped parent process (PID: $($jobInfo.ProcessId))"
        }

        # Clean up job info file
        Remove-Item $jobInfoPath -Force
    } catch {
        Write-Status "Error stopping background job: $_" "WARNING"
    }
}

# Also check for old wrapper processes (backward compatibility)
$wrapperProcesses = Get-Process | Where-Object {
    $_.ProcessName -eq "powershell" -and
    $_.CommandLine -like "*claude_bot_wrapper*"
}

if ($wrapperProcesses) {
    foreach ($proc in $wrapperProcesses) {
        try {
            Stop-Process -Id $proc.Id -Force
            Write-Status "Stopped old wrapper process (PID: $($proc.Id))"
            $stopped = $true
        } catch {
            Write-Status "Failed to stop wrapper $($proc.Id): $_" "ERROR"
        }
    }
}

# Clean up old temp wrapper script (backward compatibility)
$oldWrapperPath = Join-Path $env:TEMP "claude_bot_wrapper.ps1"
if (Test-Path $oldWrapperPath) {
    Remove-Item $oldWrapperPath -Force
}

# Stop Python processes
$pythonProcesses = Get-Process | Where-Object {
    $_.ProcessName -like "*python*" -and
    $_.CommandLine -like "*main.py*"
}

if ($pythonProcesses) {
    foreach ($proc in $pythonProcesses) {
        try {
            if ($Force) {
                Stop-Process -Id $proc.Id -Force
                Write-Status "Force killed Python process (PID: $($proc.Id))"
            } else {
                # Try graceful shutdown first
                $proc.CloseMainWindow() | Out-Null
                Start-Sleep -Milliseconds 500
                if (-not $proc.HasExited) {
                    Stop-Process -Id $proc.Id -Force
                }
            }
            $stopped = $true
        } catch {
            Write-Status "Failed to stop process $($proc.Id): $_" "ERROR"
        }
    }
}

if ($stopped) {
    Write-Status "Bot stopped successfully" "SUCCESS"
} else {
    Write-Status "No bot processes found" "WARNING"
}
