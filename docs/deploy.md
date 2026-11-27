# Деплой: сервер, Terraform, CI і секрети

Сайт живе на **https://dnd.voronin.app** — VPS на RackNerd, домен у Cloudflare.
Усе, що потрібно для деплою, лежить у репозиторії: код — відкрито, доступи,
стан Terraform і корпус книг — зашифровані git-crypt.

- **Звичайно** деплоїть GitHub Actions: злиття PR у `main` → CI зелений →
  `deploy.yml` (див. [docs/ci.md](ci.md)).
- **Вручну з Windows** — та сама логіка однією командою:

```powershell
.\deploy\terraform\deploy.ps1
```

## Як це влаштовано

Дві частини, що змінюються з різною частотою:

```
ЗАСТОСУНОК — з кожним злиттям у main             VPS (Ubuntu 24.04, 192.227.140.142)
GitHub Actions (deploy.yml) або deploy.ps1        ─────────────────────────────────
  docker build (runtime)  ──► dndsheet:local
  scripts/deploy_app.py (SSH)
     ├─ образ: docker save + gzip ──────────────► docker load (якщо id новий)
     └─ compose.yml, Caddyfile, .env ───────────► /opt/dndsheet → docker compose up -d
                                                    ├─ caddy  :80/:443  (Let's Encrypt)
                                                    └─ app    :8000     (dndsheet:local)

ІНФРАСТРУКТУРА — рідко, вручну
deploy.ps1 -Infra ─► terraform apply
  ├─ cloudflare_dns_record ─────────────────────► Cloudflare: dnd.voronin.app → IP (без проксі)
  └─ bootstrap (SSH) ───────────────────────────► Docker, ufw, swap, бекапи, SSH лише ключем
```

**Застосунок — `scripts/deploy_app.py`.** Без стану: кожен запуск доводить
сервер до того, що в репозиторії. Образ вантажиться лише коли його id
змінився (id останнього лежить у `/opt/dndsheet/IMAGE_ID`), Caddy перечитує
конфіг, скрипт чекає, поки застосунок стане healthy і HTTPS відповість. Той
самий скрипт запускає і CI (Linux), і `deploy.ps1` (Windows).

**Інфраструктура — Terraform.** У RackNerd немає API для Terraform, тож сервер
куплено вручну; Terraform доводить його до потрібного стану по SSH і керує
записом DNS у Cloudflare. Кожен крок повторюється лише тоді, коли змінилось те,
від чого він залежить:

| Крок | Повторюється, коли змінилось | Що робить |
| --- | --- | --- |
| `cloudflare_dns_record.site` | IP або домен | запис A `dnd.voronin.app` → IP, «сіра хмарка» (трафік прямо на сервер) |
| `terraform_data.bootstrap` | `files/bootstrap.sh` | Docker з офіційного репозиторію, ufw (22, 80, 443), swap 2 ГБ, щоденний бекап бази, `PasswordAuthentication no` |

**Чому застосунок не в Terraform.** Колись був — але стан Terraform мусив би
після кожного деплою з CI комітитись назад у захищену гілку `main`. Скрипт без
стану цього не потребує.

**Чому образ збирається не на сервері.** Корпус довідника (`content/compendium`,
`bestiary`, `index`) — тексти книг: у git він лише зашифрований. Розблокувати
його вміє CI (секрет `GIT_CRYPT_KEY`) і ваш компʼютер, а не сервер.

## Файли

