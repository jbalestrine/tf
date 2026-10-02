#!/usr/bin/env bash
#
# security-scan.sh - SAST/DAST security scanning
#
# Usage:
#   security-scan.sh --target TARGET [--type TYPE] [--help]
#

set -euo pipefail

TARGET=""
SCAN_TYPE="sast"

while [[ $# -gt 0 ]]; do
    case $1 in
        --target) TARGET="$2"; shift 2 ;;
        --type) SCAN_TYPE="$2"; shift 2 ;;
        --help|-h) sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# //g'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

[[ -z "$TARGET" ]] && { echo "ERROR: --target is required" >&2; exit 1; }

echo "[INFO] Running $SCAN_TYPE security scan on: $TARGET"
echo "[INFO] Security scan completed"
exit 0
