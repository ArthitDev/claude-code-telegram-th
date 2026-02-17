@echo off
chcp 65001 >nul
title Claude Code Telegram Bot - Restarting
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "restart_bot.ps1" %*
echo.
pause
