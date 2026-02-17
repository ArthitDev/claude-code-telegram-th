# Claude Code Telegram Bot - Interactive Menu Script
# รันเมนูจัดการ bot แบบเฟี้ยว ๆ

param(
    [switch]$Status,
    [switch]$Start,
    [switch]$Stop,
    [switch]$Restart,
    [switch]$Debug,
    [switch]$Logs
)

$ErrorActionPreference = "Stop"

# Get paths
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Resolve-Path (Join-Path $ScriptDir "..")
$VenvPath = Join-Path $ProjectDir ".venv"
if (-not (Test-Path $VenvPath)) {
    $VenvPath = Join-Path $ProjectDir "venv"
}

# Colors
$Colors = @{
    Reset = "`e[0m"
    Bold = "`e[1m"
    Dim = "`e[2m"
    Cyan = "`e[36m"
    Green = "`e[32m"
    Yellow = "`e[33m"
    Red = "`e[31m"
    Magenta = "`e[35m"
    Blue = "`e[34m"
    White = "`e[37m"
    BgCyan = "`e[46m"
    BgGreen = "`e[42m"
    BgRed = "`e[41m"
    BgYellow = "`e[43m"
}

# Icons
$Icons = @{
    Bot = "🤖"
    Play = "▶"
    Stop = "⏹"
    Restart = "🔄"
    Bug = "🐛"
    Log = "📋"
    Chart = "📊"
    Exit = "👋"
    Check = "✓"
    Cross = "✗"
    Warning = "⚠"
    Info = "ℹ"
    Clock = "⏱"
    Memory = "💾"
    Cpu = "⚡"
    Folder = "📁"
}

function Write-Color {
    param([string]$Text, [string]$Color = "Reset", [switch]$NoNewline)
    $output = "$($Colors[$Color])$Text$($Colors.Reset)"
    if ($NoNewline) { Write-Host $output -NoNewline } else { Write-Host $output }
}

function Write-Header {
    Clear-Host
    Write-Host ""
    Write-Color "  ╔══════════════════════════════════════════════════════════╗" "Cyan"
    Write-Color "  ║" "Cyan" -NoNewline
    Write-Color "           $($Icons.Bot) CLAUDE CODE TELEGRAM BOT" "White" -NoNewline
    Write-Color "             ║" "Cyan"
    Write-Color "  ╚══════════════════════════════════════════════════════════╝" "Cyan"
    Write-Host ""
}

function Get-BotStatus {
    $process = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*main.py*' } | Select-Object -First 1
    $jobInfoPath = Join-Path $env:TEMP "claude_bot_job.json"
    $isBackground = Test-Path $jobInfoPath

    if ($process) {
        $cpu = if ($process.CPU) { "{0:N1}" -f $process.CPU } else { "N/A" }
        $mem = "{0:N1}" -f ($process.WorkingSet64 / 1MB)
        $uptime = (Get-Date) - $process.StartTime
        $uptimeStr = "{0:hh\:mm\:ss}" -f $uptime

        return @{
            Running = $true
            IsBackground = $isBackground
            Pid = $process.Id
            Cpu = $cpu
            Memory = $mem
            Uptime = $uptimeStr
            StartTime = $process.StartTime.ToString('yyyy-MM-dd HH:mm:ss')
        }
    }
    return @{ Running = $false }
}

function Show-Status {
    Write-Header
    $botStatus = Get-BotStatus

    Write-Color "  📊 BOT STATUS" "Yellow"
    Write-Color "  ──────────────────────────────────────────────────────────" "Dim"
    Write-Host ""

    if ($botStatus.Running) {
        Write-Color "    $($Icons.Check) Status: " "Green" -NoNewline
        Write-Color "RUNNING" "Green"

        if ($botStatus.IsBackground) {
            Write-Color "    $($Icons.Check) Mode: " "Cyan" -NoNewline
            Write-Color "Background (Auto-restart enabled)" "Cyan"
        } else {
            Write-Color "    $($Icons.Info) Mode: " "Yellow" -NoNewline
            Write-Color "Foreground" "Yellow"
        }

        Write-Host ""
        Write-Color "    $($Icons.Clock) PID:        $($botStatus.Pid)" "White"
        Write-Color "    $($Icons.Clock) Started:    $($botStatus.StartTime)" "White"
        Write-Color "    $($Icons.Clock) Uptime:     $($botStatus.Uptime)" "White"
        Write-Color "    $($Icons.Cpu) CPU Time:   $($botStatus.Cpu)s" "White"
        Write-Color "    $($Icons.Memory) Memory:     $($botStatus.Memory) MB" "White"
    } else {
        Write-Color "    $($Icons.Cross) Status: " "Red" -NoNewline
        Write-Color "STOPPED" "Red"
    }

    Write-Host ""
    Write-Color "  ──────────────────────────────────────────────────────────" "Dim"
}

