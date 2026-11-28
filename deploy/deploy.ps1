# Deploys dnd-sheet from Windows with vps-infra's deploy script (the same one CI runs).
#
#   .\deploy\deploy.ps1                 # build the image and deploy
#   .\deploy\deploy.ps1 -NoBuild        # deploy the dndsheet:local image as it is
#   .\deploy\deploy.ps1 -DryRun         # only print the steps
#   .\deploy\deploy.ps1 -VpsInfra D:\src\vps-infra   # where vps-infra is checked out
#
# After a merge into main, GitHub Actions deploys (.github/workflows/deploy.yml): a manual
# run is for checking a branch or when CI is unavailable. Infrastructure (DNS, server
# setup, the shared Caddy) is in vps-infra and changes only from there.
param(
    [switch]$NoBuild,
    [switch]$DryRun,
    [string]$VpsInfra = ""
)
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
if (-not $VpsInfra) { $VpsInfra = Join-Path $root "..\vps-infra" }
$script = Join-Path $VpsInfra "scripts\deploy_app.py"
if (-not (Test-Path $script)) {
    throw "vps-infra isn't at ${VpsInfra}: git clone https://github.com/ihor-voronin/vps-infra there or pass -VpsInfra"
}
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "Python 3 is required in PATH" }

if (-not $NoBuild -and -not $DryRun) {
    docker compose -f (Join-Path $root "docker-compose.yml") build app
    if ($LASTEXITCODE -ne 0) { throw "the image build failed" }
}
$deployArgs = @($script, "--root", $root, "--project", "deploy\project.toml")
if ($DryRun) { $deployArgs += "--dry-run" }
& $python @deployArgs
if ($LASTEXITCODE -ne 0) { throw "the deploy failed (see the lines above; a failed release is rolled back)" }
