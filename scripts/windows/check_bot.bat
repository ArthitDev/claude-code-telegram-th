@echo off
chcp 65001 >nul
title Claude Code Telegram Bot - Status Check
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "check_bot.ps1"
echo.
pause
