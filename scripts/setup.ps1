#requires -Version 5.1
[CmdletBinding()]
param([string]$Python = "python", [switch]$SkipInstall)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
$venv = Join-Path $root ".venv"
$venvPython = Join-Path $venv "Scripts\python.exe"
$dbt = Join-Path $venv "Scripts\dbt.exe"
Write-Host "Inside Airbnb - Windows bootstrap (no Snowflake writes)"
if (-not (Test-Path $venvPython)) {
    & $Python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Unable to create virtual environment." }
}
if (-not $SkipInstall) {
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
    & $venvPython -m pip install -r (Join-Path $root "requirements-dev.txt")
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
}
& $venvPython -m pip check
if ($LASTEXITCODE -ne 0) { throw "Dependency conflicts in isolated environment." }
if (-not (Test-Path $dbt)) { throw "dbt not installed. Run setup without -SkipInstall." }
& $dbt --version
if ($LASTEXITCODE -ne 0) { throw "dbt startup failed." }
Write-Host "[OK] Isolated Python environment ready: $venv"
Write-Host "NEXT: Configure ~/.dbt/profiles.yml with your own Snowflake access."
Write-Host "NEXT: Run .\.venv\Scripts\dbt.exe debug (no data modification)."
Write-Host "NEXT: Run dbt build only after confirming target, role and warehouse."
Write-Host "NOTE: RAW datasets under data/raw are not included in Git."
Write-Host "NOTE: This script does not ingest data, deploy Streamlit or modify Snowflake."
