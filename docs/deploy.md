# Deploy: server, Terraform, CI and secrets

The site runs at **https://dnd.voronin.app** — a RackNerd VPS, domain in Cloudflare.
Everything needed to deploy is in the repository: the code in plain text; credentials,
Terraform state and the book corpus encrypted with git-crypt.

- **Normally** GitHub Actions deploys: PR merged into `main` → CI green →
  `deploy.yml` (see [docs/ci.md](ci.md)).
- **By hand from Windows** — the same logic in one command:

```powershell
.\deploy\terraform\deploy.ps1
```

## How it works

Two parts that change at different rates:

```
APP — with every merge into main                  VPS (Ubuntu 24.04, 192.227.140.142)
GitHub Actions (deploy.yml) or deploy.ps1         ─────────────────────────────────
  docker build (runtime)  ──► dndsheet:local
  scripts/deploy_app.py (SSH)
     ├─ image: docker save + gzip ──────────────► docker load (if the id is new)
     └─ compose.yml, Caddyfile, .env ───────────► /opt/dndsheet → docker compose up -d
                                                    ├─ caddy  :80/:443  (Let's Encrypt)
                                                    └─ app    :8000     (dndsheet:local)

INFRASTRUCTURE — rarely, by hand
deploy.ps1 -Infra ─► terraform apply
  ├─ cloudflare_dns_record ─────────────────────► Cloudflare: dnd.voronin.app → IP (no proxy)
  └─ bootstrap (SSH) ───────────────────────────► Docker, ufw, swap, backups, key-only SSH
```

**The app — `scripts/deploy_app.py`.** Stateless: every run brings the server to what's
in the repository. The image is uploaded only when its id changed (the last id is in
`/opt/dndsheet/IMAGE_ID`), Caddy reloads its config, and the script waits for the app to
become healthy and for HTTPS to answer. CI (Linux) and `deploy.ps1` (Windows) run the
same script.

**Infrastructure — Terraform.** RackNerd has no Terraform API, so the server was bought
by hand; Terraform brings it to the desired state over SSH and manages the DNS record in
Cloudflare. Each step reruns only when what it depends on changes:

| Step | Reruns when | What it does |
| --- | --- | --- |
| `cloudflare_dns_record.site` | IP or domain changes | A record `dnd.voronin.app` → IP, "grey cloud" (traffic goes straight to the server) |
| `terraform_data.bootstrap` | `files/bootstrap.sh` changes | Docker from the official repository, ufw (22, 80, 443), 2 GB swap, daily database backup, `PasswordAuthentication no` |

**Why the app isn't in Terraform.** It used to be — but then the Terraform state would
have to be committed back into the protected `main` branch after every CI deploy. The
stateless script doesn't need that.

**Why the image isn't built on the server.** The compendium corpus (`content/compendium`,
`bestiary`, `index`) is book text: in git it exists only encrypted. CI (the
`GIT_CRYPT_KEY` secret) and your machine can unlock it; the server can't.

## Files

| Path | What it is | In git |
| --- | --- | --- |
| `scripts/deploy_app.py` | app deploy (CI and Windows) | plain |
| `deploy/terraform/*.tf` | infrastructure: DNS, server setup | plain |
| `deploy/terraform/files/` | `bootstrap.sh`, `compose.yml`, `Caddyfile.tftpl` | plain (LF) |
| `deploy/terraform/deploy.ps1` | Windows entry point: the app or `-Infra` | plain |
| `.github/workflows/` | CI and deploy (docs/ci.md) | plain |
| `deploy/secrets/prod.env` | app variables → `.env` on the server | encrypted |
| `deploy/secrets/cloudflare.env` | `CLOUDFLARE_API_TOKEN` (DNS for zone `voronin.app`) | encrypted |
| `deploy/secrets/racknerd.env` | VPS panel and root password (for the panel console) | encrypted |
| `deploy/secrets/ssh/id_ed25519` | the key used to reach the server | encrypted |
| `deploy/secrets/terraform/terraform.tfvars` | IP, domain, zone | encrypted |
| `deploy/secrets/terraform/terraform.tfstate` | Terraform state (infrastructure only) | encrypted |
| `content/compendium`, `bestiary`, `index` | compendium corpus (book texts) | encrypted |
| `deploy/local/` | temporary: git-crypt key for the GitHub secret | no (`.gitignore`) |

Encryption is driven by the `.gitattributes` rules in `deploy/secrets/` and in the corpus
folders. File names are visible, contents are not. The `secrets-encrypted` hook (pre-commit
and CI) checks that all of it really is ciphertext in the index.

## Regular deploy

Through a PR: merge into `main` → CI → the deploy runs by itself. By hand from Windows:

```powershell
.\deploy\terraform\deploy.ps1                # build the image and update the app
.\deploy\terraform\deploy.ps1 -NoBuild       # no rebuild (only config or .env changed)
.\deploy\terraform\deploy.ps1 -Infra -Plan   # what Terraform would change
.\deploy\terraform\deploy.ps1 -Infra         # apply infrastructure (asks for "yes")
```

`deploy.ps1` refuses to run while anything in `deploy/secrets/` is still encrypted.

