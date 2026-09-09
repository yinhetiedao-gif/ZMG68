@echo off
rem Xiaomang Pattern Lab only. This wrapper intentionally uses PowerShell 7,
rem avoiding the legacy Windows PowerShell parser and all legacy app launchers.
pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_pattern_lab.ps1" %*
exit /b %ERRORLEVEL%
