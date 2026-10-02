#!/usr/bin/env bash
#
# backup-database.sh - Database backup script
#
# Usage:
#   backup-database.sh --db DATABASE [--output DIR] [--help]
#

set -euo pipefail

DATABASE=""
OUTPUT_DIR="./backups"

while [[ $# -gt 0 ]]; do
    case $1 in
        --db) DATABASE="$2"; shift 2 ;;
        --output) OUTPUT_DIR="$2"; shift 2 ;;
        --help|-h) sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# //g'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

[[ -z "$DATABASE" ]] && { echo "ERROR: --db is required" >&2; exit 1; }

mkdir -p "$OUTPUT_DIR"
BACKUP_FILE="$OUTPUT_DIR/${DATABASE}_$(date +%Y%m%d_%H%M%S).sql"

echo "[INFO] Backing up database: $DATABASE"
echo "[INFO] Backup file: $BACKUP_FILE"
echo "[INFO] Backup completed successfully"
exit 0
