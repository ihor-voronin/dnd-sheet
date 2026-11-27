# Деплой: сервер, Terraform і секрети

Сайт живе на **https://dnd.voronin.app** — VPS на RackNerd, домен у Cloudflare.
Усе, що потрібно для деплою, лежить у репозиторії: код Terraform — відкрито,
доступи й стан — зашифровані git-crypt. Деплой — одна команда з Windows:

```powershell
.\deploy\terraform\deploy.ps1
```

## Як це влаштовано

```
цей компʼютер                                   VPS (Ubuntu 24.04, 192.227.140.142)
─────────────                                   ─────────────────────────────────
docker compose build app  ──► dndsheet:local
        │
deploy.ps1 ─► terraform apply
                 ├─ cloudflare_dns_record ────► Cloudflare: dnd.voronin.app → IP (без проксі)
                 ├─ bootstrap  (SSH)  ────────► Docker, ufw, swap, бекапи, SSH лише ключем
                 ├─ image      (SSH)  ────────► docker load  ◄─ image.tar.gz (~90 МБ)
                 └─ app        (SSH)  ────────► /opt/dndsheet: compose.yml, Caddyfile, .env
                                                  ├─ caddy  :80/:443  (Let's Encrypt)
                                                  └─ app    :8000     (dndsheet:local)
```

**Чому Terraform, а не створення сервера через API.** У RackNerd немає API для
Terraform, тож сервер куплено вручну. Terraform доводить наявний сервер до
потрібного стану по SSH і керує записом DNS у Cloudflare. Кожен крок — ресурс
`terraform_data` з тригерами: він повторюється лише тоді, коли змінилося те,
від чого залежить.

| Крок | Повторюється, коли змінилось | Що робить |
| --- | --- | --- |
| `cloudflare_dns_record.site` | IP або домен | запис A `dnd.voronin.app` → IP, «сіра хмарка» (трафік прямо на сервер) |
| `terraform_data.bootstrap` | `files/bootstrap.sh` | Docker з офіційного репозиторію, ufw (22, 80, 443), swap 2 ГБ, щоденний бекап бази, `PasswordAuthentication no` |
| `terraform_data.image` | id локального образу | `docker save` + gzip тут → завантажити → `docker load` там |
| `terraform_data.app` | образ, `compose.yml`, `Caddyfile`, `.env` | покласти файли в `/opt/dndsheet`, `docker compose up -d`, дочекатись healthy і HTTPS |

**Чому образ збирається тут.** Корпус довідника (`content/compendium`,
`content/bestiary`) не в git — це тексти книг. Сервер не може зібрати образ з
GitHub, тому образ їде готовим, стиснутим (~90 МБ).

## Файли

| Шлях | Що це | У git |
| --- | --- | --- |
| `deploy/terraform/*.tf` | конфігурація Terraform | відкрито |
| `deploy/terraform/files/` | `bootstrap.sh`, `compose.yml`, `Caddyfile.tftpl`, `save-image.ps1` | відкрито (LF) |
| `deploy/terraform/deploy.ps1` | збірка образу + `terraform apply` | відкрито |
| `deploy/secrets/prod.env` | змінні застосунку → `.env` на сервері | шифр |
| `deploy/secrets/cloudflare.env` | `CLOUDFLARE_API_TOKEN` (DNS зони `voronin.app`) | шифр |
| `deploy/secrets/racknerd.env` | панель VPS і пароль root (для консолі в панелі) | шифр |
| `deploy/secrets/ssh/id_ed25519` | ключ, яким Terraform заходить на сервер | шифр |
| `deploy/secrets/terraform/terraform.tfvars` | IP, домен, зона | шифр |
| `deploy/secrets/terraform/terraform.tfstate` | стан Terraform | шифр |
| `deploy/local/image.tar.gz` | тимчасовий архів образу | ні (`.gitignore`) |

Шифрує все в `deploy/secrets/` правило `deploy/secrets/.gitattributes`. Назви
файлів видно, вміст — ні.

## Звичайний деплой

```powershell
.\deploy\terraform\deploy.ps1            # зібрати образ і оновити сервер
.\deploy\terraform\deploy.ps1 -NoBuild   # без перезбирання (змінився лише конфіг чи .env)
.\deploy\terraform\deploy.ps1 -Plan      # лише показати, що зміниться
.\deploy\terraform\deploy.ps1 -AutoApprove   # без питання «yes»
```

