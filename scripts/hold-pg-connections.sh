#!/bin/sh
# Hold <count> idle Postgres connections for <seconds> to cause a controlled,
# demo-only threshold crossing of postgresql connection usage.
#
# Usage: scripts/hold-pg-connections.sh <count> <seconds> [--dry-run]
# Env:   PG_CONTAINER (required); PGUSER, PGDATABASE, PGPASSWORD are passed into
#        the container by name only, so their values never appear in argv or output.
#
# Every session sets application_name=hold-pg-connections. On exit, Ctrl-C or
# TERM the script kills its docker exec clients and also terminates those
# sessions server-side, because killing `docker exec` does not end psql in the
# container.
set -u

APP=hold-pg-connections

die() {
  printf 'error: %s\n' "$1" >&2
  exit 1
}

is_pos_int() {
  case "$1" in
    '' | *[!0-9]*) return 1 ;;
  esac
  [ "$1" -gt 0 ]
}

[ $# -ge 2 ] && [ $# -le 3 ] || die "usage: $0 <count> <seconds> [--dry-run]"
count=$1
seconds=$2
dry_run=0
if [ $# -eq 3 ]; then
  [ "$3" = "--dry-run" ] || die "unknown option: $3"
  dry_run=1
fi
is_pos_int "$count" || die "count must be a positive integer"
is_pos_int "$seconds" || die "seconds must be a positive integer"
[ -n "${PG_CONTAINER:-}" ] || die "missing env: PG_CONTAINER"

query() {
  docker exec -e PGUSER -e PGDATABASE -e PGPASSWORD "$PG_CONTAINER" psql -tAc "$1"
}

max=$(query "show max_connections" | tr -d '[:space:]') || die "could not read max_connections"
current=$(query "select count(*) from pg_stat_activity" | tr -d '[:space:]') || die "could not read the current connection count"
is_pos_int "$max" || die "unexpected max_connections value"
case "$current" in '' | *[!0-9]*) die "unexpected connection count value" ;; esac

if [ $((current + count)) -ge "$max" ]; then
  die "refusing: would exceed max_connections (current $current + $count >= $max)"
fi

printf 'max_connections=%s current=%s holding=%s for %ss (usage about %s%%)\n' \
  "$max" "$current" "$count" "$seconds" "$(((current + count) * 100 / max))"

session_cmd="docker exec -e PGUSER -e PGDATABASE -e PGPASSWORD -e PGAPPNAME=$APP $PG_CONTAINER psql -c \"select pg_sleep($seconds)\""

if [ "$dry_run" -eq 1 ]; then
  i=0
  while [ "$i" -lt "$count" ]; do
    printf 'DRY-RUN %s\n' "$session_cmd"
    i=$((i + 1))
  done
  exit 0
fi

pids=""
cleanup() {
  trap - EXIT INT TERM
  if [ -n "$pids" ]; then
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null
    query "select pg_terminate_backend(pid) from pg_stat_activity where application_name = '$APP' and pid <> pg_backend_pid()" >/dev/null 2>&1
    wait 2>/dev/null
    pids=""
  fi
}
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM
trap cleanup EXIT

i=0
while [ "$i" -lt "$count" ]; do
  docker exec -e PGUSER -e PGDATABASE -e PGPASSWORD -e PGAPPNAME="$APP" "$PG_CONTAINER" \
    psql -c "select pg_sleep($seconds)" >/dev/null 2>&1 &
  pids="$pids $!"
  i=$((i + 1))
done

wait
pids=""
printf 'released %s connections\n' "$count"
