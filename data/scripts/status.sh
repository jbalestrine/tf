#!/bin/bash
# MasterChief - Platform Status
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common/functions.sh"

print_banner "MasterChief Platform Status"

# Check if running
if is_platform_running; then
    log_success "Platform is RUNNING"
    
    # Get PID
    PID=$(get_platform_pid)
    if [[ -n "$PID" ]]; then
        log_info "PID: $PID"
    fi
    
    # Get status from API
    log_info "Fetching platform status..."
    STATUS=$(get_platform_status 2>/dev/null)
    
    if [[ -n "$STATUS" ]]; then
        echo "$STATUS" | python3 -m json.tool 2>/dev/null || echo "$STATUS"
    else
        log_warn "Could not fetch status from API"
    fi
    
    # Port info
    local port="${PORT:-8080}"
    log_info "Web UI: http://localhost:$port"
    log_info "API: http://localhost:$port/api/v1"
    
else
    log_error "Platform is NOT RUNNING"
    log_info "Start with: ./scripts/start.sh"
    exit 1
fi