Скрипт:

1. відмовляється працювати, поки щось у `deploy/secrets/` зашифроване;
2. бере токен Cloudflare з `deploy/secrets/cloudflare.env`;
3. збирає `dndsheet:local` (`docker compose build app`), якщо немає `-NoBuild`;
4. передає Terraform id образу (`-var image_id=…`) і `terraform.tfvars`.

**Після деплою закомітьте стан** — інакше на іншому компʼютері Terraform
вирішить, що нічого ще не створено:

```powershell
git add deploy/secrets/terraform
git commit -m "Terraform state after deploy"
```

## Перший запуск на новому компʼютері

1. Інструменти: `winget install --id Hashicorp.Terraform -e`,
   `winget install --id AGWA.git-crypt -e`, Docker Desktop, GnuPG з вашим ключем.
2. Розблокувати секрети:

   ```powershell
   git config gpg.program "C:/Program Files/GnuPG/bin/gpg.exe"
   git-crypt unlock
   ```

   `gpg.program` потрібен, бо ключ лежить у GnuPG для Windows, а не в `gpg`
   з Git Bash.
3. `.\deploy\terraform\deploy.ps1 -Plan` — має показати «No changes» (стан з git
   збігається з сервером).

## Доступ до сервера

```powershell
ssh -i deploy\secrets\ssh\id_ed25519 root@192.227.140.142
```

Вхід паролем по SSH вимкнено. Якщо ключ втрачено — консоль VNC у панелі
RackNerd (доступи в `deploy/secrets/racknerd.env`), пароль root.

На Windows OpenSSH відмовляється від ключа з «чужими» правами — один раз:
`icacls deploy\secrets\ssh\id_ed25519 /inheritance:r /grant:r "$env:USERNAME:R"`.
На Linux — `chmod 600`.

На сервері:

| Що | Де |
| --- | --- |
| застосунок | `/opt/dndsheet` (`compose.yml`, `Caddyfile`, `.env`) |
| база | `/opt/dndsheet/var/dndsheet.sqlite3` |
| бекапи | `/opt/dndsheet/backups/dndsheet-РРРР-ММ-ДД.sqlite3`, 14 днів (`/etc/cron.daily/dndsheet-backup`) |
| журнали | `docker logs dndsheet-app`, `docker logs dndsheet-caddy` |

## Відновити базу з бекапу

```bash
cd /opt/dndsheet
docker compose -f compose.yml stop app
cp backups/dndsheet-2026-11-27.sqlite3 var/dndsheet.sqlite3
chown 10001:10001 var/dndsheet.sqlite3
docker compose -f compose.yml start app
```

## Домен і HTTPS

- DNS: Cloudflare, зона `voronin.app`, запис керується Terraform (`dns.tf`).
  Без проксі Cloudflare: сертифікат видає Let's Encrypt через Caddy (HTTP-01),
  і віджет Telegram бачить справжній домен.
- Caddy сам продовжує сертифікат; `http://` і голий IP переводить на
  `https://dnd.voronin.app`.
- Змінити домен: `domain` у `deploy/secrets/terraform/terraform.tfvars` →
  `deploy.ps1 -NoBuild`. Старий запис Terraform видалить сам.

## Вхід через Telegram і Mini App

Бот — `@DnD_Sheet_VoroninAppBot`; назва й токен — у `deploy/secrets/prod.env`
(`DNDSHEET_TELEGRAM_BOT`, `DNDSHEET_TELEGRAM_BOT_TOKEN`). Окремого сервера бота
немає: і віджет на сайті, і Mini App працюють без нього.

**На сайті** — віджет «Увійти через Telegram». У @BotFather: `/setdomain` →
`dnd.voronin.app`.

**У Telegram (Mini App)** — той самий сайт усередині Telegram:

- вхід без кнопки: Telegram передає підписаний `initData`, сервер перевіряє
  його (`POST /api/v1/auth/telegram-webapp`, ключ — HMAC «WebAppData» від
  токена бота) і повертає токен сесії. Той самий Telegram id — той самий
  гравець, персонажі спільні з сайтом;
- сесія їде заголовком `Authorization: Bearer …`: у Telegram у браузері сайт
  живе в iframe, куди cookie не доходять;
