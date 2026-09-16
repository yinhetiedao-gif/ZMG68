[CmdletBinding()]
param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",
    [string]$OutputRoot = "",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$labRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent $labRoot
$python = Join-Path $labRoot ".venv\Scripts\python.exe"
$pyinstallerRoot = Join-Path $projectRoot "build-tools\pyinstaller-local"
$spec = Join-Path $projectRoot "xiaomang_pattern_lab.spec"
# Node's production packages contain legitimately deep paths. Building below
# this long source checkout can exceed Win32's 260-character limit, so the
# default distributable goes to a short, user-visible Desktop folder.
if (-not $OutputRoot) {
    $OutputRoot = Join-Path ([Environment]::GetFolderPath("Desktop")) "XiaomangPatternLabBuild"
}
$distRoot = Join-Path $OutputRoot $Configuration.ToLowerInvariant()
$workRoot = Join-Path $labRoot ("build\" + $Configuration.ToLowerInvariant())

if (-not (Test-Path -LiteralPath $python)) { throw "缺少 Pattern Lab 项目运行时：$python" }
if (-not (Test-Path -LiteralPath $pyinstallerRoot)) { throw "缺少项目内 PyInstaller：$pyinstallerRoot" }
if (-not (Test-Path -LiteralPath $spec)) { throw "缺少打包规格文件：$spec" }

$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
if ($null -eq $nodeCommand -or -not (Test-Path -LiteralPath $nodeCommand.Source)) {
    throw "未找到 Node.js。当前 Raster→SVG 上游 MCP 需要随 EXE 打包的 node.exe。"
}

if (-not $SkipTests) {
    Push-Location -LiteralPath $projectRoot
    try {
        & $python -m unittest tests.test_noise_field_gate_q tests.test_pattern_lab tests.test_canvas_direct_manipulation -q
        if ($LASTEXITCODE -ne 0) { throw "打包前定向回归失败，已停止构建。" }
    } finally { Pop-Location }
}

$env:PYTHONPATH = "$pyinstallerRoot;$projectRoot\build-tools\vtracer-runtime;$projectRoot"
$env:XIAOMANG_NODE_EXE = (Resolve-Path -LiteralPath $nodeCommand.Source).Path
$env:XIAOMANG_BUILD_CONFIGURATION = $Configuration.ToLowerInvariant()

New-Item -ItemType Directory -Force -Path $distRoot, $workRoot | Out-Null
Push-Location -LiteralPath $projectRoot
try {
    & $python -m PyInstaller --noconfirm --clean --distpath $distRoot --workpath $workRoot $spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller 构建失败。" }
} finally {
    Pop-Location
    Remove-Item Env:XIAOMANG_NODE_EXE -ErrorAction SilentlyContinue
    Remove-Item Env:XIAOMANG_BUILD_CONFIGURATION -ErrorAction SilentlyContinue
}

$exe = Join-Path $distRoot "XiaomangPatternLab\XiaomangPatternLab.exe"
if (-not (Test-Path -LiteralPath $exe)) { throw "构建未生成预期 EXE：$exe" }
Write-Host "构建完成：$exe"
