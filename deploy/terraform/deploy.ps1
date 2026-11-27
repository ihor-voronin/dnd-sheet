# Деплой dnd-sheet з Windows.
#
#   .\deploy.ps1                 # зібрати образ і оновити застосунок (scripts/deploy_app.py)
#   .\deploy.ps1 -NoBuild        # без перезбирання образу (лише конфіг або .env)
#   .\deploy.ps1 -Infra          # інфраструктура через Terraform: DNS, налаштування сервера
#   .\deploy.ps1 -Infra -Plan    # лише показати, що змінить Terraform
#   .\deploy.ps1 -Infra -AutoApprove
#
# Після злиття в main застосунок деплоїть GitHub Actions (.github/workflows/deploy.yml) —
# вручну це потрібно для перевірки гілки або коли CI недоступний.
param(
    [switch]$NoBuild,
    [switch]$Infra,
    [switch]$Plan,
    [switch]$AutoApprove
)
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\..\.."

# Секрети мають бути розблоковані: інакше там шифр — і стан, і ключ, і .env.
$secrets = Join-Path $root "deploy\secrets"
foreach ($file in Get-ChildItem $secrets -Recurse -File | Where-Object Name -ne ".gitattributes") {
    $bytes = [System.IO.File]::ReadAllBytes($file.FullName) | Select-Object -First 9
    if ($bytes.Count -eq 9 -and [System.Text.Encoding]::ASCII.GetString($bytes) -eq "`0GITCRYPT") {
        throw "$($file.Name) зашифрований — спершу git-crypt unlock (див. docs/deploy.md)."
    }
}

if (-not $Infra) {
    $python = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $python) { throw "Потрібен Python 3 у PATH" }
    $deployArgs = @((Join-Path $root "scripts\deploy_app.py"))
    if (-not $NoBuild) { $deployArgs += "--build" }
    & $python @deployArgs
    if ($LASTEXITCODE -ne 0) { throw "деплой застосунку не вдався" }
    return
}

# Токен Cloudflare (запис DNS) — зашифрований, у deploy/secrets/cloudflare.env.
$cloudflareEnv = Join-Path $root "deploy\secrets\cloudflare.env"
foreach ($line in Get-Content $cloudflareEnv) {
    if ($line -match '^\s*([A-Z_]+)\s*=\s*(.*?)\s*$') {
        Set-Item -Path "Env:$($Matches[1])" -Value ($Matches[2].Trim("'`""))
    }
}
if (-not $env:CLOUDFLARE_API_TOKEN) {
    throw "Немає CLOUDFLARE_API_TOKEN у deploy/secrets/cloudflare.env (див. docs/deploy.md)."
}

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
    # Масив явно: `if` розгорнув би масив з одного елемента в рядок.
    [string[]]$extra = @()
    if ($AutoApprove -and -not $Plan) { $extra += "-auto-approve" }
    & $terraform $action -var-file="..\secrets\terraform\terraform.tfvars" @extra
    if ($LASTEXITCODE -ne 0) { throw "terraform $action завершився з помилкою" }
} finally { Pop-Location }
