# Claude Code Telegram Bot - Windows Setup Script
# Run this script to set up the bot on Windows

param(
    [switch]$SkipVenv,
    [switch]$SkipDeps,
    [switch]$CreateService
)

$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Resolve-Path (Join-Path $ScriptDir "..\..")
$VenvPath = Join-Path $ProjectDir ".venv"

# Colors
$Green = "`e[32m"
$Red = "`e[31m"
$Yellow = "`e[33m"
$Cyan = "`e[36m"
$Reset = "`e[0m"

function Write-Status {
    param([string]$Message, [string]$Status = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    switch ($Status) {
        "SUCCESS" { Write-Host "${Green}[$timestamp] ✓ $Message${Reset}" }
        "ERROR" { Write-Host "${Red}[$timestamp] ✗ $Message${Reset}" }
        "WARNING" { Write-Host "${Yellow}[$timestamp] ⚠ $Message${Reset}" }
        "STEP" { Write-Host "${Cyan}[$timestamp] → $Message${Reset}" }
        default { Write-Host "[$timestamp] ℹ $Message" }
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Claude Code Telegram Bot Setup" -ForegroundColor Cyan
Write-Host "  Windows Production Environment" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check Python installation
Write-Status "Checking Python installation..." "STEP"
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
}

if (-not $pythonCmd) {
    Write-Status "Python not found! Please install Python 3.11 or higher." "ERROR"
    Write-Host "Download from: https://www.python.org/downloads/"
    exit 1
}

$pythonVersion = & $pythonCmd.Source --version 2>&1
Write-Status "Found: $pythonVersion" "SUCCESS"

# Check Python version (need 3.11+)
$versionString = $pythonVersion -replace "Python "
$major, $minor = $versionString.Split('.')[0,1]
if ([int]$major -lt 3 -or ([int]$major -eq 3 -and [int]$minor -lt 11)) {
    Write-Status "Python 3.11 or higher required!" "ERROR"
    exit 1
}

Set-Location $ProjectDir
Write-Status "Project directory: $ProjectDir" "INFO"

# Create virtual environment
if (-not $SkipVenv) {
    Write-Status "Creating virtual environment..." "STEP"
    if (Test-Path $VenvPath) {
        Write-Status "Virtual environment already exists, skipping..." "WARNING"
    } else {
        & $pythonCmd.Source -m venv $VenvPath
        Write-Status "Virtual environment created at $VenvPath" "SUCCESS"
    }
} else {
    Write-Status "Skipping virtual environment creation" "WARNING"
}

# Install dependencies
if (-not $SkipDeps) {
    Write-Status "Installing dependencies..." "STEP"

    $VenvPython = Join-Path $VenvPath "Scripts\python.exe"
    $VenvPip = Join-Path $VenvPath "Scripts\pip.exe"

    # Upgrade pip
    & $VenvPython -m pip install --upgrade pip

    # Install requirements
    $ReqFile = Join-Path $ProjectDir "requirements.txt"
    if (Test-Path $ReqFile) {
        & $VenvPip install -r $ReqFile
        Write-Status "Dependencies installed" "SUCCESS"
    } else {
        Write-Status "requirements.txt not found!" "ERROR"
        exit 1
    }

    # Check for claude-agent-sdk
    Write-Status "Checking claude-agent-sdk..." "STEP"
    $sdkCheck = & $VenvPython -c "import claude_agent_sdk; print('OK')" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Status "claude-agent-sdk not installed, attempting to install..." "WARNING"
        & $VenvPip install claude-agent-sdk
    } else {
        Write-Status "claude-agent-sdk is installed" "SUCCESS"
    }
} else {
    Write-Status "Skipping dependency installation" "WARNING"
}

# Create necessary directories
Write-Status "Creating directories..." "STEP"
$dirs = @("data", "logs", "projects")
foreach ($dir in $dirs) {
    $path = Join-Path $ProjectDir $dir
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
        Write-Status "Created directory: $dir"
    }
}

# Check .env file
Write-Status "Checking environment configuration..." "STEP"
$EnvFile = Join-Path $ProjectDir ".env"
$EnvExample = Join-Path $ProjectDir ".env.example"