| Шлях | Що це | У git |
| --- | --- | --- |
| `scripts/deploy_app.py` | деплой застосунку (CI і Windows) | відкрито |
| `deploy/terraform/*.tf` | інфраструктура: DNS, налаштування сервера | відкрито |
| `deploy/terraform/files/` | `bootstrap.sh`, `compose.yml`, `Caddyfile.tftpl` | відкрито (LF) |
| `deploy/terraform/deploy.ps1` | вхід з Windows: застосунок або `-Infra` | відкрито |
| `.github/workflows/` | CI і деплой (docs/ci.md) | відкрито |
| `deploy/secrets/prod.env` | змінні застосунку → `.env` на сервері | шифр |
| `deploy/secrets/cloudflare.env` | `CLOUDFLARE_API_TOKEN` (DNS зони `voronin.app`) | шифр |
| `deploy/secrets/racknerd.env` | панель VPS і пароль root (для консолі в панелі) | шифр |
| `deploy/secrets/ssh/id_ed25519` | ключ, яким заходять на сервер | шифр |
| `deploy/secrets/terraform/terraform.tfvars` | IP, домен, зона | шифр |
| `deploy/secrets/terraform/terraform.tfstate` | стан Terraform (лише інфраструктура) | шифр |
| `content/compendium`, `bestiary`, `index` | корпус довідника (тексти книг) | шифр |
| `deploy/local/` | тимчасове: ключ git-crypt для секрету GitHub | ні (`.gitignore`) |

Шифрують правила `.gitattributes` у `deploy/secrets/` і в папках корпусу. Назви
файлів видно, вміст — ні. Хук `secrets-encrypted` (pre-commit і CI) перевіряє,
що в індексі все це справді шифр.

## Звичайний деплой

Через PR: злили в `main` → CI → деплой сам. Вручну з Windows:

```powershell
.\deploy\terraform\deploy.ps1                # зібрати образ і оновити застосунок
.\deploy\terraform\deploy.ps1 -NoBuild       # без перезбирання (змінився лише конфіг чи .env)
.\deploy\terraform\deploy.ps1 -Infra -Plan   # що змінить Terraform
.\deploy\terraform\deploy.ps1 -Infra         # застосувати інфраструктуру (спитає «yes»)
```

`deploy.ps1` відмовляється працювати, поки щось у `deploy/secrets/` зашифроване.

**Після `-Infra` закомітьте стан** — інакше на іншому компʼютері Terraform
вирішить, що нічого ще не створено:

```powershell
git add deploy/secrets/terraform
git commit -m "Terraform state after infra change"
```

## Перший запуск на новому компʼютері

1. Інструменти: `winget install --id Hashicorp.Terraform -e`,
   `winget install --id AGWA.git-crypt -e`, Docker Desktop, Python 3, GnuPG з
   вашим ключем.
2. Розблокувати секрети й корпус:

   ```powershell
   git config gpg.program "C:/Program Files/GnuPG/bin/gpg.exe"
   git-crypt unlock
   ```

   `gpg.program` потрібен, бо ключ лежить у GnuPG для Windows, а не в `gpg`
   з Git Bash.
3. `.\deploy\terraform\deploy.ps1 -Infra -Plan` — має показати «No changes».

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

- **Terraform `local-exec` на Windows**: провайдер `external` не бачить Docker
  Desktop, а `cmd` ламає лапки в шляхах. Через це образ і застосунок пішли з
  Terraform у `scripts/deploy_app.py` (Python однаково працює на Windows і в CI).
- **PowerShell 5 читає `.ps1` без BOM як cp1251** — кирилиця ламає розбір;
  хук `fix-byte-order-marker` не чіпає `.ps1`.
- **Файли для сервера мусять мати LF** — `deploy/terraform/files/.gitattributes`
  (`eol=lf`), а скрипти ще й прибирають `` перед завантаженням.
- **`deploy/local/` — лише тимчасове**: доступи й ключі — у `deploy/secrets/`.

## Коли щось пішло не так

| Симптом | Де дивитись |
| --- | --- |
| `deploy.ps1` чи CI: «… зашифрований» | `git-crypt unlock`; у CI — секрет `GIT_CRYPT_KEY` |
| `app: healthy` не дочекались | у виводі — останні 60 рядків `docker logs dndsheet-app`; найчастіше `.env` |
| `https: ще немає сертифіката` | `docker logs dndsheet-caddy`: запис DNS ще не поширився або закритий порт 80 |
| Terraform хоче все створити заново | стан не закомічений або не розблокований |
| SSH: `Permission denied (publickey)` | права на ключ (див. вище) або ключ не той |