function Show-Menu {
    Write-Header
    $botStatus = Get-BotStatus

    # Status bar
    if ($botStatus.Running) {
        Write-Color "  [$($Icons.Check) RUNNING]" "Green" -NoNewline
        Write-Color " PID:$($botStatus.Pid) | $($botStatus.Memory)MB | $($botStatus.Uptime)" "Dim"
    } else {
        Write-Color "  [$($Icons.Cross) STOPPED]" "Red"
    }
    Write-Host ""

    # Menu items
    $menuItems = @(
        @{ Num = "1"; Icon = $Icons.Play; Color = "Green"; Text = "Start Bot"; Sub = "with auto-restart"; Disabled = $botStatus.Running },
        @{ Num = "2"; Icon = $Icons.Play; Color = "Yellow"; Text = "Start Bot"; Sub = "no auto-restart"; Disabled = $botStatus.Running },
        @{ Num = "3"; Icon = $Icons.Bug; Color = "Magenta"; Text = "Debug Mode"; Sub = "see output on screen"; Disabled = $botStatus.Running },
        @{ Num = "4"; Icon = $Icons.Play; Color = "Cyan"; Text = "Background"; Sub = "hidden window + auto-restart"; Disabled = $botStatus.Running },
        @{ Num = "5"; Icon = $Icons.Restart; Color = "Yellow"; Text = "Restart Bot"; Sub = "stop then start"; Disabled = -not $botStatus.Running },
        @{ Num = "6"; Icon = $Icons.Stop; Color = "Red"; Text = "Stop Bot"; Sub = "force stop"; Disabled = -not $botStatus.Running },
        @{ Num = "7"; Icon = $Icons.Chart; Color = "Blue"; Text = "Check Status"; Sub = "detailed info"; Disabled = $false },
        @{ Num = "8"; Icon = $Icons.Log; Color = "Cyan"; Text = "View Logs"; Sub = "tail -f"; Disabled = $false },
        @{ Num = "0"; Icon = $Icons.Exit; Color = "Red"; Text = "Exit"; Sub = ""; Disabled = $false }
    )

    Write-Color "  MENU OPTIONS:" "Yellow"
    Write-Color "  ──────────────────────────────────────────────────────────" "Dim"
    Write-Host ""

    foreach ($item in $menuItems) {
        $numColor = if ($item.Disabled) { "Dim" } else { $item.Color }
        $textColor = if ($item.Disabled) { "Dim" } else { "White" }
        $subColor = if ($item.Disabled) { "Dim" } else { "Dim" }

        $disabledMark = if ($item.Disabled) { " $($Icons.Warning) [RUNNING]" } else { "" }

        Write-Color "   [$($item.Num)]" $numColor -NoNewline
        Write-Color " $($item.Icon) " $item.Color -NoNewline
        Write-Color "$($item.Text.PadRight(12))" $textColor -NoNewline
        Write-Color "$($item.Sub)" $subColor -NoNewline
        Write-Color $disabledMark "Yellow"
    }

    Write-Host ""
    Write-Color "  ──────────────────────────────────────────────────────────" "Dim"
}

function Start-BotForeground {
    param([switch]$AutoRestart, [switch]$DebugMode)

    if (-not (Test-Path $VenvPath)) {
        Write-Color "  $($Icons.Cross) Virtual environment not found!" "Red"
        return
    }

    $pythonPath = Join-Path $VenvPath "Scripts\python.exe"
    Push-Location $ProjectDir

    try {
        if ($DebugMode) {
            Write-Color "  $($Icons.Bug) Starting in DEBUG mode..." "Magenta"
            Write-Color "  Press Ctrl+C to stop`n" "Dim"
            $env:DEBUG = 'true'
            & $pythonPath main.py
            Remove-Item Env:\DEBUG -ErrorAction SilentlyContinue
        }
        elseif ($AutoRestart) {
            Write-Color "  $($Icons.Play) Starting with auto-restart..." "Green"
            while ($true) {
                & $pythonPath main.py
                if ($LASTEXITCODE -eq 0) { break }
                Write-Color "  $($Icons.Warning) Bot crashed, restarting in 5 seconds..." "Yellow"
                Start-Sleep -Seconds 5
            }
        }
        else {
            Write-Color "  $($Icons.Play) Starting bot..." "Green"
            & $pythonPath main.py
        }
    } finally {
        Pop-Location
    }
}

