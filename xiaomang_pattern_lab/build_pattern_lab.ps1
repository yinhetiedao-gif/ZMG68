[CmdletBinding()]
param(
    [switch]$SkipTests,
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
$labRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent $labRoot
$deps = Join-Path $projectRoot "build-tools\pyinstaller-local"
$runtime = Join-Path $projectRoot "build-tools\vtracer-runtime"
$dist = Join-Path $labRoot "dist\XiaomangPatternLab"
$work = Join-Path $labRoot "build"
$spec = Join-Path $labRoot "build-spec"

$runtimeConfig = Join-Path $labRoot "runtime-config.json"

function Resolve-PatternLabBuildPython {
    param([string]$RequestedPath)

    $configuredPath = ""
    if (Test-Path -LiteralPath $runtimeConfig) {
        try {
            $configuredPath = [string]((Get-Content -LiteralPath $runtimeConfig -Raw | ConvertFrom-Json).python_path)
        }
        catch {
            throw "Pattern Lab 运行时配置文件无效：$runtimeConfig。请重新运行 configure_pattern_lab_runtime.ps1。"
        }
    }
    [string[]]$candidates = @(
        $RequestedPath,
        $env:XIAOMANG_PATTERN_LAB_PYTHON,
        $configuredPath,
        (Join-Path $labRoot "runtime\python\python.exe"),
        (Join-Path $projectRoot "build-tools\pattern-lab-python\python.exe"),
        "C:\Users\13524\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

    if ($candidates.Count -eq 0) {
        throw "未找到用于构建的 Python。请先用 configure_pattern_lab_runtime.ps1 配置官方完整 Python。"
    }
    return (Resolve-Path -LiteralPath $candidates[0]).Path
}

$python = Resolve-PatternLabBuildPython -RequestedPath $PythonPath

Set-Location -LiteralPath $projectRoot
if (-not $SkipTests) {
    & $python -m unittest tests.test_faithful_mapping tests.test_foundation0 tests.test_canvas_direct_manipulation tests.test_grid_parametric tests.test_pattern_lab tests.test_pattern_lab_performance -v
    if ($LASTEXITCODE -ne 0) { throw "Pattern Lab 自动测试失败，已停止构建。" }
}

if (-not (Test-Path (Join-Path $deps "PyInstaller"))) {
    throw "缺少项目本地 PyInstaller：$deps。请准备该依赖后再构建。"
}

$env:PYTHONPATH = "$deps;$runtime;$projectRoot"
& $python -m PyInstaller --noconfirm --clean --onefile --windowed --name "XiaomangPatternLab" --paths $projectRoot --paths $runtime --collect-all tkinter --collect-all PIL --collect-all vtracer --add-data "$projectRoot\external;external" --distpath $dist --workpath $work --specpath $spec (Join-Path $labRoot "desktop_entry.py")
if ($LASTEXITCODE -ne 0) { throw "Xiaomang Pattern Lab 构建失败。" }

Write-Host "构建完成：$dist\XiaomangPatternLab.exe"
