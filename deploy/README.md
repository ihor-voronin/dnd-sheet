# Deploy and secrets

> The full description — how the deploy works, the server, backups, recovery and
> diagnostics: **[docs/deploy.md](../docs/deploy.md)**. This is the short version.

Deploy secrets (the bot token, the owner id, the server address and the SSH key) live in
[`deploy/secrets/`](secrets/) and are **encrypted with git-crypt**: only ciphertext
reaches GitHub, and only someone whose GPG key has been added to the repository
(`.git-crypt/keys/`) can decrypt them.

## What's here

| File | What it holds |
| --- | --- |
| `secrets/prod.env` | the `DNDSHEET_*` variables for production — on the server it becomes `.env` next to `docker-compose.yml` |
| `secrets/racknerd.env` | the VPS panel (SolusVM) and the root password — for the console in the panel; SSH doesn't accept passwords |
| `secrets/cloudflare.env` | `CLOUDFLARE_API_TOKEN` — a token for writing DNS (the `voronin.app` zone) |
| `secrets/server.toml` | the server address, user, port (for vps-infra's `deploy_app.py`) |
| `secrets/ssh/deploy_ed25519` | this project's deploy key: the deploy and CI log in with it |
| `secrets/ssh/id_ed25519` | the old key from before vps-infra (it is vps-infra's platform key now); removed here in step 8 |
| `secrets/terraform/` | the old Terraform state; Terraform runs only from vps-infra now, removed here in step 8 |
| `secrets/.gitattributes` | the "encrypt everything in this folder" rule (the file itself is plaintext) |

File **names** aren't encrypted — only the contents. So don't name files in a way that
gives the secret away.

## Unlock (a new computer or server)

You need git-crypt and a GPG key that has been added to the repository:

```powershell
winget install --id AGWA.git-crypt -e
git config gpg.program "C:/Program Files/GnuPG/bin/gpg.exe"   # Windows: the GnuPG that holds the key
git-crypt unlock
```

On a Linux server: `apt install git-crypt gnupg`, import the GPG key (`gpg --import`),
then `git-crypt unlock`.

Without unlocking, the files in `secrets/` are binary ciphertext; the rest of the
repository works as usual.

## Add a person or a server

```powershell
gpg --import their-public-key.asc
git-crypt add-gpg-user --trusted <key fingerprint>
```

The command commits the key into `.git-crypt/keys/` itself. Revoking access isn't that
simple: whoever already had the key could have kept the old secrets — in that case the
secrets have to be rotated (a new token in @BotFather, etc.).

## Deploy

GitHub Actions deploys the app after a merge into `main` ([docs/ci.md](../docs/ci.md));
manually from Windows — `deploy\deploy.ps1` ([docs/deploy.md](../docs/deploy.md)).
Infrastructure is in [vps-infra](https://github.com/ihor-voronin/vps-infra/blob/main/docs/platform.md).

## Before committing

```powershell
git-crypt status -e    # the list of encrypted files; an empty "not encrypted" is good
```

A secret that reached git in plaintext even once stays in the history. It can't be
encrypted retroactively — it has to be **rotated**.