- тема — як у Telegram; кнопка «Назад» Telegram; свайп униз не закриває
  застосунок посеред листа;
- PDF качає сам Telegram (`downloadFile`), друк відкривається в браузері
  телефона — за посиланням з коротким токеном `?link=…` (5 хвилин, лише GET);
- «Поділитися» дає ще й `https://t.me/DnD_Sheet_VoroninAppBot?startapp=s_<токен>`
  — лист «лише читати» відкривається одразу в Telegram.

Скрипт Telegram (`telegram-web-app.js`) вантажиться лише тоді, коли сторінку
відкрив Telegram (див. `frontend/index.html`); звичайний сайт telegram.org не чіпає.

Налаштування в @BotFather (робить власник бота):

1. `/mybots` → бот → **Bot Settings → Configure Mini App → Enable Mini App** →
   URL `https://dnd.voronin.app` — у профілі бота зʼявиться кнопка «Open».
2. **Bot Settings → Menu Button** → URL `https://dnd.voronin.app`, текст
   «Лист персонажа» — кнопка біля поля повідомлення.
3. Посилання на застосунок: `https://t.me/DnD_Sheet_VoroninAppBot?startapp`.
4. Аватар бота: `/setuserpic` → бот → надіслати `branding/bot-avatar.png`
   (640×640, той самий кубик d20, що й іконка сайту; усі іконки генерує
   `scripts/make_icons.py`).

**Перевірити локально без Telegram**: `.claude/launch.json` → `miniapp-check`
(тестовий токен `123456:TEST-TOKEN`). Підписати `initData` тим самим токеном
(як у `backend/tests/identity/test_auth.py::_init_data`) і відкрити
`http://localhost:8021/?x=1#tgWebAppData=<initData>&tgWebAppVersion=8.0&tgWebAppPlatform=android`.

## Секрети

- **Додати людину** (щоб могла деплоїти): імпортувати її публічний ключ GPG і
  `git-crypt add-gpg-user --trusted <відбиток>` — команда сама комітить.
- **Відкликати** не вийде «назад у часі»: хто мав ключ, міг зберегти старі
  секрети. Тоді змініть їх: новий токен Cloudflare, новий ключ SSH (оновити
  `authorized_keys` на сервері), новий токен бота.
- **Перед комітом** — `git-crypt status -e`: усе в `deploy/secrets/` має бути
  `encrypted`.
- Секрет, що хоч раз потрапив у git відкритим, лишається в історії — його
  замінюють, а не шифрують заднім числом.

## Образ

| | Розмір |
| --- | --- |
| на диску сервера | ~270 МБ |
| архів для завантаження | ~90 МБ |

Що тримає розмір: python:3.12-slim (~120 МБ), WeasyPrint з fontTools (~60 МБ),
pango/harfbuzz і шрифт DejaVu для PDF (~25 МБ), корпус довідника (~46 МБ).
Python-залежності ставляться окремим етапом без `.pyc` і без вихідників
backend; uvicorn — без `[standard]`.

## Підводні камені (вже обійдені)

- **Провайдер `external` не бачить Docker Desktop** («permission denied … npipe»),
  а `local-exec` бачить. Тому id образу передає `deploy.ps1`, а не Terraform.
- **`cmd` ламає лапки** в шляхах `local-exec` на Windows — образ зберігає
  `files/save-image.ps1`, викликаний через `interpreter` без лапок.
- **PowerShell 5 читає `.ps1` без BOM як cp1251** — кирилиця ламає розбір.
  `save-image.ps1` збережений з BOM.
- **Файли для сервера мусять мати LF** — `deploy/terraform/files/.gitattributes`
  (`eol=lf`), а Terraform ще й прибирає `\r` перед завантаженням.

## Коли щось пішло не так

| Симптом | Де дивитись |
| --- | --- |
| `deploy.ps1`: «… зашифрований» | `git-crypt unlock` |
| `app: healthy` не дочекались | у виводі — останні 60 рядків `docker logs dndsheet-app`; найчастіше `.env` |
| `https: ще немає сертифіката` | `docker logs dndsheet-caddy`: запис DNS ще не поширився або закритий порт 80 |
| Terraform хоче все створити заново | стан не закомічений або не розблокований |
| SSH: `Permission denied (publickey)` | права на ключ (див. вище) або ключ не той |
