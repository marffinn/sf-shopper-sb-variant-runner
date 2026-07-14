@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_and_commit.ps1"
if %ERRORLEVEL% neq 0 (
    echo.
    echo Automation run failed with exit code %ERRORLEVEL%
    pause
)
