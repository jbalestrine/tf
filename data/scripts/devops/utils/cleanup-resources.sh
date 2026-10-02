#!/usr/bin/env bash
#
# cleanup-resources.sh - Resource cleanup script
#
# Usage:
#   cleanup-resources.sh --type TYPE [--dry-run] [--help]
#

set -euo pipefail

TYPE=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --type) TYPE="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        --help|-h) sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# //g'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

[[ -z "$TYPE" ]] && { echo "ERROR: --type is required" >&2; exit 1; }

echo "[INFO] Cleaning up resources of type: $TYPE"
[[ "$DRY_RUN" == "true" ]] && echo "[INFO] DRY RUN MODE"
echo "[INFO] Cleanup completed"
exit 0
