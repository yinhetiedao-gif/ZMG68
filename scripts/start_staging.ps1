param(
    [string]$PythonExe = 'python',
    [string]$CloudflaredExe = 'cloudflared',
    [int]$ApiPort = 8766,
    [int]$WebPort = 5175
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$web = Join-Path $repo 'web'
$runtime = Join-Path $repo 'work/staging'
$stateFile = Join-Path $runtime 'processes.json'
if (Test-Path -LiteralPath $stateFile) { throw "Staging state already exists: $stateFile. Stop or inspect that instance first." }
foreach ($port in @($ApiPort, $WebPort)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use; choose another staging port."
    }
}
$python = (Get-Command $PythonExe -ErrorAction Stop).Source
$cloudflared = (Get-Command $CloudflaredExe -ErrorAction Stop).Source
$node = (Get-Command node -ErrorAction Stop).Source
$npm = (Get-Command npm.cmd -ErrorAction Stop).Source
$vite = Join-Path $web 'node_modules/vite/bin/vite.js'
if (-not (Test-Path -LiteralPath $vite)) { throw 'Install web dependencies first: npm ci in web/.' }
New-Item -ItemType Directory -Path $runtime -Force | Out-Null

$env:VITE_API_BASE_URL = ''
Push-Location $web
try {
    & $npm run build -- --mode staging
    if ($LASTEXITCODE -ne 0) { throw 'Staging web build failed.' }
} finally { Pop-Location }

$env:XIAOMANG_STAGING = '1'
$env:XIAOMANG_DEV_MANUFACTURING_SNAPSHOTS = '0'
$env:XIAOMANG_STAGING_API_TARGET = "http://127.0.0.1:$ApiPort"
$processes = @()
try {
    $api = Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'xiaomang_pattern_lab.web.app:create_app', '--factory', '--host', '127.0.0.1', '--port', "$ApiPort") -WorkingDirectory $repo -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'api.out.log') -RedirectStandardError (Join-Path $runtime 'api.err.log')
    $processes += $api
    $front = Start-Process -FilePath $node -ArgumentList @($vite, 'preview', '--host', '127.0.0.1', '--port', "$WebPort", '--strictPort') -WorkingDirectory $web -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'web.out.log') -RedirectStandardError (Join-Path $runtime 'web.err.log')
    $processes += $front
    $ready = $false
    for ($n = 0; $n -lt 30; $n++) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$WebPort/api/v1/health" -TimeoutSec 2 -NoProxy
            if ($health.status -eq 'ok') { $ready = $true; break }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready) { throw 'Same-origin /api health check failed. Inspect work/staging logs.' }
    $tunnel = Start-Process -FilePath $cloudflared -ArgumentList @('tunnel', '--url', "http://127.0.0.1:$WebPort", '--no-autoupdate') -WorkingDirectory $repo -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'tunnel.out.log') -RedirectStandardError (Join-Path $runtime 'tunnel.err.log')
    $processes += $tunnel
    $state = [pscustomobject]@{ repo = $repo; api_port = $ApiPort; web_port = $WebPort; api_pid = $api.Id; web_pid = $front.Id; tunnel_pid = $tunnel.Id }
    $state | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding UTF8
    $url = $null
    for ($n = 0; $n -lt 60; $n++) {
        $logs = (Get-Content -LiteralPath (Join-Path $runtime 'tunnel.err.log') -Raw -ErrorAction SilentlyContinue) + (Get-Content -LiteralPath (Join-Path $runtime 'tunnel.out.log') -Raw -ErrorAction SilentlyContinue)
        if ($logs -match 'https://[a-z0-9-]+\.trycloudflare\.com') { $url = $Matches[0]; break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $url) { throw 'Tunnel URL was not issued. Inspect work/staging/tunnel.err.log.' }
    Write-Output "Public staging URL: $url"
    Write-Output "Stop: & '$PSScriptRoot/stop_staging.ps1'"
} catch {
    foreach ($process in $processes) { if (-not $process.HasExited) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue } }
    if (Test-Path -LiteralPath $stateFile) { Remove-Item -LiteralPath $stateFile }
    throw
}
