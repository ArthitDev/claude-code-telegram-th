# Claude Code Telegram Bot - Windows Production Deployment

## Quick Start

### 1. Initial Setup

```powershell
# Run setup script (PowerShell as Administrator recommended)
.\scripts\windows\setup_windows.ps1

# Or with options:
.\scripts\windows\setup_windows.ps1 -CreateService  # Install as Windows service
```

### 2. Configure Environment

Edit `.env` file in project root:

```env
# Required
TELEGRAM_TOKEN=your_bot_token_here
ALLOWED_USER_ID=your_telegram_user_id
ANTHROPIC_API_KEY=your_api_key_here

# Optional
CLAUDE_WORKING_DIR=C:\Users\YourName\projects
LOG_LEVEL=INFO
```

### 3. Start the Bot

**Option A: Using Shortcuts (Recommended)**
- Double-click `Start Bot.lnk` in project root

**Option B: Using PowerShell**
```powershell
.\scripts\windows\start_bot.ps1
```

**Option C: Using Batch File**
```cmd
.\scripts\windows\start_bot.bat
```

**Option D: Debug Mode (with console output)**
```powershell
.\scripts\windows\start_bot.ps1 -Debug
```

### 4. Manage the Bot

```powershell
# Check status
.\scripts\windows\check_bot.ps1

# Stop bot
.\scripts\windows\stop_bot.ps1

# Restart bot
.\scripts\windows\restart_bot.ps1

# Force stop (if normal stop doesn't work)
.\scripts\windows\stop_bot.ps1 -Force
```

## Windows Service Installation

To run the bot as a Windows service (runs automatically on startup):

```powershell
# Install as service
.\scripts\windows\setup_windows.ps1 -CreateService

# Manage service
Start-Service ClaudeCodeTelegramBot
Stop-Service ClaudeCodeTelegramBot
Restart-Service ClaudeCodeTelegramBot
Get-Service ClaudeCodeTelegramBot
```

## Directory Structure

```
claude-code-telegram/
├── scripts/windows/          # Windows management scripts
│   ├── setup_windows.ps1     # Initial setup
│   ├── start_bot.ps1         # Start bot (background)
│   ├── stop_bot.ps1          # Stop bot
│   ├── restart_bot.ps1       # Restart bot
│   ├── check_bot.ps1         # Check status
│   └── *.bat                 # Batch file wrappers
├── logs/                     # Log files
│   └── bot.log
├── data/                     # Database files
├── projects/                 # Default working directory
├── Start Bot.lnk             # Desktop shortcut (created by setup)
└── Stop Bot.lnk              # Desktop shortcut (created by setup)
```

## Troubleshooting

### Bot won't start

1. Check Python installation:
   ```powershell
   python --version  # Should be 3.11+
   ```

2. Check virtual environment:
   ```powershell
   .venv\Scripts\python.exe --version
   ```

3. Check logs:
   ```powershell
   Get-Content logs\bot.log -Tail 50
   ```

4. Verify environment variables:
   ```powershell
   Get-Content .env
   ```

### Windows-specific Issues

**Issue: `cd` command not working**
- Claude Code uses Bash commands by default
- On Windows, install Git Bash or use WSL
- Or use Windows-specific paths like `C:\path\to\dir`

**Issue: Unicode/Thai characters not displaying**
- Set console encoding to UTF-8:
  ```powershell
  chcp 65001
  ```

**Issue: Permission denied**
- Run PowerShell as Administrator
- Or adjust folder permissions:
  ```powershell
  icacls .\ /grant Users:F /T
  ```

### Network Issues

**Issue: Cannot connect to Telegram API**
- Check Windows Firewall settings
- Check proxy settings if behind corporate proxy
- Test connectivity:
  ```powershell
  Test-NetConnection -ComputerName api.telegram.org -Port 443
  ```

## Auto-Restart on Crash

The bot automatically restarts if it crashes:
- Edit `start_bot.ps1` and set `$AutoRestart = $true` (default)
- Logs are rotated automatically
- Check `logs/bot.log` for crash details

## Log Rotation

Logs are automatically rotated when they reach 10MB:
- `logs/bot.log` - Current log
- `logs/bot.log.1` - Previous log
- `logs/bot.log.2` - Older log (etc.)

## Windows-specific Configuration

### Environment Variables

Set system-wide environment variables:

```powershell
[Environment]::SetEnvironmentVariable("TELEGRAM_TOKEN", "your_token", "Machine")
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "your_key", "Machine")
```

### Firewall Rules

Allow Python through Windows Firewall:

```powershell
New-NetFirewallRule -DisplayName "Claude Bot" -Direction Inbound -Program ".venv\Scripts\python.exe" -Action Allow
```

### Task Scheduler (Alternative to Service)

Create a scheduled task to start bot on login:

```powershell
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-File C:\path\to\start_bot.ps1"
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "ClaudeCodeBot" -Action $Action -Trigger $Trigger -Settings $Settings
```

## Performance Tuning

### For Low-Memory Systems

Edit `start_bot.ps1` and add:
```powershell
$env:PYTHONOPTIMIZE = "2"
$env:PYTHONDONTWRITEBYTECODE = "1"
```

### For Better Network Performance

```powershell
# Increase TCP buffer sizes (run as Administrator)
netsh int tcp set global autotuninglevel=experimental
```

## Security Considerations

1. **Protect .env file**: Ensure `.env` is not readable by other users
2. **Use strong API keys**: Rotate keys regularly
3. **Limit ALLOWED_USER_ID**: Only authorize specific Telegram users
4. **Firewall**: Only allow necessary outbound connections
5. **Updates**: Keep Python and dependencies updated

## Support

For issues specific to Windows deployment:
1. Check logs in `logs/bot.log`
2. Run `check_bot.ps1` for diagnostics
3. Check Windows Event Viewer
4. Open an issue with Windows version and error details
