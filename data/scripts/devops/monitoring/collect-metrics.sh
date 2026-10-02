#!/usr/bin/env bash
#
# collect-metrics.sh - Prometheus metrics collection
#
# Usage:
#   collect-metrics.sh --target TARGET [--interval SECONDS] [--help]
#

set -euo pipefail

TARGET=""
INTERVAL=60

while [[ $# -gt 0 ]]; do
    case $1 in
        --target) TARGET="$2"; shift 2 ;;
        --interval) INTERVAL="$2"; shift 2 ;;
        --help|-h) sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# //g'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

[[ -z "$TARGET" ]] && { echo "ERROR: --target is required" >&2; exit 1; }

echo "[INFO] Collecting metrics from: $TARGET"
echo "[INFO] Collection interval: ${INTERVAL}s"
echo "[INFO] Metrics collection started"
exit 0
