#!/usr/bin/env bash
#
# check-health.sh - Health endpoint checker
#
# Usage:
#   check-health.sh --url URL [--timeout SECONDS] [--help]
#

set -euo pipefail

URL=""
TIMEOUT=30

while [[ $# -gt 0 ]]; do
    case $1 in
        --url) URL="$2"; shift 2 ;;
        --timeout) TIMEOUT="$2"; shift 2 ;;
        --help|-h) sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# //g'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

[[ -z "$URL" ]] && { echo "ERROR: --url is required" >&2; exit 1; }

echo "[INFO] Checking health of: $URL"
if command -v curl &> /dev/null; then
    if curl -sf --max-time "$TIMEOUT" "$URL" > /dev/null; then
        echo "[SUCCESS] Health check passed"
        exit 0
    else
        echo "[FAILED] Health check failed"
        exit 1
    fi
else
    echo "[WARN] curl not found, skipping health check"
    exit 0
fi
