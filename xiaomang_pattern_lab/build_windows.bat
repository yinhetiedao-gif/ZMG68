@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_pattern_lab.ps1" -Configuration Release
if errorlevel 1 pause
endlocal
