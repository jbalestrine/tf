#!/bin/bash
# MasterChief - View Logs
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common/functions.sh"

LOG_FILE="$PROJECT_ROOT/logs/masterchief.log"

# Create log file if it doesn't exist
touch "$LOG_FILE"

# Follow logs by default, or show last N lines
if [[ "${1:-}" == "--tail" || "${1:-}" == "-n" ]]; then
    LINES="${2:-100}"
    log_info "Showing last $LINES lines..."
    tail -n "$LINES" "$LOG_FILE"
else
    log_info "Following logs (Ctrl+C to stop)..."
    tail -f "$LOG_FILE"
fi
