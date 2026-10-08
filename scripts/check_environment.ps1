#requires -Version 5.1
[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
$dbt = Join-Path $root ".venv\Scripts\dbt.exe"
if (-not (Test-Path $dbt)) { throw "Run .\scripts\setup.ps1 first." }
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    Write-Warning "No .env file. Configure Snowflake environment variables separately or create .env locally."
} else {
    Write-Host "[OK] Local .env file present (not loaded automatically)."
}
Write-Host "Checking dbt profile and Snowflake connection (read-only)..."
& $dbt debug
if ($LASTEXITCODE -ne 0) { throw "dbt debug failed: verify ~/.dbt/profiles.yml, role, account and credentials." }
Write-Host "[OK] dbt connection verified. No models executed."
