$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$stateFile = Join-Path $repo 'work/staging/processes.json'
if (-not (Test-Path -LiteralPath $stateFile)) { throw 'No staging process record exists.' }
$state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
if ($state.repo -ne $repo) { throw 'Staging record points to a different repository; refusing to stop processes.' }
$targets = @(
    @{ id = [int]$state.tunnel_pid; marker = "127.0.0.1:$($state.web_port)" },
    @{ id = [int]$state.web_pid; marker = "--port $($state.web_port)" },
    @{ id = [int]$state.api_pid; marker = "--port $($state.api_port)" }
)
foreach ($target in $targets) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($target.id)" -ErrorAction SilentlyContinue
    if (-not $process) { continue }
    if ($process.CommandLine -notlike "*$($target.marker)*") {
        throw "PID $($target.id) no longer matches this staging instance; refusing to stop it."
    }
    # Windows virtualenv launchers may keep the real Python as a child.
    # Only stop children that still have this exact parent and port marker.
    if ($target.id -eq [int]$state.api_pid) {
        $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($target.id)" -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -eq 'python.exe' })
        foreach ($child in $children) {
            if ($child.CommandLine -notlike "*$($target.marker)*") {
                throw "Python child PID $($child.ProcessId) does not match this staging instance."
            }
            Stop-Process -Id $child.ProcessId
        }
    }
    Stop-Process -Id $target.id
}
Remove-Item -LiteralPath $stateFile
Write-Output 'Staging processes stopped. Existing user services were untouched.'
