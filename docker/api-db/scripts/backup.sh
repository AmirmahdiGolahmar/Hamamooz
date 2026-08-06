#!/bin/sh

set -e

echo "[backup] $(date -Iseconds) starting backup service"

export PGPASSWORD="$POSTGRES_PASSWORD"
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-7}

while true; do
    TIMESTAMP=$(date +"%Y%m%d%H%M%S")
    FILE="/backups/${POSTGRES_DB}_${TIMESTAMP}.dump"

    echo "[backup] $(date -Iseconds) starting dump -> ${FILE}"

    pg_dump -h "$PGHOST" -p "$PGPORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -F c -f "$FILE"

    echo "[backup] $(date -Iseconds) dump complete ($(du -h "$FILE" | cut -f1))"

    find /backups -name "${POSTGRES_DB}_*.dump" -mtime +"${RETENTION_DAYS}" -delete

    sleep 86400
done