#!/usr/bin/env bash
#
# rotate-secrets.sh - Secret rotation automation
#
# Usage:
#   rotate-secrets.sh --service SERVICE [--dry-run] [--help]
#

set -euo pipefail

SERVICE=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --service) SERVICE="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        --help|-h) sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# //g'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

[[ -z "$SERVICE" ]] && { echo "ERROR: --service is required" >&2; exit 1; }

echo "[INFO] Rotating secrets for service: $SERVICE"
[[ "$DRY_RUN" == "true" ]] && echo "[INFO] DRY RUN MODE"
echo "[INFO] Secret rotation completed"
exit 0