function Start-BotBackground {
    $scriptPath = Join-Path $ScriptDir "start_bot.ps1"
    if (Test-Path $scriptPath) {
        Write-Color "  $($Icons.Play) Starting bot in background..." "Cyan"
        & $scriptPath
        Start-Sleep -Seconds 1
    } else {
        Write-Color "  $($Icons.Cross) start_bot.ps1 not found!" "Red"
    }
}

function Stop-Bot {
    $scriptPath = Join-Path $ScriptDir "stop_bot.ps1"
    if (Test-Path $scriptPath) {
        Write-Color "  $($Icons.Stop) Stopping bot..." "Red"
        & $scriptPath
    } else {
        # Fallback: kill process directly
        $process = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*main.py*' }
        if ($process) {
            $process | Stop-Process -Force
            Write-Color "  $($Icons.Check) Bot stopped!" "Green"
        } else {
            Write-Color "  $($Icons.Warning) Bot was not running." "Yellow"
        }
    }
}

function Show-Logs {
    $logPath = Join-Path $ProjectDir "logs\bot.log"
    if (Test-Path $logPath) {
        Write-Header
        Write-Color "  📋 LOGS (Press Ctrl+C to stop)" "Cyan"
        Write-Color "  ──────────────────────────────────────────────────────────" "Dim"
        Write-Host ""
        try {
            Get-Content $logPath -Wait -Tail 30
        } catch {
            # Ctrl+C pressed
        }
    } else {
        Write-Color "  $($Icons.Warning) No log file found at: $logPath" "Yellow"
        Start-Sleep -Seconds 2
    }
}

# Handle quick commands
if ($Status) { Show-Status; exit }
if ($Start) { Start-BotForeground -AutoRestart; exit }
if ($Stop) { Stop-Bot; exit }
if ($Restart) { Stop-Bot; Start-Sleep -Seconds 2; Start-BotForeground -AutoRestart; exit }
if ($Debug) { Start-BotForeground -DebugMode; exit }
if ($Logs) { Show-Logs; exit }

# Main menu loop
while ($true) {
    Show-Menu
    $choice = Read-Host "`n  Select option"

    switch ($choice) {
        '1' {
            $botStatus = Get-BotStatus
            if (-not $botStatus.Running) {
                Start-BotForeground -AutoRestart
                Write-Host ""
                Write-Color "  Press any key to continue..." "Dim"
                $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
            }
        }
        '2' {
            $botStatus = Get-BotStatus
            if (-not $botStatus.Running) {
                Start-BotForeground
                Write-Host ""
                Write-Color "  Press any key to continue..." "Dim"
                $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
            }
        }
        '3' {
            $botStatus = Get-BotStatus
            if (-not $botStatus.Running) {
                Start-BotForeground -DebugMode
                Write-Host ""
                Write-Color "  Press any key to continue..." "Dim"
                $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
            }
        }
        '4' {
            $botStatus = Get-BotStatus
            if (-not $botStatus.Running) {
                Start-BotBackground
                Start-Sleep -Seconds 2
            }
        }
        '5' {
            $botStatus = Get-BotStatus
            if ($botStatus.Running) {
                Stop-Bot
                Start-Sleep -Seconds 2
                Start-BotForeground -AutoRestart
                Write-Host ""
                Write-Color "  Press any key to continue..." "Dim"
                $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
            }
        }
        '6' {
            $botStatus = Get-BotStatus
            if ($botStatus.Running) {
                Stop-Bot
                Start-Sleep -Seconds 2
            }
        }
        '7' {
            Show-Status
            Write-Host ""
            Write-Color "  Press any key to continue..." "Dim"
            $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
        }
        '8' {
            Show-Logs
        }
        '0' {
            Clear-Host
            Write-Host ""
            Write-Color "  $($Icons.Exit) Goodbye! 👋" "Green"
            Write-Host ""
            exit 0
        }
        default {
            Write-Color "  $($Icons.Warning) Invalid option!" "Red"
            Start-Sleep -Seconds 1
        }
    }
}
