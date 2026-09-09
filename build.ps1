param([switch]$SkipTests)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = "C:\Users\13524\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$deps = Join-Path $root "build-tools\pyinstaller-local"
$vtracerRuntime = Join-Path $root "build-tools\vtracer-runtime"
$dist = Join-Path $root "dist\小芒造物"

if (-not (Test-Path $python)) { throw "未找到构建 Python。请设置 `$python 为可用 Python 路径。" }
if (-not $SkipTests) {
    & $python -m unittest discover -s (Join-Path $root "tests") -v
    if ($LASTEXITCODE -ne 0) { throw "自动测试失败，已停止打包。" }
}
if (-not (Test-Path (Join-Path $deps "PyInstaller"))) {
    & $python -m pip install --disable-pip-version-check --target $deps PyInstaller --timeout 15 --retries 1
    if ($LASTEXITCODE -ne 0) { throw "无法准备 PyInstaller。请检查网络，或将 PyInstaller 放入 build-tools\pyinstaller-local 后重试。" }
}
$env:PYTHONPATH = "$deps;$vtracerRuntime;$root"
& $python -m PyInstaller --noconfirm --clean --onefile --windowed --name "小芒造物" --paths $root --paths $vtracerRuntime --collect-all vtracer --add-data "$root\ppg\locales;ppg\locales" --distpath $dist --workpath (Join-Path $root "build") --specpath (Join-Path $root "build-spec") (Join-Path $root "main.py")
if ($LASTEXITCODE -ne 0) { throw "应用打包失败，未生成安装程序。" }
Write-Host "构建完成：$dist\小芒造物.exe"
