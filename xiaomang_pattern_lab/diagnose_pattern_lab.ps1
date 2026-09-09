[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "pattern_lab_runtime.ps1")

Write-Output "Project Root: $PatternLabProjectRoot"
Write-Output "Lab Root: $PatternLabRoot"
Write-Output "Entry Point: xiaomang_pattern_lab.main ($PatternLabRoot\main.py)"
Write-Output "Venv: $PatternLabVenv"
Write-Output "Venv Exists: $(Test-Path -LiteralPath $PatternLabVenvPython)"
Write-Output "Requirements: $(Join-Path $PatternLabRoot 'requirements.txt')"
Write-Output "Test Assets: $(Join-Path $PatternLabRoot 'fixtures')"
Write-Output "Test Assets Exist: $(Test-Path -LiteralPath (Join-Path $PatternLabRoot 'fixtures'))"
try {
    $probeDirectory = Join-Path $PatternLabRoot "work\diagnostics"
    New-Item -ItemType Directory -Force -Path $probeDirectory | Out-Null
    $probeFile = Join-Path $probeDirectory "write-probe.tmp"
    Set-Content -LiteralPath $probeFile -Value "ok"
    Remove-Item -LiteralPath $probeFile -Force
    Write-Output "Write Permission: OK"
}
catch { Write-Output "Write Permission: FAILED - $($_.Exception.Message)" }

Write-Output "Python Candidates:"
foreach ($candidate in Get-PatternLabPythonCandidates) {
    $result = Test-PatternLabPython -PythonPath $candidate
    Write-Output "  $($result.python) | Tk=$($result.ok) | Version=$($result.version)"
    if (-not $result.ok) { Write-Output "    $($result.error)" }
}
if (Test-Path -LiteralPath $PatternLabVenvPython) {
    $venvCheck = Test-PatternLabPython -PythonPath $PatternLabVenvPython
    Write-Output "Venv Tk: $($venvCheck.ok)"
}
Write-Output "Required Dependencies: Pillow"
if (Test-Path -LiteralPath $PatternLabLastError) {
    Write-Output "Last Launch Error:"
    Get-Content -LiteralPath $PatternLabLastError -Raw
}
else { Write-Output "Last Launch Error: (none)" }
exit 0
