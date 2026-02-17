# Claude Code Telegram Bot - Windows Startup Script
# Run this script to start the bot in background with auto-restart

param(
    [switch]$Debug,
    [switch]$NoAutoRestart,
    [string]$LogPath = ""
)

$ErrorActionPreference = "Stop"

# Get script directory and project root (scripts/windows -> project root)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Resolve-Path (Join-Path $ScriptDir "..\..")
$VenvPath = Join-Path $ProjectDir ".venv"

# Set default log path if not provided
if ([string]::IsNullOrEmpty($LogPath)) {
    $LogPath = Join-Path $ProjectDir "logs\bot.log"
}

# Colors for output
$Green = "`e[32m"
$Red = "`e[31m"
$Yellow = "`e[33m"
$Reset = "`e[0m"

function Write-Status {
    param([string]$Message, [string]$Status = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    switch ($Status) {
        "SUCCESS" { Write-Host "$Green[$timestamp] [OK] $Message$Reset" }
        "ERROR" { Write-Host "$Red[$timestamp] [ERROR] $Message$Reset" }
        "WARNING" { Write-Host "$Yellow[$timestamp] [WARN] $Message$Reset" }
        default { Write-Host "[$timestamp] [INFO] $Message" }
    }
}

# Check if already running
$existingProcess = Get-Process | Where-Object {
    $_.ProcessName -like "*python*" -and
    $_.CommandLine -like "*main.py*"
}

if ($existingProcess) {
    Write-Status "Bot is already running (PID: $($existingProcess.Id))" "WARNING"
    Write-Host "Use stop_bot.ps1 to stop the existing instance first."
    exit 1
}

# Create logs directory
$LogDir = Split-Path -Parent $LogPath
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    Write-Status "Created logs directory: $LogDir"
}

# Check virtual environment
if (-not (Test-Path $VenvPath)) {
    Write-Status "Virtual environment not found at $VenvPath" "ERROR"
    Write-Host "Please run setup_windows.ps1 first to set up the environment."
    exit 1
}

# Activate virtual environment
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Status "Python not found in virtual environment" "ERROR"
    exit 1
}

Write-Status "Using Python: $VenvPython"

# Set environment variables for Windows
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"

# Change to project directory
Set-Location $ProjectDir
Write-Status "Working directory: $ProjectDir"

# Start bot
if ($Debug) {
    Write-Status "Starting bot in DEBUG mode..."
    $env:DEBUG = "true"
    & $VenvPython main.py
} else {
    if ($NoAutoRestart) {
        Write-Status "Starting bot in background mode (no auto-restart)..."
        $process = Start-Process -FilePath $VenvPython -ArgumentList "main.py" `
            -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $LogPath `
            -RedirectStandardError (Join-Path $LogDir "bot_error.log")

        Write-Status "Bot started with PID: $($process.Id)" "SUCCESS"
        Write-Status "Logs: $LogPath"
    } else {
        Write-Status "Starting bot with auto-restart..."

        # Create auto-restart script block as a job
        $jobScript = {
            param($VenvPython, $ProjectDir, $LogPath, $LogDir)

            # Set location to project directory
            Set-Location $ProjectDir

            # Set environment variables
            $env:PYTHONIOENCODING = "utf-8"
            $env:PYTHONUNBUFFERED = "1"

            while ($true) {
                $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
                Add-Content -Path $LogPath -Value "$timestamp [WRAPPER] Starting bot..."

                $psi = New-Object System.Diagnostics.ProcessStartInfo
                $psi.FileName = $VenvPython
                $psi.Arguments = "main.py"
                $psi.WorkingDirectory = $ProjectDir
                $psi.UseShellExecute = $false
                $psi.CreateNoWindow = $true
                $psi.RedirectStandardOutput = $true
                $psi.RedirectStandardError = $true

                $process = New-Object System.Diagnostics.Process
                $process.StartInfo = $psi
                $process.Start() | Out-Null

                # Read output and error streams
                $stdout = $process.StandardOutput.ReadToEndAsync()
                $stderr = $process.StandardError.ReadToEndAsync()

                $process.WaitForExit()
                $exitCode = $process.ExitCode

                # Write output to log
                $stdout.Result | Out-File -FilePath $LogPath -Append -Encoding UTF8
                $stderr.Result | Out-File -FilePath (Join-Path $LogDir "bot_error.log") -Append -Encoding UTF8

                $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

                if ($exitCode -eq 0) {
                    Add-Content -Path $LogPath -Value "$timestamp [WRAPPER] Bot exited normally"
                    break
                } else {
                    Add-Content -Path $LogPath -Value "$timestamp [WRAPPER] Bot crashed with exit code $exitCode, restarting in 5 seconds..."
                    Start-Sleep -Seconds 5
                }
            }
        }

        # Start the job
        $job = Start-Job -ScriptBlock $jobScript -ArgumentList $VenvPython, $ProjectDir, $LogPath, $LogDir

        # Save job info for stop_bot.ps1
        $jobInfo = @{
            JobId = $job.Id
            ProcessId = $PID
            StartTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
            LogPath = $LogPath
        } | ConvertTo-Json

        $jobInfoPath = Join-Path $env:TEMP "claude_bot_job.json"
        $jobInfo | Out-File -FilePath $jobInfoPath -Encoding UTF8

        Write-Status "Bot started with auto-restart (Job ID: $($job.Id))" "SUCCESS"
        Write-Status "Logs: $LogPath"
        Write-Status "Use stop_bot.ps1 to stop the bot"
    }
}
