# Deploy: the shared VPS, CI and secrets

The site runs at **https://dnd.voronin.app** on a RackNerd VPS that several projects share.
The server itself (DNS in Cloudflare, Docker, firewall, swap, the shared Caddy, PostgreSQL,
backups) belongs to the **[vps-infra](https://github.com/ihor-voronin/vps-infra/blob/main/docs/platform.md)** repository. This repository
only says what dnd-sheet is: its image, `deploy/compose.yml`, `deploy/site.caddy` and
`deploy/project.toml`, plus its encrypted secrets.

- **Normally** GitHub Actions deploys: PR merged into `main` → CI green → `deploy.yml`
  calls vps-infra's reusable `deploy-app.yml@v1` (see [docs/ci.md](ci.md)).
- **By hand from Windows** the same script runs (vps-infra checked out next to this
  repository):

```powershell
.\deploy\deploy.ps1
```

## How it works

```
GitHub Actions: deploy.yml → vps-infra deploy-app.yml@v1     VPS (Ubuntu 24.04)
  docker build (runtime) ──► dndsheet:local                  ─────────────────────────────
  vps-infra scripts/deploy_app.py --project deploy/project.toml (SSH, deploy_ed25519)
     ├─ keep the running release: dndsheet:previous, /opt/dndsheet/previous/
     ├─ image: docker save + gzip ─────────────────────────► docker load (if the id is new)
     ├─ compose.yml, .env ─────────────────────────────────► /opt/dndsheet → compose -p dndsheet up -d
     └─ site.caddy ────────────────────────────────────────► /opt/edge/sites/dndsheet.caddy
                                                             ├─ edge-caddy :80/:443 (vps-infra, every site)
                                                             └─ dndsheet-app :8000 on the `edge` network
```

The script is stateless: every run brings the server to what's in the repository. The
image is uploaded only when its id changed (`/opt/dndsheet/IMAGE_ID`). The site file is
validated before Caddy reloads, so a broken one never takes the other sites down. The
script waits for the container's health and for `https://dnd.voronin.app/healthz`. If any
step fails it **rolls back** to the release that ran before (below, "A deploy failed").

**Infrastructure** (the DNS record, the server setup, the shared Caddy) changes only from
vps-infra: `python scripts/terraform.py plan|apply` and its manual platform deploy
([vps-infra docs/deploys.md](https://github.com/ihor-voronin/vps-infra/blob/main/docs/deploys.md)).

**Why the image isn't built on the server.** The compendium corpus (`content/compendium`,
`bestiary`, `index`) is book text: in git it exists only encrypted. CI (the
`GIT_CRYPT_KEY` secret) and your machine can unlock it; the server can't.

## Files

| Path | What it is | In git |
| --- | --- | --- |
| `deploy/project.toml` | what vps-infra deploys: image, compose, site, container, health URL, which secrets go where | plain |
| `deploy/compose.yml` | the app container on the `edge` network (no Caddy here any more) | plain |
| `deploy/site.caddy` | the site block in the shared Caddy: compression, caching of `/assets/*`, security headers | plain |
| `deploy/deploy.ps1` | Windows entry point: build, then vps-infra's `deploy_app.py` | plain |
| `.github/workflows/` | CI and deploy (docs/ci.md) | plain |
| `deploy/secrets/prod.env` | app variables → `/opt/dndsheet/.env` (mode 600) | encrypted |
| `deploy/secrets/server.toml` | server address, user, port | encrypted |
| `deploy/secrets/ssh/deploy_ed25519` | this project's deploy key (its public half is in vps-infra's `projects/dndsheet.toml`) | encrypted |
| `deploy/secrets/ssh/id_ed25519`, `cloudflare.env`, `racknerd.env`, `terraform/` | the old copies from before vps-infra; removed in step 8 of the move | encrypted |
| `content/compendium`, `bestiary`, `index` | compendium corpus (book texts) | encrypted |
| `deploy/local/` | temporary: git-crypt key for the GitHub secret | no (`.gitignore`) |

Encryption is driven by the `.gitattributes` rules in `deploy/secrets/` and in the corpus
folders. File names are visible, contents are not. The `secrets-encrypted` hook (pre-commit
and CI) checks that all of it really is ciphertext in the index.

## Regular deploy

Through a PR: merge into `main` → CI → the deploy runs by itself. By hand from Windows:

```powershell
.\deploy\deploy.ps1            # build the image and deploy
.\deploy\deploy.ps1 -NoBuild   # deploy the dndsheet:local image as it is
.\deploy\deploy.ps1 -DryRun    # only print the steps
```

It expects vps-infra in `..\vps-infra` (or `-VpsInfra <path>`), and refuses to run while
anything it needs in `deploy/secrets/` is still encrypted.

### A deploy failed

Before it changes anything, the deploy tags the running image `dndsheet:previous` and
copies `compose.yml`, `IMAGE_ID`, `.env` and the site file to `/opt/dndsheet/previous/`.
When a later step fails (the app never gets healthy, a command on the server fails), it
puts them back, reloads Caddy and runs `up -d` again, so the site keeps the previous
release. The job still fails, and its last lines say whether the previous release is
healthy. By hand: [vps-infra docs/deploys.md](https://github.com/ihor-voronin/vps-infra/blob/main/docs/deploys.md#what-a-failure-does).
The SQLite database isn't touched by a rollback.

## First run on a new machine

1. Tools: `winget install --id AGWA.git-crypt -e`, Docker Desktop, Python 3, GnuPG with
   your key; `git clone https://github.com/ihor-voronin/vps-infra ..\vps-infra`.
2. Unlock secrets and the corpus:

   ```powershell
   git config gpg.program "C:/Program Files/GnuPG/bin/gpg.exe"
   git-crypt unlock
   ```

   `gpg.program` is needed because the key lives in GnuPG for Windows, not in the `gpg`
   bundled with Git Bash.
3. `.\deploy\deploy.ps1 -DryRun` prints every step without touching the server.

## Server access

```powershell
ssh -i deploy\secrets\ssh\deploy_ed25519 root@192.227.140.142
```

Password login over SSH is disabled. If the key is lost — the VNC console in the
RackNerd panel (credentials in `deploy/secrets/racknerd.env`), root password.

On Windows, OpenSSH rejects a key with "foreign" permissions — once:
`icacls deploy\secrets\ssh\deploy_ed25519 /inheritance:r /grant:r "$env:USERNAME:R"`.
On Linux — `chmod 600`.

On the server:

| What | Where |
| --- | --- |
| app | `/opt/dndsheet` (`compose.yml`, `.env`, `previous/` for the rollback) |
| site in the shared Caddy | `/opt/edge/sites/dndsheet.caddy` (vps-infra's `/opt/edge`) |
| database | `/opt/dndsheet/var/dndsheet.sqlite3` (SQLite, WAL) |
| backups | `/opt/dndsheet/backups/dndsheet-YYYY-MM-DD.sqlite3`, 14 days (`/etc/cron.daily/dndsheet-backup`) |
| logs | `docker logs dndsheet-app`, `docker logs edge-caddy` |

The database is a host folder mounted into the container (not a Docker volume), so
deploys, image changes and even `docker compose down -v` don't touch it. Backups are on
the same disk — an off-server copy is not set up yet.

## Restore the database from a backup

```bash
cd /opt/dndsheet
docker compose -p dndsheet -f compose.yml stop app
cp backups/dndsheet-2026-11-27.sqlite3 var/dndsheet.sqlite3
chown 10001:10001 var/dndsheet.sqlite3
docker compose -p dndsheet -f compose.yml start app
```

## Domain and HTTPS

- DNS: Cloudflare, zone `voronin.app`; the record is managed by vps-infra's Terraform
  (`dns.tf`, the domain from its `projects/dndsheet.toml`).
  No Cloudflare proxy: Let's Encrypt issues the certificate through Caddy (HTTP-01),
  and the Telegram widget sees the real domain.
- The shared Caddy (vps-infra's `edge-caddy`) renews the certificate itself; `http://`
  and the bare IP redirect to `https://dnd.voronin.app`.
- To change the domain: `domain` in vps-infra's `projects/dndsheet.toml` and its
  Terraform apply, then the new name in `deploy/site.caddy`, `deploy/project.toml`
  (`health_url`), `DNDSHEET_PUBLIC_URL` in `prod.env`, and a deploy.

## Telegram sign-in and the Mini App

The bot is `@DnD_Sheet_VoroninAppBot`; its name and token are in `deploy/secrets/prod.env`
(`DNDSHEET_TELEGRAM_BOT`, `DNDSHEET_TELEGRAM_BOT_TOKEN`). There is no separate bot
server: both the site widget and the Mini App work without one.

**On the site** — the "Log in with Telegram" widget. In @BotFather: `/setdomain` →
`dnd.voronin.app`.

**In Telegram (Mini App)** — the same site inside Telegram:

- sign-in without a button: Telegram passes a signed `initData`, the server verifies it
  (`POST /api/v1/auth/telegram-webapp`, key — HMAC "WebAppData" of the bot token) and
  returns a session token. Same Telegram id — same player, characters shared with the site;
- the session travels as `Authorization: Bearer …`: Telegram in a browser hosts the site
  in an iframe where cookies don't arrive;
- Telegram's theme and Back button; swiping down doesn't close the app mid-sheet;
- Telegram downloads the PDF itself (`downloadFile`), printing opens in the phone's
  browser — via a link with a short-lived `?link=…` token (5 minutes, GET only);
- "Share" also gives `https://t.me/DnD_Sheet_VoroninAppBot?startapp=s_<token>` —
  the read-only sheet opens right inside Telegram.

The Telegram script (`telegram-web-app.js`) loads only when Telegram opened the page
(see `frontend/index.html`); the regular site doesn't contact telegram.org.

Setup in @BotFather (done by the bot owner):

1. `/mybots` → bot → **Bot Settings → Configure Mini App → Enable Mini App** →
   URL `https://dnd.voronin.app` — the bot profile gets an "Open" button.
2. **Bot Settings → Menu Button** → URL `https://dnd.voronin.app`, text
   "Лист персонажа" — a button next to the message field.
3. Link to the app: `https://t.me/DnD_Sheet_VoroninAppBot?startapp`.
4. Bot avatar: `/setuserpic` → bot → send `branding/bot-avatar.png`
   (640×640, the same d20 as the site icon; all icons are generated by
   `scripts/make_icons.py`).

**Testing locally without Telegram**: `.claude/launch.json` → `miniapp-check`
(test token `123456:TEST-TOKEN`). Sign `initData` with that token (as
`backend/tests/identity/test_auth.py::_init_data` does) and open
`http://localhost:8021/?x=1#tgWebAppData=<initData>&tgWebAppVersion=8.0&tgWebAppPlatform=android`.

## Secrets

- **Add a person** (so they can deploy): import their public GPG key and run
  `git-crypt add-gpg-user --trusted <fingerprint>` — the command commits by itself.
- **Revoking** can't go "back in time": whoever had the key could keep the old
  secrets. Rotate them: a new Cloudflare token, a new SSH key (update
  `authorized_keys` on the server), a new bot token.
- **Before committing** — `git-crypt status -e`: everything in `deploy/secrets/` must be
  `encrypted` (the `secrets-encrypted` hook checks this too).
- A secret that has ever been committed in plain text stays in history — it is rotated,
  not encrypted retroactively.

## Image

| | Size |
| --- | --- |
| on the server's disk | ~270 MB |
| upload archive | ~90 MB |

What keeps it at that size: python:3.12-slim (~120 MB), WeasyPrint with fontTools
(~60 MB), Pango/HarfBuzz and the DejaVu font for PDF (~25 MB), the compendium corpus
(~46 MB). Python dependencies are installed in a separate stage without `.pyc` and
without backend sources; uvicorn without `[standard]`.

## Pitfalls (already worked around)

- **Terraform `local-exec` on Windows**: the `external` provider can't reach Docker
  Desktop, and `cmd` breaks quotes in paths. That's why the app deploy is a Python script
  (now vps-infra's `deploy_app.py`), not Terraform.
- **PowerShell 5 reads `.ps1` without a BOM as cp1251** — Cyrillic breaks parsing; the
  `fix-byte-order-marker` hook leaves `.ps1` files alone.
- **Files for the server must have LF**: vps-infra's scripts strip `\r` before
  uploading.
- **`deploy/local/` is temporary only**: credentials and keys belong in `deploy/secrets/`.

## When something goes wrong

| Symptom | Where to look |
| --- | --- |
| `deploy.ps1` or CI: "… is encrypted" | `git-crypt unlock`; in CI — the `GIT_CRYPT_KEY` secret |
| "did not become healthy" … "rolled back" | the new release failed and the previous one runs again: the logs are in the output |
| HTTPS doesn't answer yet | `docker logs edge-caddy`: DNS not propagated yet or port 80 closed |
| SSH: `Permission denied (publickey)` | key permissions (see above) or the wrong key |
