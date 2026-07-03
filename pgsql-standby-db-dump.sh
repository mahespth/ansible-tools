#!/usr/bin/bash

# Pause WAL while dumping a standby db
# we want to backup the standby database but because we have wal
# WAL active it will produce a conflict error.
#
# Steve Maher
# -------------------------------------------------

set -uo pipefail

STANDBY_HOST="standby-db"
DB="awx"
BACKUP_DIR="/backups/postgres"
TS="$(date +%Y%m%d_%H%M%S)"

FINAL="${BACKUP_DIR}/${DB}_${TS}.dump.zst"
TMP="${FINAL}.tmp"
LOG="${FINAL}.log"

PSQL="psql -h ${STANDBY_HOST} -d postgres -v ON_ERROR_STOP=1 -At"

resume_replay() {
  ${PSQL} -c "select pg_wal_replay_resume();" >/dev/null 2>&1 || true
}

rm -f "$TMP"
trap resume_replay EXIT INT TERM

# Confirm this is actually a standby.
IS_STANDBY="$(${PSQL} -c "select pg_is_in_recovery();")"

if [[ "$IS_STANDBY" != "t" ]]; then
  echo "Refusing to use standby backup mode: target is not in recovery" >&2
  exit 1
fi

# Pause WAL replay.
${PSQL} -c "select pg_wal_replay_pause();" >/dev/null

# Wait until it is really paused.
while true; do
  STATE="$(${PSQL} -c "select pg_get_wal_replay_pause_state();")"
  [[ "$STATE" == "paused" ]] && break
  sleep 1
done

echo "WAL replay paused on standby"

nice -n 10 ionice -c2 -n7 \
  pg_dump \
    -h "$STANDBY_HOST" \
    --format=custom \
    --compress=0 \
    --dbname="$DB" \
    2>"$LOG" \
| nice -n 10 ionice -c2 -n7 \
  zstd -3 -T0 -o "$TMP"

rc_pg_dump=${PIPESTATUS[0]}
rc_zstd=${PIPESTATUS[1]}

# Resume as soon as the dump stream has finished.
resume_replay
trap - EXIT INT TERM

if (( rc_pg_dump != 0 || rc_zstd != 0 )); then
  echo "Backup failed: pg_dump=$rc_pg_dump zstd=$rc_zstd" >&2
  echo "See log: $LOG" >&2
  rm -f "$TMP"
  exit 1
fi

zstd -t "$TMP" || {
  echo "zstd validation failed" >&2
  rm -f "$TMP"
  exit 1
}

zstd -dc "$TMP" | pg_restore --list >/dev/null || {
  echo "pg_restore archive validation failed" >&2
  rm -f "$TMP"
  exit 1
}

mv "$TMP" "$FINAL"

echo "Backup complete: $FINAL"
