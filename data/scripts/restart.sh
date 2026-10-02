#!/bin/bash
# MasterChief - Restart Platform
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common/functions.sh"

print_banner "Restarting MasterChief Platform"

# Stop if running
if is_platform_running; then
    log_info "Stopping platform..."
    "$SCRIPT_DIR/stop.sh"
    sleep 2
fi

# Start platform
log_info "Starting platform..."
"$SCRIPT_DIR/start.sh" --daemon
