#!/bin/sh

set -e

# Check empty argument
if [ -z "$1" ]; then
    echo "Usage: $0 <path-to-dump-file>"
    exit 1
fi

DUMP_FILE="$1"

# Check if dump file exists
if [ ! -f "$DUMP_FILE" ]; then
    echo "File not found: $DUMP_FILE"
    exit 1
fi

# Load POSTGRES_* vars from .env if not already set in the shell
if [ -f .env ]; then
    set -a
    . ./.env
    set +a
fi

echo "Restoring $DUMP_FILE into database '${POSTGRES_DB}'..."
read -p "Continue? [y/N] " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Aborted."
    exit 1
fi

cat "$DUMP_FILE" | docker compose exec -T db pg_restore \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists

echo "Restore complete."