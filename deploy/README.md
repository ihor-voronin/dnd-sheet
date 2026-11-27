# Деплой і секрети

Секрети для деплою (токен бота, id власника, а згодом адреса сервера й ключ
SSH) лежать у [`deploy/secrets/`](secrets/) і **шифруються git-crypt**:
у GitHub потрапляє лише шифр, розшифровує їх тільки той, чий ключ GPG
додано до репозиторію (`.git-crypt/keys/`).

## Що тут

| Файл | Що в ньому |
| --- | --- |
| `secrets/prod.env` | змінні `DNDSHEET_*` для продакшну — на сервері стає `.env` поруч з `docker-compose.yml` |
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

## Деплой на VPS (Terraform)

Сервер — VPS на RackNerd. API для Terraform у RackNerd немає, тож Terraform
не створює сервер, а доводить наявний до потрібного стану по SSH
([`terraform/main.tf`](terraform/main.tf)):

1. **bootstrap** — Docker з офіційного репозиторію, файрвол (22, 80, 443),
   swap 2 ГБ, щоденний бекап бази в `/opt/dndsheet/backups` (14 днів),
   вхід по SSH лише ключем;
2. **image** — образ збирається на цьому компʼютері (корпус довідника не в git)
   і їде на сервер через `docker save` / `docker load`;
3. **dns** — запис A `dnd.voronin.app` → IP сервера в Cloudflare
   ([`terraform/dns.tf`](terraform/dns.tf)), без проксі Cloudflare;
4. **app** — `compose.yml` з Caddy (сам отримує сертифікат Let's Encrypt і
   переводить HTTP на HTTPS; голий IP веде на домен), `.env` з
   `secrets/prod.env`, запуск і перевірка: застосунок healthy, HTTPS відповідає.

Кожен крок повторюється лише тоді, коли змінилося те, від чого він залежить:
новий образ, конфіг, `.env` чи скрипт сервера.

Локально, поза git (`deploy/local/`): доступи до панелі й сервера
(`racknerd.env`), токен Cloudflare (`cloudflare.env`), ключ деплою
(`ssh/id_ed25519`), стан Terraform і тимчасовий `image.tar`. Адреса сервера — у `terraform/terraform.tfvars` (теж поза git;
приклад — `terraform.tfvars.example`).

### Перший запуск

1. Додати ключ деплою на сервер — один раз, з паролем root:

   ```powershell
   Get-Content deploy\local\ssh\id_ed25519.pub | ssh root@<IP> "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
   ```

2. Перевірити, що ключ пускає без пароля:

   ```powershell
   ssh -i deploy\local\ssh\id_ed25519 root@<IP> "cat /etc/os-release | head -2"
   ```

3. Токен Cloudflare: dash.cloudflare.com → My Profile → API Tokens →
   Create Token → шаблон «Edit zone DNS», зона `voronin.app`; додати право
   Zone · Zone · Read. Вписати в `deploy/local/cloudflare.env`.

4. Деплой (Terraform покаже план і спитає `yes`):

   ```powershell
   .\deploy\terraform\deploy.ps1
   ```

Після першого деплою вхід паролем вимкнено — пароль root і панелі краще
змінити, бо вони передавалися відкрито.

### Далі

```powershell
.\deploy\terraform\deploy.ps1            # зібрати образ і оновити сервер
.\deploy\terraform\deploy.ps1 -NoBuild   # лише конфіг або .env
.\deploy\terraform\deploy.ps1 -Plan      # подивитися, що зміниться
```

Вхід «за іменем» на сервері вимкнений (`DNDSHEET_DEV_LOGIN=0`), тож без
бота на сайті доступні довідник і посилання «поділитися». Щоб увімкнути вхід
через Telegram: бот у @BotFather, там же `/setdomain` → `dnd.voronin.app`,
назва й токен бота в `secrets/prod.env` — і `deploy.ps1 -NoBuild`.

## Перед комітом

```powershell
git-crypt status -e    # список зашифрованих файлів; порожній «not encrypted» — добре
```

Секрет, який хоч раз потрапив у git відкритим, лишається в історії. Його не
шифрують заднім числом — його **замінюють** на новий.
