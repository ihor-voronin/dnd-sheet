# Деплой і секрети

> Повний опис — як влаштований деплой, кроки Terraform, сервер, бекапи,
> відновлення й діагностика: **[docs/deploy.md](../docs/deploy.md)**. Тут — коротко.

Секрети для деплою (токен бота, id власника, а згодом адреса сервера й ключ
SSH) лежать у [`deploy/secrets/`](secrets/) і **шифруються git-crypt**:
у GitHub потрапляє лише шифр, розшифровує їх тільки той, чий ключ GPG
додано до репозиторію (`.git-crypt/keys/`).

## Що тут

| Файл | Що в ньому |
| --- | --- |
| `secrets/prod.env` | змінні `DNDSHEET_*` для продакшну — на сервері стає `.env` поруч з `docker-compose.yml` |
| `secrets/racknerd.env` | панель VPS (SolusVM) і пароль root — для консолі в панелі; по SSH пароль не пускає |
| `secrets/cloudflare.env` | `CLOUDFLARE_API_TOKEN` — токен для запису DNS (зона `voronin.app`) |
| `secrets/ssh/id_ed25519` | ключ деплою: ним заходять на сервер Terraform, `deploy_app.py` і CI |
| `secrets/terraform/terraform.tfvars` | адреса сервера, домен, зона Cloudflare |
| `secrets/terraform/terraform.tfstate` | стан Terraform (лише інфраструктура: DNS, налаштування сервера) |
| `secrets/.gitattributes` | правило «шифрувати все в цій папці» (сам файл відкритий) |

Назви файлів **не** шифруються — лише вміст. Тож не називайте файли так,
щоб назва сама видавала секрет.

## Розблокувати (новий компʼютер або сервер)

Потрібні git-crypt і ключ GPG, доданий до репозиторію:

```powershell
winget install --id AGWA.git-crypt -e
git config gpg.program "C:/Program Files/GnuPG/bin/gpg.exe"   # Windows: GnuPG, де лежить ключ
git-crypt unlock
```

На Linux-сервері: `apt install git-crypt gnupg`, імпортувати ключ GPG
(`gpg --import`), потім `git-crypt unlock`.

Без розблокування файли в `secrets/` — двійковий шифр; решта репозиторію
працює як завжди.

## Додати людину чи сервер

```powershell
gpg --import їхній-публічний-ключ.asc
git-crypt add-gpg-user --trusted <відбиток ключа>
```

Команда сама робить коміт з ключем у `.git-crypt/keys/`. Забрати доступ
так просто не вийде: той, хто вже мав ключ, міг зберегти старі секрети —
тоді секрети треба замінити (новий токен у @BotFather тощо).

## Деплой

Застосунок деплоїть GitHub Actions після злиття в `main` ([docs/ci.md](../docs/ci.md));
вручну з Windows — `deploy\terraform\deploy.ps1`, інфраструктура —
`deploy.ps1 -Infra` ([docs/deploy.md](../docs/deploy.md)).

## Перед комітом

```powershell
git-crypt status -e    # список зашифрованих файлів; порожній «not encrypted» — добре
```

Секрет, який хоч раз потрапив у git відкритим, лишається в історії. Його не
шифрують заднім числом — його **замінюють** на новий.
