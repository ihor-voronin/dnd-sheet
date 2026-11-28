# Several projects on one VPS: repositories, secrets and deploys

The plan for when the shared PostgreSQL ([ADR 0006](adr/0006-shared-postgresql.md),
[docs/database.md](database.md)) serves more than dnd-sheet. It covers which repository
owns what, where secrets live, how the server and each app get deployed, and how to add or
remove a project. Nothing here is built yet. Once the platform repository exists, this file
moves there as its README.

**Status:** plan, 2026-11-28. The decisions marked **[owner]** in § 9 need a yes before work
starts.

## 1. The problem with today's layout

dnd-sheet owns the whole server: `deploy/terraform` (bootstrap, firewall, swap, DNS, the
Terraform state), Caddy on ports 80/443 inside its own compose, the SSH key, the Cloudflare
token, and now `deploy/postgres`. A second project can't live with that:

- **Ports 80/443 can be bound once.** A second web app needs the same reverse proxy, so
  Caddy has to stop being part of dnd-sheet.
- **Shared things change for shared reasons.** A Postgres upgrade or a firewall rule
  shouldn't be a dnd-sheet PR, and a dnd-sheet deploy (`--remove-orphans`) must never be
  able to touch them.
- **Secrets would be copied around.** Each project would need the Cloudflare token, the root
  key and the Postgres superuser password.

## 2. Repositories

```
platform  (new, private or public, git-crypt)      the server and everything shared
├─ terraform/        bootstrap.sh, dns.tf (all records), state        ← from dnd-sheet/deploy/terraform
├─ edge/             Caddy: compose.yml, Caddyfile (imports sites/*)  ← Caddy leaves dnd-sheet's compose
├─ postgres/         compose.yml, postgresql.conf, pg_hba.conf,       ← from dnd-sheet/deploy/postgres
│                    create-project.sql, provision.sh, backup.sh
├─ projects/         one small file per project: slug, domain, database yes/no, URL variable
├─ scripts/          deploy_platform.py; deploy_app.py (shared by every app, § 5)
├─ .github/workflows ci.yml (validate everything), deploy.yml (manual), deploy-app.yml (reusable)
└─ secrets/          ssh key, Cloudflare token, Terraform state and vars, backup tokens

dnd-sheet  (and every other project)                 only what belongs to the app
├─ Dockerfile, code, migrations (backend/src/dndsheet/db/migrations)
├─ deploy/compose.yml      the app service only; joins the external networks `edge` and `pg`
├─ deploy/site.caddy       its Caddy site block (domain, headers, cache rules)
├─ deploy/project.toml     slug, image, health URL: what the shared deploy needs to know
├─ deploy/secrets/         app-only secrets (bot token, owner id), its own deploy key
└─ .github/workflows/deploy.yml   calls platform's reusable deploy-app.yml
```

Rules of thumb:

- **One owner per file on the server.** Platform owns `/opt/edge`, `/opt/pg`, cron, ufw and
  DNS. A project owns `/opt/<slug>`, `/opt/edge/sites/<slug>.caddy` and its database's
  schema. Nothing else.
- **Naming is one slug everywhere:** the database, the roles (`<slug>`, `<slug>_app`),
  `/opt/<slug>`, the compose project, the container prefix, the site file. The domain is
  usually `<slug>.voronin.app`, except dnd-sheet keeps `dnd.voronin.app`.
- **Shared code is versioned, not copied.** Every app deploys through platform's
  reusable workflow and `deploy_app.py`, pinned to a tag (`@v1`). A fix to the deploy lands
  once, and each project picks it up when it bumps the tag.

## 3. On the server

