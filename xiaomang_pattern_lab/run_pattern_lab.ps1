[CmdletBinding()]
param(
    [switch]$SelfTest,
    [string]$Workspace = ""
)

# Compatibility wrapper: the normal entry no longer asks users for PythonPath.
& (Join-Path $PSScriptRoot "start_pattern_lab.ps1") -SelfTest:$SelfTest -Workspace $Workspace
exit $LASTEXITCODE
