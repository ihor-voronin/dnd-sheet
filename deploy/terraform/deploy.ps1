# Deploys dnd-sheet from Windows.
#
#   .\deploy.ps1                 # build the image and update the app (scripts/deploy_app.py)
#   .\deploy.ps1 -NoBuild        # without rebuilding the image (config or .env only)
#   .\deploy.ps1 -Infra          # infrastructure via Terraform: DNS, server setup
#   .\deploy.ps1 -Infra -Plan    # only show what Terraform would change
#   .\deploy.ps1 -Infra -AutoApprove
#
# After a merge into main, GitHub Actions deploys the app (.github/workflows/deploy.yml) —
# a manual run is for checking a branch or when CI is unavailable.
param(
    [switch]$NoBuild,
    [switch]$Infra,
    [switch]$Plan,
    [switch]$AutoApprove
)
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\..\.."

# The secrets must be unlocked: otherwise the state, the key and .env are all ciphertext.
$secrets = Join-Path $root "deploy\secrets"
foreach ($file in Get-ChildItem $secrets -Recurse -File | Where-Object Name -ne ".gitattributes") {
    $bytes = [System.IO.File]::ReadAllBytes($file.FullName) | Select-Object -First 9
    if ($bytes.Count -eq 9 -and [System.Text.Encoding]::ASCII.GetString($bytes) -eq "`0GITCRYPT") {
        throw "$($file.Name) is encrypted — run git-crypt unlock first (see docs/deploy.md)."
    }
}

if (-not $Infra) {
    $python = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $python) { throw "Python 3 is required in PATH" }
    $deployArgs = @((Join-Path $root "scripts\deploy_app.py"))
    if (-not $NoBuild) { $deployArgs += "--build" }
    & $python @deployArgs
    if ($LASTEXITCODE -ne 0) { throw "the app deploy failed" }
    return
}

# The Cloudflare token (for the DNS record) is encrypted, in deploy/secrets/cloudflare.env.
$cloudflareEnv = Join-Path $root "deploy\secrets\cloudflare.env"
foreach ($line in Get-Content $cloudflareEnv) {
    if ($line -match '^\s*([A-Z_]+)\s*=\s*(.*?)\s*$') {
        Set-Item -Path "Env:$($Matches[1])" -Value ($Matches[2].Trim("'`""))
    }
}
if (-not $env:CLOUDFLARE_API_TOKEN) {
    throw "CLOUDFLARE_API_TOKEN is missing from deploy/secrets/cloudflare.env (see docs/deploy.md)."
}

$terraform = (Get-Command terraform -ErrorAction SilentlyContinue).Source
if (-not $terraform) {
    $terraform = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter terraform.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $terraform) { throw "Terraform not found: winget install --id Hashicorp.Terraform -e" }

Push-Location $PSScriptRoot
try {
    & $terraform init -input=false | Out-Null
    $action = if ($Plan) { "plan" } else { "apply" }
    # An explicit array: `if` would unwrap a one-element array into a string.
    [string[]]$extra = @()
    if ($AutoApprove -and -not $Plan) { $extra += "-auto-approve" }
    & $terraform $action -var-file="..\secrets\terraform\terraform.tfvars" @extra
    if ($LASTEXITCODE -ne 0) { throw "terraform $action failed" }
} finally { Pop-Location }
