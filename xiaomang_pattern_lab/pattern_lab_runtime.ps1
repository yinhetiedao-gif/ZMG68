# Shared, non-interactive runtime discovery for Xiaomang Pattern Lab.
# This file never changes PATH or registers a system-wide Python installation.

$PatternLabRoot = $PSScriptRoot
$PatternLabProjectRoot = Split-Path -Parent $PatternLabRoot
$PatternLabVenv = Join-Path $PatternLabRoot ".venv"
$PatternLabVenvPython = Join-Path $PatternLabVenv "Scripts\python.exe"
$PatternLabRuntimeConfig = Join-Path $PatternLabRoot "runtime-config.json"
$PatternLabDiagnosticDir = Join-Path $PatternLabRoot "work\diagnostics"
$PatternLabLastError = Join-Path $PatternLabDiagnosticDir "last-launch-error.txt"

function Write-PatternLabLastError {
    param([string]$Message)
    New-Item -ItemType Directory -Force -Path $PatternLabDiagnosticDir | Out-Null
    $stamp = (Get-Date).ToString("o")
    Set-Content -LiteralPath $PatternLabLastError -Encoding utf8 -Value "[$stamp]`r`n$Message"
}

function Get-PatternLabConfiguredPython {
    if (-not (Test-Path -LiteralPath $PatternLabRuntimeConfig)) { return "" }
    try {
        return [string]((Get-Content -LiteralPath $PatternLabRuntimeConfig -Raw | ConvertFrom-Json).python_path)
    }
    catch {
        Write-PatternLabLastError "运行时配置文件无效：$PatternLabRuntimeConfig`r`n$($_.Exception.Message)"
        return ""
    }
}

function Get-PatternLabPythonCandidates {
    $candidates = [System.Collections.Generic.List[string]]::new()
    foreach ($candidate in @(
        (Join-Path $PatternLabRoot ".runtime\python312-standalone\python\python.exe"),
        (Join-Path $PatternLabRoot ".runtime\python312\python.exe"),
        (Join-Path $PatternLabRoot ".runtime\python312-embed\python.exe"),
        (Join-Path $PatternLabProjectRoot "build-tools\pattern-lab-python\python.exe"),
        (Get-PatternLabConfiguredPython)
    )) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) { $candidates.Add((Resolve-Path -LiteralPath $candidate).Path) }
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            $fromLauncher = (& $pyLauncher.Source -3 -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1).Trim()
            if ($fromLauncher -and (Test-Path -LiteralPath $fromLauncher)) { $candidates.Add((Resolve-Path -LiteralPath $fromLauncher).Path) }
        }
        catch { }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notmatch "WindowsApps") {
        if (Test-Path -LiteralPath $pythonCommand.Source) { $candidates.Add((Resolve-Path -LiteralPath $pythonCommand.Source).Path) }
    }
    return @($candidates | Select-Object -Unique)
}

function Test-PatternLabPython {
    param([Parameter(Mandatory = $true)][string]$PythonPath, [switch]$RequirePillow)
    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
        return [pscustomobject]@{ ok = $false; python = $PythonPath; version = ""; error = "文件不存在" }
    }
    $probe = @'
import sys
try:
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    root.update_idletasks()
    root.destroy()
    import PIL
except Exception:
    import traceback
    traceback.print_exc()
    raise
print(sys.version.split()[0])
'@
    if (-not $RequirePillow) {
        $probe = $probe.Replace("    import PIL`n", "")
    }
    $output = & $PythonPath -c $probe 2>&1
    if ($LASTEXITCODE -ne 0) {
        return [pscustomobject]@{ ok = $false; python = $PythonPath; version = ""; error = ($output -join [Environment]::NewLine) }
    }
    $version = ($output | Select-Object -Last 1).ToString().Trim()
    return [pscustomobject]@{ ok = $true; python = (Resolve-Path -LiteralPath $PythonPath).Path; version = $version; error = "" }
}

function Resolve-PatternLabBasePython {
    $failures = [System.Collections.Generic.List[string]]::new()
    foreach ($candidate in Get-PatternLabPythonCandidates) {
        $result = Test-PatternLabPython -PythonPath $candidate
        if ($result.ok) { return $result }
        $failures.Add("$candidate`r`n$($result.error)")
    }
    $details = if ($failures.Count) { $failures -join "`r`n`r`n" } else { "未发现 py、PATH Python、项目运行时或已配置运行时。" }
    throw "未找到可用的 Python+Tk 运行时。`r`n$details"
}

function Ensure-PatternLabVenv {
    if (Test-Path -LiteralPath $PatternLabVenvPython) {
        $venvCheck = Test-PatternLabPython -PythonPath $PatternLabVenvPython
        if ($venvCheck.ok) { return $venvCheck }
    }
    $base = Resolve-PatternLabBasePython
    & $base.python -m venv --copies $PatternLabVenv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $PatternLabVenvPython)) {
        throw "无法建立项目独立虚拟环境：$PatternLabVenv"
    }
    $created = Test-PatternLabPython -PythonPath $PatternLabVenvPython
    if (-not $created.ok) { throw "已创建 .venv，但 Tcl/Tk 校验失败：`r`n$($created.error)" }
    return $created
}

function Ensure-PatternLabDependencies {
    param([Parameter(Mandatory = $true)][string]$PythonPath)
    $requirements = Join-Path $PatternLabRoot "requirements.txt"
    if (-not (Test-Path -LiteralPath $requirements)) { throw "缺少 Pattern Lab 依赖定义：$requirements" }
    & $PythonPath -c "import PIL" 2>$null
    if ($LASTEXITCODE -eq 0) { return }
    & $PythonPath -m pip install --disable-pip-version-check -r $requirements
    if ($LASTEXITCODE -ne 0) { throw "Pattern Lab 依赖安装失败。" }
    & $PythonPath -c "import PIL; print(PIL.__version__)"
    if ($LASTEXITCODE -ne 0) { throw "Pillow 安装后导入仍失败。" }
}

function Invoke-PatternLabImportSmokeTest {
    param([Parameter(Mandatory = $true)][string]$PythonPath)
    Push-Location -LiteralPath $PatternLabProjectRoot
    try {
        & $PythonPath -c "import PIL; import ppg.foundation; import ppg.integrations.imagetosvg; import xiaomang_pattern_lab.main; print('IMPORT_SMOKE=OK')"
        if ($LASTEXITCODE -ne 0) { throw "关键模块导入测试失败。" }
    }
    finally { Pop-Location }
}
