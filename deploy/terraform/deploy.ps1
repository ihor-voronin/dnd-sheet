# Деплой dnd-sheet на VPS: зібрати образ тут і передати його Terraform.
#
#   .\deploy.ps1            # зібрати образ і застосувати (Terraform покаже план і спитає)
#   .\deploy.ps1 -NoBuild   # без перезбирання образу (лише конфіг або .env)
#   .\deploy.ps1 -Plan      # лише показати, що зміниться
param(
    [switch]$NoBuild,
    [switch]$Plan
)
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\..\.."

# Секрети мають бути розблоковані: інакше prod.env — шифр, і на сервер поїде сміття.
$envFile = Join-Path $root "deploy\secrets\prod.env"
$head = [System.IO.File]::ReadAllBytes($envFile) | Select-Object -First 9
if ([System.Text.Encoding]::ASCII.GetString($head) -eq "`0GITCRYPT") {
    throw "deploy/secrets/prod.env зашифрований — спершу git-crypt unlock (див. deploy/README.md)."
}

# Токен Cloudflare (запис DNS) — лише локально, у deploy/local/cloudflare.env.
$cloudflareEnv = Join-Path $root "deploy\local\cloudflare.env"
if (Test-Path $cloudflareEnv) {
    foreach ($line in Get-Content $cloudflareEnv) {
        if ($line -match '^\s*([A-Z_]+)\s*=\s*(.*?)\s*$') {
            Set-Item -Path "Env:$($Matches[1])" -Value ($Matches[2].Trim("'`""))
        }
    }
}
if (-not $env:CLOUDFLARE_API_TOKEN) {
    throw "Немає CLOUDFLARE_API_TOKEN: впишіть токен у deploy/local/cloudflare.env (див. deploy/README.md)."
}

if (-not $NoBuild) {
    Push-Location $root
    try { docker compose build app } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "docker compose build app не вдався" }
}

$imageId = docker image inspect --format "{{.Id}}" dndsheet:local
if ($LASTEXITCODE -ne 0 -or -not $imageId) { throw "Немає образу dndsheet:local — запустіть без -NoBuild." }

$terraform = (Get-Command terraform -ErrorAction SilentlyContinue).Source
if (-not $terraform) {
    $terraform = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter terraform.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $terraform) { throw "Terraform не знайдено: winget install --id Hashicorp.Terraform -e" }

Push-Location $PSScriptRoot
try {
    & $terraform init -input=false | Out-Null
    $action = if ($Plan) { "plan" } else { "apply" }
    & $terraform $action -var "image_id=$imageId"
} finally { Pop-Location }
