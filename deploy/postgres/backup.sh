#!/bin/sh
# Logical backups of every database on the shared PostgreSQL (docs/database.md).
#
#   backup.sh            nightly (/etc/cron.daily/pg-backup): one pg_dump per database + roles
#   backup.sh check      weekly: restore each newest dump into a scratch database, then drop it
#
# Dumps land in /opt/pg/backups (root only), 14 daily copies. They are on the same disk as the
# data, so an off-server copy (OFFSITE_CMD, e.g. rclone to Cloudflare R2) is strongly advised.
set -eu

ROOT=${PG_BACKUPS:-/opt/pg/backups}
KEEP_DAYS=${PG_KEEP_DAYS:-14}
DAY=$(date +%F)
PG=${PG_CONTAINER:-pg}
PSQL="docker exec -i $PG psql -U postgres -v ON_ERROR_STOP=1 -Atq"

databases() {
  $PSQL -c "SELECT datname FROM pg_database WHERE datallowconn AND NOT datistemplate AND datname <> 'postgres' ORDER BY 1"
}

backup() {
  umask 077
  mkdir -p "$ROOT"
  # Roles and grants, without password hashes: passwords live in git-crypt (deploy/secrets).
  docker exec "$PG" pg_dumpall -U postgres --globals-only --no-role-passwords >"$ROOT/globals-$DAY.sql.tmp"
  mv "$ROOT/globals-$DAY.sql.tmp" "$ROOT/globals-$DAY.sql"
  for db in $(databases); do
    docker exec "$PG" pg_dump -U postgres --format=custom --compress=6 "$db" >"$ROOT/$db-$DAY.dump.tmp"
    mv "$ROOT/$db-$DAY.dump.tmp" "$ROOT/$db-$DAY.dump"
  done
  find "$ROOT" \( -name '*.dump' -o -name 'globals-*.sql' \) -mtime +"$KEEP_DAYS" -delete
  if [ -n "${OFFSITE_CMD:-}" ]; then
    sh -c "$OFFSITE_CMD"
  fi
  # Dead man's switch: a missed night shows up as a missing ping (healthchecks.io or similar).
  if [ -n "${PING_URL:-}" ]; then
    curl -fsS -m 10 --retry 3 "$PING_URL" >/dev/null || true
  fi
}

check() {
  for db in $(databases); do
    # File names carry an ISO date, so the last one in sort order is the newest.
    dump=$(find "$ROOT" -maxdepth 1 -name "$db-*.dump" | sort | tail -n 1)
    [ -n "$dump" ] || {
      echo "no dump for $db" >&2
      exit 1
    }
    scratch="restorecheck_$db"
    $PSQL -c "DROP DATABASE IF EXISTS $scratch" -c "CREATE DATABASE $scratch"
    docker exec -i "$PG" pg_restore -U postgres --no-owner --no-acl --exit-on-error -d "$scratch" <"$dump"
    count="SELECT count(*) FROM pg_tables WHERE schemaname = 'public'"
    tables=$($PSQL -d "$scratch" -c "$count")
    live=$($PSQL -d "$db" -c "$count")
    $PSQL -c "DROP DATABASE $scratch"
    # A project without tables yet is fine; a dump that lost them all is not.
    if [ "$live" -gt 0 ] && [ "$tables" -eq 0 ]; then
      echo "$db: the restored dump has no tables, the live database has $live" >&2
      exit 1
    fi
    echo "$db: restored $(basename "$dump"), $tables tables"
  done
}

case "${1:-backup}" in
  backup) backup ;;
  check) check ;;
  *)
    echo "usage: $0 [backup|check]" >&2
    exit 2
    ;;
esac