**After `-Infra`, commit the state** — otherwise Terraform on another machine will think
nothing has been created yet:

```powershell
git add deploy/secrets/terraform
git commit -m "Terraform state after infra change"
```

## First run on a new machine

1. Tools: `winget install --id Hashicorp.Terraform -e`,
   `winget install --id AGWA.git-crypt -e`, Docker Desktop, Python 3, GnuPG with
   your key.
2. Unlock secrets and the corpus:

   ```powershell
   git config gpg.program "C:/Program Files/GnuPG/bin/gpg.exe"
   git-crypt unlock
   ```

   `gpg.program` is needed because the key lives in GnuPG for Windows, not in the `gpg`
   bundled with Git Bash.
3. `.\deploy\terraform\deploy.ps1 -Infra -Plan` — should report "No changes".

## Server access

```powershell
ssh -i deploy\secrets\ssh\id_ed25519 root@192.227.140.142
```

Password login over SSH is disabled. If the key is lost — the VNC console in the
RackNerd panel (credentials in `deploy/secrets/racknerd.env`), root password.

On Windows, OpenSSH rejects a key with "foreign" permissions — once:
`icacls deploy\secrets\ssh\id_ed25519 /inheritance:r /grant:r "$env:USERNAME:R"`.
On Linux — `chmod 600`.

On the server:

| What | Where |
| --- | --- |
| app | `/opt/dndsheet` (`compose.yml`, `Caddyfile`, `.env`) |
| database | `/opt/dndsheet/var/dndsheet.sqlite3` (SQLite, WAL) |
| backups | `/opt/dndsheet/backups/dndsheet-YYYY-MM-DD.sqlite3`, 14 days (`/etc/cron.daily/dndsheet-backup`) |
| logs | `docker logs dndsheet-app`, `docker logs dndsheet-caddy` |

The database is a host folder mounted into the container (not a Docker volume), so
deploys, image changes and even `docker compose down -v` don't touch it. Backups are on
the same disk — an off-server copy is not set up yet.

## Restore the database from a backup

```bash
cd /opt/dndsheet
docker compose -f compose.yml stop app
cp backups/dndsheet-2026-11-27.sqlite3 var/dndsheet.sqlite3
chown 10001:10001 var/dndsheet.sqlite3
docker compose -f compose.yml start app
```

## Domain and HTTPS

- DNS: Cloudflare, zone `voronin.app`, the record is managed by Terraform (`dns.tf`).
  No Cloudflare proxy: Let's Encrypt issues the certificate through Caddy (HTTP-01),
  and the Telegram widget sees the real domain.
- Caddy renews the certificate itself; `http://` and the bare IP redirect to
  `https://dnd.voronin.app`.
- To change the domain: `domain` in `deploy/secrets/terraform/terraform.tfvars` →
  `deploy.ps1 -Infra` (Terraform removes the old record) and `deploy.ps1 -NoBuild`.

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
  Desktop, and `cmd` breaks quotes in paths. That's why the image and app moved out of
  Terraform into `scripts/deploy_app.py` (Python behaves the same on Windows and in CI).
- **PowerShell 5 reads `.ps1` without a BOM as cp1251** — Cyrillic breaks parsing; the
  `fix-byte-order-marker` hook leaves `.ps1` files alone.
- **Files for the server must have LF** — `deploy/terraform/files/.gitattributes`
  (`eol=lf`), and the scripts also strip `\r` before uploading.
- **`deploy/local/` is temporary only**: credentials and keys belong in `deploy/secrets/`.

## When something goes wrong

| Symptom | Where to look |
| --- | --- |
| `deploy.ps1` or CI: "… is encrypted" | `git-crypt unlock`; in CI — the `GIT_CRYPT_KEY` secret |
| "app did not become healthy" | the output shows the last 60 lines of `docker logs dndsheet-app`; usually `.env`. The deploy has already rolled back (below) |
| HTTPS doesn't answer yet | `docker logs dndsheet-caddy`: DNS not propagated yet or port 80 closed |
| Terraform wants to create everything again | state not committed or not unlocked |
| SSH: `Permission denied (publickey)` | key permissions (see above) or the wrong key |

### A deploy failed

`deploy_app.py` sets aside what runs before it changes anything: the image is tagged
`dndsheet:previous`, and `compose.yml`, `Caddyfile`, `.env` and `IMAGE_ID` are copied to
`/opt/dndsheet/previous/`. When a later step fails (the app never gets healthy, a command on
the server fails), it puts them back and runs `up -d` again, so the site keeps the previous
release. The job still fails. Its last lines say "rolled back: the previous release is
running and healthy", or that the previous one isn't healthy either. The very first deploy
has nothing to go back to.

The same by hand, after a deploy that left the server broken:

```sh
cd /opt/dndsheet && cp -p previous/compose.yml previous/Caddyfile previous/.env previous/IMAGE_ID .   && docker tag dndsheet:previous dndsheet:local   && DNDSHEET_IMAGE=dndsheet:local docker compose -f compose.yml up -d
```

SQLite isn't touched by a rollback: the data stays as the new release left it.
