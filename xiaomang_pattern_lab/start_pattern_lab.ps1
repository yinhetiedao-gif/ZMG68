[CmdletBinding()]
param(
    [switch]$SelfTest,
    [string]$Workspace = ""
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "pattern_lab_runtime.ps1")

try {
    $runtime = Ensure-PatternLabVenv
    Ensure-PatternLabDependencies -PythonPath $runtime.python
    Invoke-PatternLabImportSmokeTest -PythonPath $runtime.python
    if (-not $Workspace) { $Workspace = Join-Path $PatternLabProjectRoot "work\pattern_lab" }
    Push-Location -LiteralPath $PatternLabProjectRoot
    try {
        $arguments = @("-m", "xiaomang_pattern_lab.main", "--workspace", $Workspace)
        if ($SelfTest) { $arguments += "--self-test" }
        & $runtime.python @arguments
        if ($LASTEXITCODE -ne 0) { throw "Pattern Lab 进程异常退出，退出码：$LASTEXITCODE" }
    }
    finally { Pop-Location }
}
catch {
    $details = "小芒图案实验室启动失败。`r`n$($_.Exception.Message)"
    Write-PatternLabLastError $details
    Write-Error $details
    exit 1
}
