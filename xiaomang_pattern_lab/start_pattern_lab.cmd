@echo off
rem Xiaomang Pattern Lab only. No Python path or deprecated app fallback.
pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_pattern_lab.ps1" %*
exit /b %ERRORLEVEL%
