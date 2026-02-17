@echo off
chcp 65001 >nul
title Claude Code Telegram Bot

:: Colors
set "CYAN=[36m"
set "GREEN=[32m"
set "YELLOW=[33m"
set "RED=[31m"
set "RESET=[0m"

:: Get project root directory
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\.."
cd /d "%PROJECT_ROOT%"

:: Virtual environment path
set "VENV_PATH=%PROJECT_ROOT%\.venv"
if not exist "%VENV_PATH%\Scripts\activate.bat" (
    set "VENV_PATH=%PROJECT_ROOT%\venv"
)

:menu
cls
echo %CYAN%========================================%RESET%
echo    Claude Code Telegram Bot
echo %CYAN%========================================%RESET%
echo.
echo   %GREEN%[1]%RESET% Start Bot (with auto-restart)
echo   %GREEN%[2]%RESET% Start Bot (no auto-restart)
echo   %GREEN%[3]%RESET% Debug Mode (see output on screen)
echo   %CYAN%[4]%RESET% Start in Background (hidden, auto-restart)
echo   %CYAN%[5]%RESET% Start in Background (hidden, no auto-restart)
echo   %YELLOW%[6]%RESET% Restart Bot
echo   %YELLOW%[7]%RESET% Stop Bot
echo   %CYAN%[8]%RESET% Check Status
echo   %CYAN%[9]%RESET% View Logs
echo   %RED%[0]%RESET% Exit
echo.
echo %CYAN%========================================%RESET%
echo.

set /p choice="Select option [0-9]: "

if "%choice%"=="1" goto start_auto
if "%choice%"=="2" goto start_no_auto
if "%choice%"=="3" goto debug
if "%choice%"=="4" goto start_bg_auto
if "%choice%"=="5" goto start_bg_no_auto
if "%choice%"=="6" goto restart
if "%choice%"=="7" goto stop
if "%choice%"=="8" goto status
if "%choice%"=="9" goto logs
if "%choice%"=="0" goto exit

echo %RED%Invalid option!%RESET%
timeout /t 2 >nul
goto menu

:start_auto
cls
echo %GREEN%Starting bot with auto-restart...%RESET%
echo.
:: Run PowerShell in same window
powershell -ExecutionPolicy Bypass -Command "& {
    $venvPath = '%VENV_PATH%'
    $projectRoot = '%PROJECT_ROOT%'

    function Run-BotWithRestart {
        while ($true) {
            & '$venvPath\Scripts\python.exe' '$projectRoot\main.py'
            if ($LASTEXITCODE -eq 0) { break }
            Write-Host 'Bot crashed, restarting in 5 seconds...' -ForegroundColor Yellow
            Start-Sleep -Seconds 5
        }
    }

    Run-BotWithRestart
}"
echo.
echo %YELLOW%Bot stopped.%RESET%
pause
goto menu

:start_no_auto
cls
echo %GREEN%Starting bot without auto-restart...%RESET%
echo.
powershell -ExecutionPolicy Bypass -Command "& '%VENV_PATH%\Scripts\python.exe' '%PROJECT_ROOT%\main.py'"
echo.
echo %YELLOW%Bot stopped.%RESET%
pause
goto menu

:debug
cls
echo %YELLOW%Starting bot in DEBUG mode...%RESET%
echo Press Ctrl+C to stop
echo.
set "DEBUG=true"
powershell -ExecutionPolicy Bypass -Command "& { $env:DEBUG='true'; & '%VENV_PATH%\Scripts\python.exe' '%PROJECT_ROOT%\main.py' }"
echo.
echo %YELLOW%Debug session ended.%RESET%
pause
goto menu

:start_bg_auto
cls
echo %GREEN%Starting bot in background with auto-restart...%RESET%
echo.
powershell -ExecutionPolicy Bypass -Command "& '%~dp0start_bot.ps1'"
echo %GREEN%Bot started in background.%RESET%
echo.
pause
goto menu

:start_bg_no_auto
cls
echo %GREEN%Starting bot in background without auto-restart...%RESET%
echo.
powershell -ExecutionPolicy Bypass -Command "& '%~dp0start_bot.ps1' -NoAutoRestart"
echo %GREEN%Bot started in background.%RESET%
echo.
pause
goto menu

:restart
call :stop_bot
timeout /t 2 >nul
goto start_auto

:stop
call :stop_bot
pause
goto menu

:status
cls
echo %CYAN%Checking bot status...%RESET%
echo.
powershell -ExecutionPolicy Bypass -Command "& {
    $process = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*main.py*' }
    if ($process) {
        Write-Host 'Bot is RUNNING' -ForegroundColor Green
        $process | Select-Object Id, ProcessName, StartTime | Format-Table
    } else {
        Write-Host 'Bot is NOT RUNNING' -ForegroundColor Red
    }
}"
echo.
pause
goto menu

:logs
cls
echo %CYAN%Showing logs (Press Ctrl+C to stop, then any key to continue)...%RESET%
echo.
if exist "%PROJECT_ROOT%\logs\bot.log" (
    powershell -ExecutionPolicy Bypass -Command "& { Get-Content '%PROJECT_ROOT%\logs\bot.log' -Wait -Tail 30 }"
) else (
    echo %YELLOW%No log file found.%RESET%
    pause
)
goto menu

:exit
cls
echo %GREEN%Goodbye!%RESET%
timeout /t 1 >nul
exit /b 0

:: ============================================
:: Functions
:: ============================================

:stop_bot
cls
echo %RED%Stopping bot...%RESET%
powershell -ExecutionPolicy Bypass -Command "& {
    Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*main.py*' } | Stop-Process -Force
}"
echo %GREEN%Bot stopped!%RESET%
exit /b 0
