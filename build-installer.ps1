$ErrorActionPreference = "Stop"
$iscc = Get-Command iscc.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    $candidate = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
    if (Test-Path -LiteralPath $candidate) { $iscc = Get-Item -LiteralPath $candidate }
}
if (-not $iscc) { throw "未找到 Inno Setup。安装 Inno Setup 6 后重新运行本脚本。" }
& $PSScriptRoot\build.ps1
if ($LASTEXITCODE -ne 0) { throw "应用构建失败，已停止安装程序编译。" }
$isccPath = if ($iscc.PSObject.Properties.Name -contains "Source") { $iscc.Source } else { $iscc.FullName }
& $isccPath $PSScriptRoot\installer.iss
if ($LASTEXITCODE -ne 0) { throw "安装程序编译失败，未提供旧安装包。" }
$installer = Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot "installer-output") -Filter "小芒造物-安装程序-*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $installer) { throw "安装程序编译完成后未找到版本化安装包。" }
Write-Host "安装程序已生成：$($installer.FullName)"
