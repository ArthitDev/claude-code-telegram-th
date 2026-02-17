@echo off
chcp 65001 >nul
title Claude Code Telegram Bot - Stopping
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "stop_bot.ps1" %*
echo.
pause