if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Write-Status ".env file created from .env.example" "WARNING"
        Write-Host "`n⚠ IMPORTANT: Please edit $EnvFile and configure your settings!" -ForegroundColor Yellow
    } else {
        Write-Status ".env.example not found!" "ERROR"
    }
} else {
    Write-Status ".env file exists" "SUCCESS"
}

# Create Windows service (optional)
if ($CreateService) {
    Write-Status "Creating Windows service..." "STEP"

    $ServiceName = "ClaudeCodeTelegramBot"
    $ServiceDisplayName = "Claude Code Telegram Bot"
    $ServiceDescription = "Telegram bot for Claude Code integration"

    # Check if service exists
    $existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($existingService) {
        Write-Status "Service already exists, removing..." "WARNING"
        Stop-Service -Name $ServiceName -ErrorAction SilentlyContinue
        sc.exe delete $ServiceName | Out-Null
        Start-Sleep -Seconds 2
    }

    # Create service using NSSM (Non-Sucking Service Manager)
    $NssmPath = Join-Path $env:TEMP "nssm.exe"
    if (-not (Test-Path $NssmPath)) {
        Write-Status "Downloading NSSM..." "STEP"
        $NssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
        $NssmZip = Join-Path $env:TEMP "nssm.zip"

        Invoke-WebRequest -Uri $NssmUrl -OutFile $NssmZip
        Expand-Archive -Path $NssmZip -DestinationPath $env:TEMP -Force

        $arch = if ([Environment]::Is64BitOperatingSystem) { "win64" } else { "win32" }
        Copy-Item (Join-Path $env:TEMP "nssm-2.24\$arch\nssm.exe") $NssmPath -Force
    }

    $VenvPython = Join-Path $VenvPath "Scripts\python.exe"
    & $NssmPath install $ServiceName $VenvPython
    & $NssmPath set $ServiceName AppDirectory $ProjectDir
    & $NssmPath set $ServiceName AppParameters "main.py"
    & $NssmPath set $ServiceName DisplayName $ServiceDisplayName
    & $NssmPath set $ServiceName Description $ServiceDescription
    & $NssmPath set $ServiceName Start SERVICE_AUTO_START

    Write-Status "Windows service created: $ServiceName" "SUCCESS"
    Write-Status "Use: Start-Service $ServiceName" "INFO"
}

# Create shortcuts
Write-Status "Creating shortcuts..." "STEP"
$WshShell = New-Object -ComObject WScript.Shell

# Start shortcut
$StartShortcut = $WshShell.CreateShortcut((Join-Path $ProjectDir "Start Bot.lnk"))
$StartShortcut.TargetPath = "powershell.exe"
$StartShortcut.Arguments = "-ExecutionPolicy Bypass -File `"$ScriptDir\start_bot.ps1`""
$StartShortcut.WorkingDirectory = $ScriptDir
$StartShortcut.IconLocation = "%SystemRoot%\System32\shell32.dll, 138"
$StartShortcut.Save()

# Stop shortcut
$StopShortcut = $WshShell.CreateShortcut((Join-Path $ProjectDir "Stop Bot.lnk"))
$StopShortcut.TargetPath = "powershell.exe"
$StopShortcut.Arguments = "-ExecutionPolicy Bypass -File `"$ScriptDir\stop_bot.ps1`""
$StopShortcut.WorkingDirectory = $ScriptDir
$StopShortcut.IconLocation = "%SystemRoot%\System32\shell32.dll, 131"
$StopShortcut.Save()

Write-Status "Shortcuts created" "SUCCESS"

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Edit .env file with your configuration"
Write-Host "  2. Run 'Start Bot.lnk' or .\scripts\windows\start_bot.ps1"
Write-Host "  3. Check status with .\scripts\windows\check_bot.ps1"
Write-Host ""

if (-not $CreateService) {
    Write-Host "To install as Windows service, run:" -ForegroundColor Yellow
    Write-Host "  .\scripts\windows\setup_windows.ps1 -CreateService" -ForegroundColor Yellow
}
