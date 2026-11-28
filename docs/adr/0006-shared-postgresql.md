# ADR 0006 — One shared PostgreSQL 18 for all projects on the VPS

Status: accepted (engine: PostgreSQL 18, chosen by the owner 2026-11-28). Implemented so far:
a local prototype (adapters, migrations, copy script, tests, CI). Not deployed yet. The plan
and the runbook are in [`docs/database.md`](../database.md).

## Context

dnd-sheet keeps everything in one SQLite file (`var/dndsheet.sqlite3`, WAL): characters and
drafts as JSON documents with an owner and a version, share links, users and sessions, and
the OAuth data of the MCP server (ADR 0005). It works, and the data is tiny (120 KB on
2026-11-28). The trigger is different: **the same server will host other pet projects**, and
the VPS is small, so they should share one database server instead of each bringing its own.

The box, measured over SSH on 2026-11-28:

| | |
| --- | --- |
| CPU / RAM | 2 vCPU, 2.4 GiB (1.85 GiB available), swap 3.3 GiB (2 GB file + 1.3 GB partition) |
| Disk | 29 GB, 21 GB free |
| Running | `dndsheet-app` 146 MiB, `dndsheet-caddy` 15 MiB, dockerd + containerd ~110 MiB |
| OS | Ubuntu 24.04, Docker 29.10 |

Requirements: low memory, crash-safe, works with psycopg 3 / SQLAlchemy / any migration tool,
real backups and restores, one database and least-privilege roles per project, no public
port, a boring upgrade path. The domain must not change: storage stays behind the existing
ports (`characters/domain/ports.py`, `identity/domain/ports.py`, `identity/domain/oauth.py`),
which import-linter enforces.

## Options

### PostgreSQL 18 (chosen)

The default for a reason: every driver, ORM and migration tool, `pg_dump`/`pg_restore`,
30 years of crash-safety work, five years of minor releases per major. Measured locally in
Docker (`postgres:18.7-alpine`, the tuning from `deploy/postgres/postgresql.conf`):
**~55–70 MiB RSS idle and after the test suite**, a 39 MB empty data directory and a ~0.4 GB image. Runs
inside a 512 MB container limit without strain. PG 19 is out too, but 18 is in its second
year of minor releases, and it's the version pgrust targets, so a later experiment can point
at the same data.

### pgrust (evaluated, not chosen now)

Read from the repository itself (github.com/malisper/pgrust, 2026-11-28):

- **What it is:** Postgres 18.6 rewritten in Rust, wire- and SQL-compatible, same on-disk
  format as stock PG 18; threads instead of processes; a JIT-compiled vectorized engine
  ("Gravity"); columnar tables; one automatic memory budget. Built-in pgvector, pg_cron,
  pg_stat_statements, pgcrypto, postgres_fdw and most of contrib. C extensions can't load,
  and PL/Python, PL/Perl and PL/Tcl aren't supported.
- **Maturity:** v0.4-beta (2026-10-22), "targeting production readiness in Q1 2027". The v0.3 release said to try it on real workloads "in non-critical environments".
  Six tags since 2026-06. Development became public with v0.4. External PRs aren't
  accepted. AGPL-3.0. 6.1k stars, 70 open issues.
- **Docker:** `malisper/pgrust:v0.4-beta`, a drop-in for the official image (same env vars,
  init scripts and volume), ~96 MB compressed. `latest` still points at v0.3.
- **Open problems that matter here** (issue numbers in that repo):
  #173: the server was OOM-killed during single-client DDL on empty tables while running
  a real app's migrations. #137: 3–4× the memory of PG 18 (224 MiB idle vs 57 MiB) on a
  Django suite. #164, #144, #180: v0.4's engine refuses some ordinary statements with
  `0A000` and has no fallback executor (job-queue `FOR UPDATE SKIP LOCKED` shapes, writable
  CTEs, ORM schema introspection through `information_schema`). #172: initdb reports
  success when an fsync failed. #67 (closed): thread-per-backend weakens crash isolation.
- **Fit:** its strength is analytics on large tables, which we don't have. Its risks are
  memory, migrations and durability, which are exactly what a shared 2.4 GiB box needs.

Verdict: not for this server now. Revisit after a release the project itself calls
production-ready. Because it speaks the same protocol and reads a PG 18 data directory, that
would be a configuration change, not a code change.

### SQLite per project (kept as an option for small projects)

Zero memory, zero ops, already working, and `sqlite3 .backup` is fine for this size. It
doesn't give a shared server, concurrent writers across processes, network access for a
second service, or roles. It stays a valid choice for a tiny project that doesn't need
those; Litestream (Apache-2.0, beta label) would add off-server replication.

### Other engines worth an experiment (owner asked to keep them in the plan)

