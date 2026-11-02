$ErrorActionPreference = 'Stop'
$source = 'C:\LumiraSource'
$workspace = 'C:\LumiraWorkspace'
if (Test-Path $workspace) { Remove-Item $workspace -Recurse -Force }
New-Item -ItemType Directory -Path $workspace | Out-Null
Copy-Item "$source\*" $workspace -Recurse -Force
Set-Location $workspace
Write-Host 'Lumira validation workspace created inside Windows Sandbox.' -ForegroundColor Green
Write-Host 'Source is mounted read-only. Networking is disabled.' -ForegroundColor Yellow
Write-Host 'Run only project-controlled validation commands in this guest workspace.' -ForegroundColor Cyan
