# Database: one shared PostgreSQL for the VPS — plan and runbook

Decision and trade-offs: [ADR 0006](adr/0006-shared-postgresql.md). This document is the
how: what's built, how it runs on the server, migrations, moving the data off SQLite,
rollback, and experiments with other engines.

**Status (2026-11-28):** the local prototype is done and tested. It has the PostgreSQL
adapters behind the existing ports, migrations, a copy script with verification in both
directions, and CI against a Postgres service. **Nothing is deployed.** Production still
runs on SQLite, and nothing changes there until `DNDSHEET_DATABASE_URL` is set.

## Contents

1. [What's in the repository](#1-whats-in-the-repository)
2. [The shared server](#2-the-shared-server)
3. [Migrations](#3-migrations)
4. [Moving dnd-sheet off SQLite](#4-moving-dnd-sheet-off-sqlite)
5. [Rollback](#5-rollback)
6. [Backups, monitoring, upgrades](#6-backups-monitoring-upgrades)
7. [Adding another project](#7-adding-another-project)
8. [Experiments with other engines](#8-experiments-with-other-engines)
9. [Steps and effort](#9-steps-and-effort)
10. [Local development and tests](#10-local-development-and-tests)

## 1. What's in the repository

| Path | What it is |
| --- | --- |
| `backend/src/dndsheet/db/migrations/NNNN_*.sql` | schema migrations (plain SQL, shipped in the wheel) |
| `backend/src/dndsheet/db/migrate.py` | the migration runner |
| `backend/src/dndsheet/db/postgres.py` | `DNDSHEET_DATABASE_URL`, the connection pool, the "schema is migrated" check |
| `backend/src/dndsheet/db/transfer.py` | SQLite ↔ PostgreSQL copy and verification |
| `backend/src/dndsheet/db/__main__.py` | CLI: `python -m dndsheet.db migrate / status / copy-from-sqlite / verify / copy-to-sqlite` |
| `backend/src/dndsheet/api/storage.py` | picks the SQLite or PostgreSQL adapters |
| `characters/infrastructure/postgres_store.py` | characters, drafts, share links |
| `identity/infrastructure/postgres_identity.py`, `postgres_oauth.py` | users, sessions, OAuth |
| `backend/tests/db/` | contract tests for both backends, migrations, copy, CLI, the app on Postgres |
| `deploy/postgres/` | the shared server: `compose.yml`, `postgresql.conf`, `pg_hba.conf`, `create-project.sql`, `backup.sh` |

The domain didn't change. `dndsheet.db`, `psycopg` and `psycopg_pool` are on the
import-linter "forbidden for the domain" list.

**Schema.** `0001_initial.sql` mirrors the SQLite tables one to one, so the copy is a plain
row-by-row move:

- `characters(id, owner_id, version, record jsonb, updated_at timestamptz)` and `drafts`
  (the same, without `version`). The aggregate stays one document. **New fields inside
  the JSON (avatars, custom features) need no migration.** `jsonb` rather than `json`
  because "nothing changed" is checked with `record = $1` (key order doesn't matter), and
  because a later query or index on a key is possible. Large values are TOASTed and
  compressed (`default_toast_compression = lz4`). Images should still be files or URLs, not
  base64 inside the record: every save rewrites the whole row.
- `users`, `sessions`, `shares`, `oauth_clients/requests/codes/tokens` keep their columns.
  0/1 becomes `boolean`, `telegram_id` becomes `bigint`, and timestamps the database sets
  become `timestamptz`. Epoch-second values the ports pass as floats (`expires_at`, ...)
  stay `double precision`, so the adapters don't convert anything. `oauth_clients.info` stays
  `text`, so the SDK gets its JSON back byte for byte.
- No new foreign keys from `characters.owner_id` to `users`: with `DNDSHEET_AUTH=off` the
  owner is the local player, who isn't in `users`. The existing ones (`sessions`,
  `oauth_codes`, `oauth_tokens` → `users`) are kept, and Postgres enforces them. SQLite
  never did, which is why the copy checks for orphans (§ 4).

**Behaviour that must not change**, and the tests that pin it on both backends:
optimistic concurrency on the character version (`UPDATE … WHERE version < new`), a no-op
save is not a conflict, newest-first lists per owner, a share link is replaced, never
duplicated, OAuth codes and requests are single-use, and a used refresh token stays visible.
PostgreSQL makes two of them stronger. Taking a code is one `DELETE … RETURNING`, and a
first login from two devices at once can't create two users
(`INSERT … ON CONFLICT DO NOTHING`).

## 2. The shared server

```
VPS (2 vCPU, 2.4 GiB RAM, 29 GB disk)
├─ /opt/pg          compose project "pg"   ── container pg (postgres:18.7-alpine, 512 MB limit)
│    data/  backups/  compose.yml  postgresql.conf  pg_hba.conf  .env (superuser password)
│                         ▲ Docker network "pg" (external for the apps), no published port
├─ /opt/dndsheet    compose project        ── app (joins "pg" and its own default network) + caddy
└─ /opt/<next>      compose project        ── its app joins "pg" too
```

- **A separate compose project.** An app deploy (`docker compose up -d --remove-orphans` in
  `/opt/dndsheet`) never touches the database. It sits next to the app stack. It's not part
  of it.
- **Memory.** `shared_buffers=128MB`, `work_mem=4MB`, `max_connections=40`, JIT and parallel
  query off, `mem_limit: 512m`. Measured locally: ~55–70 MiB RSS idle and after the full
  test suite. With today's 1.85 GiB available, that leaves room for two or three more small
  apps. The 2 GB swap stays for WeasyPrint peaks.
- **Network.** No `ports:` at all. Apps join the external network `pg` and connect to
  `pg:5432`. `pg_hba.conf` lets project roles in from that network (`samenet`) with
  SCRAM, and lets the superuser in only over the socket inside the container
  (`docker exec pg psql -U postgres`). A project running on the host outside Docker would
  get `127.0.0.1:5432:5432`. Never `0.0.0.0`: Docker's port rules bypass ufw. Remote admin
  goes through an SSH tunnel to that loopback port, or `docker exec`.
- **Roles.** `create-project.sql` (idempotent) makes, per project: the database (builtin
  `C.UTF-8` collation, UTF-8), `<project>` (owns the database and `public`, runs migrations
  and copies, connection limit 5), and `<project>_app` (SELECT/INSERT/UPDATE/DELETE through
  default privileges, no DDL, connection limit 10, `statement_timeout=30s`). CONNECT is
  revoked from PUBLIC on each project database and on `postgres`. Verified locally against
  this exact configuration: the app role can't CREATE/ALTER/DROP/TRUNCATE, another
  project's roles can't connect, the superuser over TCP is rejected, and the owner can't
  create roles or databases.
- **Secrets** (git-crypt, `deploy/secrets/`, to be added in step 1 of § 9):
  - `postgres.env`: `POSTGRES_PASSWORD` (superuser) → `/opt/pg/.env`, mode 600;
  - `prod.env` gains `DNDSHEET_DATABASE_URL=postgresql://dndsheet_app:<pw>@pg:5432/dndsheet`;
  - `migrate.env`: `DNDSHEET_DATABASE_URL=postgresql://dndsheet:<pw>@pg:5432/dndsheet` (owner).
    It is used only by the one-shot migration container and never reaches the app's environment.

  Passwords are generated (`python -c "import secrets; print(secrets.token_urlsafe(32))"`).
  Rotation is `ALTER ROLE … PASSWORD` plus an edit to the env file and a redeploy.
- **How it gets there.** The stack changes rarely, like the bootstrap, so it belongs with
  Terraform: a `terraform_data.postgres` that uploads `deploy/postgres/*` and runs
  `docker compose up -d` when their hash changes, plus the backup cron. A small
  `scripts/deploy_postgres.py` in the style of `deploy_app.py` works just as well. Pick one
  in step 1. The files in `deploy/postgres/` are ready either way.
- **Ownership.** While dnd-sheet is the only user, `deploy/postgres/` lives here. When the
  second project arrives, move it to a small infra repository: the shared server shouldn't
  live inside one app's repo.

## 3. Migrations

- **Tool:** numbered plain SQL plus `dndsheet/db/migrate.py` (~100 lines, no new
  dependency). Why not Alembic: without SQLAlchemy models its autogenerate doesn't help, and
  it would pull SQLAlchemy into the image for a version table and ordering. Why not
  dbmate or sqitch: one more binary in the image and the deploy, for the same features. The
  adapters already hand-write their SQL, and the migrations match that style.
- **Where and how named:** `backend/src/dndsheet/db/migrations/NNNN_snake_case.sql`
  (`0002_character_avatar_index.sql`). The number is the order. The runner refuses a file
  with a bad name or a duplicate number.
- **How they run:** `python -m dndsheet.db migrate` under the owner role, as a deploy step
  before `docker compose up -d`:

  ```bash
  docker run --rm --network pg --env-file /opt/dndsheet/migrate.env dndsheet:local \
    python -m dndsheet.db migrate
  ```

  Each file runs in its own transaction and is recorded in `schema_migrations` with its
  SHA-256. A failed file leaves nothing behind, and the deploy stops before the new app
  starts. An advisory lock means two runners never interleave (the lock is per database,
  so every project is independent). A file that can't run in a transaction
  (`CREATE INDEX CONCURRENTLY`) starts with `-- migrate: no-transaction` and holds one
  statement.
- **The app never migrates.** Its role can't run DDL. On start it checks that every
  migration it ships is applied, and refuses to start otherwise (`require_schema`). A
  newer migration in the database than in the image isn't an error, so rolling back to the
  previous image works.
- **Forward only.** There are no down migrations. A mistake is fixed by the next migration.
  A disaster is fixed by the backup. An applied file is never edited, and the checksum
  enforces that. Schema changes follow expand → deploy → contract: add a nullable column
  or new table, deploy code that uses it, and drop the old thing in a later release. That
  way the previous image keeps working against the new schema.
- **CI:** the `backend` job has a `postgres:18.7-alpine` service container. Every PostgreSQL
  test makes its own temporary schema, runs the real migrations into it and drops it
  (`backend/tests/db/conftest.py`). `DNDSHEET_REQUIRE_POSTGRES=1` makes a missing database
  fail the job instead of skipping 27 tests and quietly losing coverage.
- **Other projects** keep their own history inside their own database: our
  `schema_migrations`, Alembic's `alembic_version`, Flyway's table, whatever they choose.
  Nothing is shared, so there is nothing to coordinate.

## 4. Moving dnd-sheet off SQLite

The data is ~120 KB: copying it takes seconds. A **maintenance window of about 5 minutes**
is simpler and safer than any dual-write scheme. Dual-run would need writes to both stores
to be kept consistent, and conflicts reconciled, for a few hundred rows. It isn't worth it.

**The copy** (`python -m dndsheet.db copy-from-sqlite FILE`, owner role):

1. Opens the SQLite file read-only and immutable, without locks or side files, so a
   `:ro` mount works. Pass a `sqlite3 .backup` snapshot, never the live file. A file with a
   non-empty `-wal` next to it is refused, because the latest writes may still be in the
   WAL.
2. Finds rows that point at a missing user (SQLite never enforced its foreign keys) and
   stops. `--drop-orphans` skips them (sessions and tokens of nonexistent users are dead
   anyway), and the report says how many were skipped.
3. Refuses a target that already has data, unless `--replace`, which truncates first.
4. Inserts everything **in one transaction**, reads it back in the same transaction and
   compares, per table, the row count and the SHA-256 of the sorted canonical rows (JSON
   with sorted keys, UTC time to the millisecond, as SQLite stores it). Any difference
   rolls the whole transaction back, so the database is either a verified copy or
   untouched.
5. `verify FILE` repeats the comparison later without writing anything. It works under the
   app role too.

**Rehearsal** (done locally on test data, 2026-11-28): the app on SQLite created the
reference characters and a draft. The copy went into the shared-server configuration and
was verified. The app ran against it as `dndsheet_app` (list, sheet, share link). Then
`copy-to-sqlite` wrote it back and verified. Do the same on the server with last night's
backup, into a scratch database, before the real cutover (§ 9, step 5).

**Cutover runbook** (on the server, after steps 1–5 of § 9). The image with this code is
already deployed by then and still running on SQLite, because the URL isn't set yet:

```bash
cd /opt/dndsheet
# 1. Stop writes. Caddy keeps serving; the API answers 502 for a few minutes.
docker compose -f compose.yml stop app
# 2. A consistent snapshot (the same command the daily backup uses).
sqlite3 var/dndsheet.sqlite3 ".backup 'backups/dndsheet-cutover.sqlite3'"
# 3. Copy and verify, as the owner role, with the image that's about to run.
docker run --rm --network pg --env-file migrate.env -v /opt/dndsheet/backups:/backups:ro \
  dndsheet:local python -m dndsheet.db copy-from-sqlite /backups/dndsheet-cutover.sqlite3
# 4. Switch: DNDSHEET_DATABASE_URL (app role) in deploy/secrets/prod.env, then from the repo:
#    .\deploy\terraform\deploy.ps1 -NoBuild
# 5. Smoke test: sign in with Telegram, open a character, change something, open a share
#    link, reconnect the MCP client (a token refresh goes through oauth_tokens).
```

The SQLite file stays where it is, untouched and no longer written to. Keep it and the
daily SQLite backups for 30 days.

## 5. Rollback

| When | How | Data loss |
| --- | --- | --- |
| During the window, before step 4 | nothing to undo: start the app again (`docker compose start app`) | none |
| After the switch, nothing written yet | remove `DNDSHEET_DATABASE_URL` from `prod.env`, `deploy.ps1 -NoBuild` | none (the SQLite file is the same) |
| After users wrote to PostgreSQL | stop the app; `python -m dndsheet.db copy-to-sqlite /app/var/dndsheet-from-pg.sqlite3` (owner role); move it over `var/dndsheet.sqlite3` (`chown 10001`); remove the URL; deploy | none: the reverse copy is verified the same way |
| The database itself is broken | `pg_restore` last night's dump (§ 6), or the steps above from the restored database | since the last dump |

The reverse copy creates the SQLite schema with the SQLite adapters themselves, so the file
is exactly what the app would have made. It also marks `json_imported`, so the old JSON
files aren't imported a second time. It refuses to overwrite an existing file.

## 6. Backups, monitoring, upgrades

**Backups** (`deploy/postgres/backup.sh`, cron):

- Nightly (`/etc/cron.daily/pg-backup`): `pg_dump --format=custom` of every database,
  plus `pg_dumpall --globals-only --no-role-passwords` for roles and grants. Kept 14 days
  in `/opt/pg/backups` (mode 700). For this data size, logical dumps beat physical backups:
  they are portable across major versions, small, and restore per project.
- **Off-server copy:** missing today, for SQLite too (docs/deploy.md). The cheapest fit is
  Cloudflare R2 (the account is already in use for DNS; 10 GB free) with `rclone`, through
  `OFFSITE_CMD`. It needs an R2 token from the owner.
- **Restore test** weekly (`backup.sh check`, `/etc/cron.weekly/pg-restore-check`): restore
  each newest dump into a scratch database, check it has tables, drop it.
- **Dead man's switch:** `PING_URL` (healthchecks.io or similar, free) is pinged after a
  successful backup. A missed night then turns into an email.
- Both modes were run locally against the shared configuration with two projects
  (`PG_CONTAINER` and `PG_BACKUPS` override the container name and the folder).
- Physical backups and PITR (pgBackRest, WAL-G) aren't worth it until losing a day of data
  starts to matter. `wal_level=replica` already allows `pg_basebackup` or a standby later.

**Monitoring**, kept small:

- the `pg` container healthcheck (`pg_isready`) and `restart: unless-stopped`;
- the app refuses to start without its schema, and `deploy_app.py` already waits for
  `healthy`;
- `pg_stat_statements` is on, and statements slower than 500 ms go to `docker logs pg`;
- `backup.sh` fails loudly (cron mails root), and the ping covers silent failures;
- the next easy wins: disk-free and backup-age checks in the same cron, and later an
  external uptime check on `/healthz`.

**Upgrades:**

- **Minor** (18.7 → 18.8, security fixes, every quarter): change the tag in
  `deploy/postgres/compose.yml` and run `docker compose pull && docker compose up -d`.
  That's about 5 seconds of downtime and no data change.
- **Major** (18 → 19+, every few years): with megabytes of data, dump and restore is the
  simplest path. Take tonight's dumps, start the new major on an empty `data/`, load globals
  and the dumps, and switch. It's the restore test, done for real. `pg_upgrade --link`
  (e.g. the `pgautoupgrade` image) is the fallback if the data ever gets big. The builtin
  collation means no index rebuilds after an OS or image change.

## 7. Adding another project

1. Pick a slug (`myproj`): the database and roles will carry it.
2. Generate two passwords and put them in that project's git-crypt secrets.
3. Run `create-project.sql`:

   ```bash
   docker exec -i pg psql -U postgres -v ON_ERROR_STOP=1 -v project=myproj \
     -v owner_password="$OWNER_PW" -v app_password="$APP_PW" -f - < create-project.sql
   ```

4. In its compose file, join the network:
   `networks: { default: {}, pg: { external: true } }` and `networks: [default, pg]` on the
   service. Connect to `postgresql://myproj_app:…@pg:5432/myproj`.
5. Migrate with any tool, as the `myproj` role, as a deploy step. Its history stays in
   its own database.
6. Budget: `max_connections=40` in total. Each app role is capped at 10, so pools should
   stay small (5).

## 8. Experiments with other engines

The owner chose PostgreSQL 18 for the server and asked to keep these as experiments. Each
one can be tried **locally, behind the same ports**, like the PostgreSQL adapters: write
`<engine>_store.py` next to `postgres_store.py`, add it to the parametrized `stores` fixture
in `backend/tests/db/test_repositories.py` (the contract tests are the acceptance test), and
select it in `api/storage.py`. Then measure memory and disk under the same test suite with
`docker stats`. Nothing goes to the server until an engine passes the contract tests and
the owner decides.

| Engine | What to try | What it would take | Watch for |
| --- | --- | --- | --- |
| **Turso** (Rust SQLite, MIT, pre-1.0) | the SQLite adapters with `pyturso` instead of `sqlite3`, and `BEGIN CONCURRENT` for parallel saves | small, if its Python API is close enough to `sqlite3` (to check); otherwise a thin wrapper | embedded only (no shared server); pre-1.0 file-format stability; its Postgres protocol is experimental |
| **SurrealDB** (document + graph, Rust, BSL 1.1) | characters and drafts as documents, owners as links. Later maybe party, campaign and character graphs | a new adapter set (SurrealQL), optimistic versioning via conditional `UPDATE … WHERE version < $v` | memory of a second server (no published figures: measure); BSL terms; OAuth tables fit a relational shape better |
| **FerretDB** (MongoDB API on Postgres + DocumentDB, Apache-2.0) | the character store through `pymongo` against FerretDB, with data still in Postgres | a Mongo-style adapter; a Postgres image with the DocumentDB extension (`ghcr.io/ferretdb/…`), not stock `postgres` | project activity (last commit on main 2026-02, last release 2025-11); coupling the shared server to a special image |
| **Valkey** (key-value, BSD-3) | sessions, OAuth requests and codes with native TTL (`SET … EX`), no purge job | a `SessionStore`/`OAuthStore` adapter, partly: grants and token families are relational queries | a second server and second backup for data that's tiny; persistence settings (AOF) so sessions survive restarts |

pgrust isn't on this list by the owner's choice. ADR 0006 records why, and what would
make it worth another look.

## 9. Steps and effort

Estimates are focused working time for one person who knows this repository.

| # | Step | Effort | Needs the owner |
| --- | --- | --- | --- |
| 0 | Prototype: adapters, migrations, copy/verify, tests, CI (this branch) | done | review |
| 1 | Secrets (`postgres.env`, `migrate.env`, URL in `prod.env`); choose Terraform or a script for `deploy/postgres`; bring the `pg` stack up on the VPS | 2–3 h | OK to touch the server and the secrets |
| 2 | `create-project.sql` for `dndsheet`; check the roles on the server as in § 2 | 0.5 h | — |
| 3 | App compose joins the external `pg` network; `deploy_app.py` runs the migration container before `up -d` (only when `migrate.env` exists) | 1–2 h | — |
| 4 | `backup.sh` in cron (daily and weekly check), `PING_URL`, R2 off-site copy | 2–3 h | an R2 token, a healthchecks.io URL |
| 5 | Rehearsal on the server: last night's SQLite backup → `dndsheet_rehearsal`, verify, drop | 0.5–1 h | — |
| 6 | Cutover (§ 4), smoke test | 0.5 h (≈5 min downtime) | a time slot |
| 7 | Watch for 2–4 weeks; then drop the SQLite code paths and the SQLite backup cron, or keep them for local single-user runs | 1–2 h | the call to remove |
| | **Remaining** | **≈ 1–1.5 days** | |

## 10. Local development and tests

Without `DNDSHEET_TEST_DATABASE_URL`, the PostgreSQL tests are skipped (27 of them), and
everything else runs as before. To run them, start a throwaway Postgres. Use a Docker
volume, not a bind mount on Windows (Postgres rejects the permissions), and a password from
`logs/` (gitignored):

```bash
docker run -d --name dndsheet-pg-proto --env-file logs/pg-proto/.env \
  -p 127.0.0.1:55432:5432 -v dndsheet-pg-proto:/var/lib/postgresql postgres:18.7-alpine
export DNDSHEET_TEST_DATABASE_URL="postgresql://postgres:<password>@127.0.0.1:55432/postgres"
PYTHONUTF8=1 .venv/Scripts/python -m pytest backend -q -p no:cacheprovider
```

To run the app on it: create a database, `python -m dndsheet.db --url … migrate`, then start
the app with `DNDSHEET_DATABASE_URL` set. `python -m dndsheet.db copy-from-sqlite` moves a
SQLite file into it. Use a copy of test data, never the real `var/`.

To try the shared-server configuration itself, copy `deploy/postgres/` into
`logs/pg-shared/`, add a `.env` with `POSTGRES_PASSWORD`, and add a `compose.override.yml`
with a named volume and a loopback port. Then run `create-project.sql` as in § 7.
