[CmdletBinding()]
param(
    [string]$SourceRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$BackupRoot = "E:\Lumira_Local_Backups"
)

$ErrorActionPreference = "Stop"
$source = (Resolve-Path $SourceRoot).Path
if (-not (Test-Path (Join-Path $source "ULTRON_COMPLETION_STATUS.md"))) {
    throw "SourceRoot does not look like the Lumira project: $source"
}

New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$destination = Join-Path $BackupRoot "personal_ai_core_$stamp"
New-Item -ItemType Directory -Path $destination -Force | Out-Null

Write-Host "Source:      $source"
Write-Host "Destination: $destination"

$robocopyArgs = @(
    $source, $destination,
    "/E", "/COPY:DAT", "/DCOPY:DAT", "/R:1", "/W:1",
    "/NP", "/NFL", "/NDL",
    "/XD", ".venv", "node_modules", ".pytest_cache", ".pytest-work", "__pycache__",
    "/XF", "*.pyc"
)
& robocopy @robocopyArgs
$copyExitCode = $LASTEXITCODE
if ($copyExitCode -ge 8) {
    throw "Robocopy failed with exit code $copyExitCode. Snapshot retained at $destination"
}

$criticalFiles = @(
    "ULTRON_COMPLETION_STATUS.md",
    "HANDOFF_CURRENT.md",
    "README.md",
    "requirements.txt",
    "final-audit-result.json",
    "app\main.py",
    "app\services\work_items\work_item_service.py",
    "tests\test_work_item_persistence.py",
    "app\services\memory\memory_service.py",
    "tests\test_memory_lifecycle.py",
    "app\services\workflow_recovery\run_recovery_service.py",
    "tests\test_run_recovery.py",
    "app\routes\command.py",
    "app\services\brain\brain_agent_orchestrator.py",
    "tests\test_brain_agent_orchestrator.py"
)
$hashResults = @()
foreach ($relativePath in $criticalFiles) {
    $sourceFile = Join-Path $source $relativePath
    $backupFile = Join-Path $destination $relativePath
    if (-not (Test-Path $sourceFile) -or -not (Test-Path $backupFile)) {
        throw "Backup verification file missing: $relativePath. Snapshot retained at $destination"
    }
    $sourceHash = (Get-FileHash $sourceFile -Algorithm SHA256).Hash
    $backupHash = (Get-FileHash $backupFile -Algorithm SHA256).Hash
    $matches = $sourceHash -eq $backupHash
    $hashResults += [pscustomobject]@{
        File = $relativePath
        Match = $matches
        SHA256 = $sourceHash
    }
    if (-not $matches) {
        throw "SHA-256 mismatch for $relativePath. Snapshot retained at $destination"
    }
}

$manifestPath = Join-Path $destination "BACKUP_MANIFEST.md"
$files = Get-ChildItem $destination -Recurse -File -Force
$sizeMB = [math]::Round((($files | Measure-Object Length -Sum).Sum) / 1MB, 2)
$hashLines = $hashResults | ForEach-Object { "- $($_.File): SHA-256 match" }
$manifest = @(
    "# Lumira Local Backup Manifest",
    "",
    "- Created: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')",
    "- Source: $source",
    "- Snapshot: $destination",
    "- Robocopy exit code: $copyExitCode (codes below 8 indicate success)",
    "- Snapshot files before this manifest: $($files.Count)",
    "- Approximate snapshot size before this manifest: $sizeMB MB",
    "- Verification: $($hashResults.Count)/$($hashResults.Count) critical-file SHA-256 checks passed",
    "- Excluded: .venv, node_modules, .pytest_cache, .pytest-work, __pycache__, *.pyc",
    "- No source files were deleted or changed by this script.",
    "",
    "## SHA-256 checks",
    "",
    $hashLines
)
Set-Content -Path $manifestPath -Value $manifest -Encoding UTF8

Write-Host "Backup verification: $($hashResults.Count)/$($hashResults.Count) critical files matched."
Write-Host "Snapshot: $destination"
Write-Host "Snapshot files: $($files.Count); approximate size: $sizeMB MB"
Write-Host "Robocopy exit code: $copyExitCode"