Status checked on their GitHub pages on 2026-11-28. None of them replaces PostgreSQL as the shared server.
`docs/database.md` § Experiments says how to try each one behind the same ports.

| Engine | Kind | Status / licence | Why try it here | Why not the shared server |
| --- | --- | --- | --- | --- |
| **Turso** (tursodatabase/turso) | SQLite rewritten in Rust, embedded | v0.8.4 (2026-11-20), "not yet 1.0", MIT; MVCC `BEGIN CONCURRENT`; Python `pyturso`; Postgres protocol experimental | The closest relative of pgrust on the SQLite side; concurrent writes without a server | Embedded, not a server; pre-1.0 |
| **SurrealDB** | document + graph, Rust | v4.0.1 (2026-11), core BSL 1.1, Python SDK | A character is a document. A graph would suit party, campaign and character links | Another server and query language, BSL licence, no footprint figures published |
| **FerretDB** | MongoDB API on Postgres | v2.7.0 (2025-11), Apache-2.0; needs Postgres with Microsoft's DocumentDB extension | A document API on top of the same Postgres data | Needs a non-stock Postgres image. Last commit on main 2026-02 |
| **Valkey** | key-value (Redis fork) | 9.2.1 (2026-11), BSD-3 | Sessions and OAuth codes are TTL data, a natural key-value fit | A second server for data Postgres already holds well |

Also looked at, briefly: rqlite (Raft-replicated SQLite, MIT, v10.8, overkill on one node);
Doltgres (Postgres-compatible with git-style versioning, Apache-2.0, "1.0, ready for
production", which is interesting for character history); OrioleDB (Postgres storage engine,
"not recommended for production"); PGlite (Postgres in WASM, alpha, one connection, JS);
CouchDB; PocketBase (repository archived 2026-10).

## Decision

1. **One PostgreSQL 18 instance per VPS, shared by all projects**, as its own compose
   project `pg` (`deploy/postgres/`), separate from each app's compose, so app deploys never
   restart the database. It has a 512 MB memory limit and small-box tuning. Data lives in a
   host folder (`/opt/pg/data`). The builtin `C.UTF-8` collation can't change under an OS
   upgrade.
2. **No public port.** Projects in Docker reach it as `pg:5432` on the external network
   `pg`. A non-Docker project on the host would use a loopback-only published port. The
   superuser connects only over the socket inside the container.
3. **Per project: one database and two roles.** `<project>` owns the schema and runs
   migrations. `<project>_app` gets data access only, with a connection limit and a statement
   timeout. CONNECT is revoked from PUBLIC, so projects can't see each other's databases
   (`deploy/postgres/create-project.sql`, verified locally).
4. **The same ports, a second adapter set.** `characters/infrastructure/postgres_store.py`,
   `identity/infrastructure/postgres_identity.py` and `identity/infrastructure/postgres_oauth.py`
   implement exactly what the SQLite adapters implement. `api/storage.py` picks one by
   `DNDSHEET_DATABASE_URL`, and SQLite stays the default. The same contract tests run on
   both (`backend/tests/db/test_repositories.py`).
5. **Character and draft documents are `jsonb`.** The schema doesn't mirror the aggregate, so
   new JSON fields (avatars, custom features) need no migration. Equality checks for "nothing
   changed" compare `jsonb`, not text.
6. **Migrations are numbered plain SQL with a ~100-line runner** (`dndsheet/db/migrate.py`).
   They run forward only, one transaction per file, behind an advisory lock, and a checksum
   guards files already applied. The deploy runs them as the owner role. The app only checks
   that they are applied. Each project keeps its own history inside its own database.
7. **Driver: psycopg 3** with `psycopg_pool`. It's synchronous, like the current handlers
   (FastAPI runs them in a thread pool), and uses a small pool (5).
8. **Cutover by a short maintenance window**, with a copy that verifies itself (row counts +
   SHA-256 per table) inside the copying transaction, and a verified reverse copy for rollback.

## Consequences

- About 60 MiB more RAM on the box, and a second thing to back up, monitor and upgrade. In
  return every next project gets a database by running one script.
- The app image grows by psycopg's binary wheel (a few MB). A deploy gains one step: the
  migration run.
- Both storage backends are kept for a while, until PostgreSQL has run in production without
  rollback; then the SQLite adapters can go (or stay for local single-user runs).
- No ORM and no Alembic: the SQL in the adapters stays explicit, as it is today. The cost is
  that migrations are hand-written, which they would be for this schema anyway. Another
  project on the server may pick Alembic or anything else: its history lives in its own
  database.
- CI runs the PostgreSQL tests against a `postgres:18.7-alpine` service, and a skipped
  PostgreSQL test fails the job there.
