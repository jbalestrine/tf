#!/bin/bash
# MasterChief - Stop Platform
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common/functions.sh"

print_banner "Stopping MasterChief Platform"

# Check if running
if ! is_platform_running; then
    log_warn "Platform is not running"
    exit 0
fi

# Get PID
PID=$(get_platform_pid)

if [[ -z "$PID" ]]; then
    log_warn "Could not determine platform PID"
    exit 1
fi

log_info "Stopping platform (PID: $PID)..."

# Send SIGTERM
kill -TERM $PID 2>/dev/null || true

# Wait for graceful shutdown
for i in {1..10}; do
    if ! is_platform_running; then
        log_success "Platform stopped successfully"
        rm -f "$PROJECT_ROOT/data/masterchief.pid"
        exit 0
    fi
    sleep 1
done

# Force kill if still running
log_warn "Platform did not stop gracefully, forcing..."
kill -KILL $PID 2>/dev/null || true
rm -f "$PROJECT_ROOT/data/masterchief.pid"

log_success "Platform stopped (forced)"