```
/opt/edge      compose project "edge": Caddy :80/:443, networks: edge
   Caddyfile   global options + `import sites/*.caddy`; the bare IP → redirect
   sites/      dndsheet.caddy, <next>.caddy …   (written by each app's deploy)
/opt/pg        compose project "pg": PostgreSQL 18, networks: pg, no published port
   projects/<slug>/app.env, owner.env           (written by provision.sh, root 600)
   backups/    nightly dumps of every database
/opt/dndsheet  compose project "dndsheet": app, networks: edge + pg (both external)
/opt/<next>    the same shape
```

- Two Docker networks with different jobs. Caddy and the apps share `edge`. The apps and
  Postgres share `pg`. Caddy never sees the database, and the database never sees the
  internet.
- Each app compose sets `mem_limit`, so one project can't eat the box. The sum of the
  limits plus Postgres (512 MB) plus Caddy stays under the RAM minus ~300 MB for the OS
  and Docker.

## 4. Secrets: database passwords never leave the server

Who holds what:

| Secret | Lives in | Used by |
| --- | --- | --- |
| root SSH key for platform work | platform `secrets/` | platform deploy, Terraform |
| one SSH deploy key **per project** (separate lines in `authorized_keys`) | that project's `deploy/secrets/` | that project's deploy |
| Cloudflare token, Terraform state | platform `secrets/` | Terraform only |
| Postgres superuser password | platform `secrets/` → `/opt/pg/.env` | administration only |
| a project's DB passwords (owner, app) | **only on the server**, `/opt/pg/projects/<slug>/` | that project's deploy and app |
| app secrets (bot tokens, …) | the project's `deploy/secrets/` | the app |
| R2 / backup ping tokens | platform `secrets/` | backups |

`provision.sh <slug> <URL_VARIABLE>` runs on the server as part of the platform deploy, once
per project file. When the project has no passwords yet, it generates them (`openssl rand`),
runs `create-project.sql`, and writes:

- `app.env`: `DNDSHEET_DATABASE_URL=postgresql://dndsheet_app:…@pg:5432/dndsheet`. The
  variable name comes from the project file. The app's compose loads it with
  `env_file: [.env, /opt/pg/projects/dndsheet/app.env]`.
- `owner.env`: the same URL for the owner role. Only the one-shot migration container gets
  it.

When the passwords exist, it reruns the SQL with them (grants stay up to date).
`provision.sh --rotate <slug>` makes new ones, and the next app deploy picks them up.

Why not git-crypt for these too: the passwords would have to live in two repositories
(platform creates the role, the project connects with it) and be kept in sync. With the
server as the only copy there's nothing to sync, and nothing to leak from a repository. If
the server is lost, a restore loads the dumps (roles without passwords), reruns
`provision.sh --rotate` for every project, and redeploys the apps. The off-server backup
may also carry `projects/` encrypted (restic or rclone crypt) to skip that step.

The trade-off for SSH keys: anyone who can run `docker` on the host is effectively root, so
separate Linux users per project wouldn't isolate projects from each other. Separate keys
still pay off. Each one can be revoked alone (a leaked key of one repo doesn't need
rotating everywhere), and `authorized_keys` comments show whose key it is.

## 5. Deploys

### Platform (rare, by hand or manual workflow)

`deploy_platform.py`, stateless like today's `deploy_app.py`, in this order:

1. Terraform: bootstrap (Docker, ufw, swap, cron, sshd) and DNS records for every project
   file.
2. `/opt/pg`: upload compose and config, `docker compose up -d`, wait for healthy.
3. `/opt/edge`: upload compose and Caddyfile, `docker compose up -d`,
   `caddy validate && caddy reload`.
4. `provision.sh` for every project file with `database: true`.
5. Backup cron (`/etc/cron.daily/pg-backup`, `/etc/cron.weekly/pg-restore-check`).

Postgres restarts only when its compose or config changed (compose decides). Minor version
bumps are a one-line PR here (docs/database.md § 6).

### An app (every merge to main, per project)

The project's `deploy.yml` builds the image and calls the reusable workflow
`platform/.github/workflows/deploy-app.yml@v1` with its `project.toml`. The shared
`deploy_app.py` then:

1. **Checks the platform is there.** Networks `edge` and `pg` exist, and if the project has a
   database, `/opt/pg/projects/<slug>/owner.env` exists. Otherwise it stops: "run the
   platform deploy / add projects/<slug>.yml".
2. Ships the image if its id changed (as today: `docker save` → `docker load`).
3. Writes `/opt/<slug>/compose.yml` and `.env`.
4. **Migrates:** `docker run --rm --network pg --env-file /opt/pg/projects/<slug>/owner.env
   <image> <migrate command>`. The command comes from `project.toml`
   (`python -m dndsheet.db migrate` here, `alembic upgrade head` elsewhere). A failure stops
   the deploy before the new app starts. The old one keeps running.
5. `docker compose up -d --remove-orphans` in `/opt/<slug>`. It can only remove that
   project's own containers.
6. Writes `/opt/edge/sites/<slug>.caddy` and runs `caddy validate`, then `caddy reload`. An
   invalid file fails the deploy, and Caddy keeps serving the old config for every site.
7. Waits for healthy and for the public URL, as today.

`concurrency: deploy-<slug>` per project. Two projects may deploy at the same time:
their files don't overlap, Caddy serializes reloads, and migrations lock per database.

**Image transport.** It stays `docker save | scp` for now: no registry and no new
credentials. With three or more projects, a private GHCR image is cheaper on CI time. The
server then pulls with a read-only token. dnd-sheet's image contains book texts, so the
package must stay private.

### CI

- **platform:** `terraform fmt -check` and `validate`; shellcheck/shfmt;
  `caddy validate` of the Caddyfile with every site file of the projects in `projects/` as
  fixtures; and a job that starts `postgres:<pinned>` with the real `postgresql.conf` and
  `pg_hba.conf`, provisions two fake projects and asserts the isolation checks from
  docs/database.md § 2 (the app role can't do DDL, no cross-project connect, no superuser
  over TCP).
- **each project:** as today, plus a Postgres service container on the **same major** as
  platform pins. A test that compares the pin with the platform repo's tag keeps them from
  drifting.

## 6. Adding a project

1. **platform PR:** `projects/<slug>.yml` (`slug`, `domain`, `database: true`,
   `url_env`, `deploy_key`, the public half of the project's new deploy key). Merge, then run
   the platform deploy: DNS record, database, roles, passwords on the server, the key in
   `authorized_keys`.
2. **project repo:** `deploy/compose.yml` (app only, networks `edge` and `pg` external,
   `mem_limit`), `deploy/site.caddy`, `deploy/project.toml`, the private half of the deploy
   key in `deploy/secrets/`, and `deploy.yml` calling `deploy-app.yml@v1`.
3. Migrations in its own tool and its own history (§ 3 of docs/database.md); its own
   database means no coordination with other projects.
4. First deploy, then check `/healthz`, a backup the next morning, and a restore check at the
   end of the week.

Expected effort per new project once the platform exists: about an hour of wiring.

## 7. Removing a project

1. Final dump (`backup.sh` already has last night's; take a fresh one), kept 90 days.
2. In the project: `docker compose down` in `/opt/<slug>`, then remove the site file and
   reload Caddy.
3. platform PR: delete `projects/<slug>.yml`. The platform deploy removes the DNS record
   and the deploy key. Dropping the database and roles stays manual on purpose:
   `DROP DATABASE <slug>; DROP ROLE <slug>_app; DROP ROLE <slug>;`.

## 8. Moving dnd-sheet to this layout

| # | Step | Downtime | Effort |
| --- | --- | --- | --- |
| 1 | Create the platform repo: git-crypt with a new key, protected `main`. Move `deploy/terraform`, `deploy/postgres`. Move the Terraform state (same resources: `terraform plan` must say "No changes" before anything else) | none | 2–3 h |
| 2 | `edge` stack: Caddyfile with `import sites/*.caddy`. dnd-sheet gets `deploy/site.caddy` (today's Caddyfile block). Copy the `caddy-data` volume, so certificates move with it | ~10 s while the old Caddy stops and the new one binds 80/443 | 2 h |
| 3 | dnd-sheet compose: drop the `caddy` service, join `edge`. Deploy through the shared `deploy_app.py` (generalized from today's script) | ~5 s (app restart) | 2–3 h |
| 4 | `pg` stack and `provision.sh dndsheet DNDSHEET_DATABASE_URL`. Migration step in the deploy. App still on SQLite: `app.env` is added only at the cutover | none | 2 h |
| 5 | Backups, restore check, off-site copy, ping | none | 2–3 h |
| 6 | Data cutover (docs/database.md § 4): add `app.env` to the compose `env_file`, copy and verify, deploy | ~5 min | 1 h |
| 7 | Remove from dnd-sheet what moved out: `deploy/terraform`, `deploy/postgres`, the Cloudflare token, the root key. Its own deploy key only | none | 1 h |
| | **Total** | | **≈ 2 days** |

Steps 1–3 are worth doing even before the database: they are what makes a second project
possible at all. Steps 4–6 replace § 9 of docs/database.md (same work, different home).

## 9. Decisions for the owner

1. **[owner] A separate platform repository** (recommended), or keep the shared parts in
   dnd-sheet until the second project actually exists. Keeping them postpones the move, but
   the Caddy split (steps 2–3) is needed either way.
2. **[owner] Its visibility.** Public is fine with git-crypt and makes the reusable workflow
   trivially callable. A private repo works too, if its Settings → Actions → Access allows
   repositories of the same owner. Check that setting when creating it.
3. **[owner] DB passwords generated and kept on the server** (recommended, § 4), or in
   git-crypt in each project repo.
4. **[owner] Image transport:** `docker save` over SSH (today, no new credentials) or a
   private GHCR package.
5. **[owner] Off-site backups:** Cloudflare R2 (needs a token) or another target.
