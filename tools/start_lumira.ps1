# Start Lumira's local backend and desktop workbench in separate PowerShell windows.
# This script does not install packages, change machine settings, or expose Lumira to the LAN.
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Desktop = Join-Path $Root "lumira_desktop"
$NodeModules = Join-Path $Desktop "node_modules"

if (-not (Test-Path $Python -PathType Leaf)) {
    throw "Lumira's virtual environment was not found at '$Python'. Create the project's .venv and install requirements before launching."
}
if (-not (Test-Path (Join-Path $Desktop "package.json") -PathType Leaf)) {
    throw "Desktop package.json was not found at '$Desktop'."
}
if (-not (Test-Path $NodeModules -PathType Container)) {
    throw "Desktop dependencies are missing. From the project root, run: npm ci --prefix lumira_desktop"
}

function Test-LoopbackService([int]$Port, [string]$Path, [string]$ExpectedMarker) {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port$Path" -TimeoutSec 2 -UseBasicParsing
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300 -and $response.Content -match $ExpectedMarker)
    } catch {
        return $false
    }
}

function Test-ListeningPort([int]$Port) {
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1)
}

$safeRoot = $Root.Replace("'", "''")
$safePython = $Python.Replace("'", "''")
$safeDesktop = $Desktop.Replace("'", "''")

if (Test-LoopbackService 8000 "/health" '"status"\s*:') {
    Write-Host "Lumira backend is already responding at http://127.0.0.1:8000"
} elseif (Test-ListeningPort 8000) {
    throw "Port 8000 is already occupied by a service that did not pass the Lumira health check. Close that service or inspect it before retrying."
} else {
    # Pin the launched backend to loopback even if the parent shell has HOST set to a LAN address.
    $backendCommand = "Set-Location -LiteralPath '$safeRoot'; `$env:HOST='127.0.0.1'; `$env:PORT='8000'; `$env:RELOAD='false'; & '$safePython' run.py"
    $encodedBackend = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($backendCommand))
    Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encodedBackend)
    Write-Host "Started Lumira backend in a new window."
}

if (Test-LoopbackService 5000 "/" 'id="root"') {
    Write-Host "Desktop workbench is already responding at http://127.0.0.1:5000"
} elseif (Test-ListeningPort 5000) {
    throw "Port 5000 is already occupied by a service that did not respond as expected. Inspect it before retrying."
} else {
    $desktopCommand = "Set-Location -LiteralPath '$safeDesktop'; npm run dev -- --host 127.0.0.1 --port 5000"
    $encodedDesktop = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($desktopCommand))
    Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encodedDesktop)
    Write-Host "Started Lumira desktop in a new window."
}

Write-Host ""
Write-Host "Open Lumira at: http://127.0.0.1:5000"
Write-Host "Keep both service windows open. The servers are bound to loopback only."
