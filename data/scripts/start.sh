#!/bin/bash
# MasterChief - Start Platform
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common/functions.sh"

print_banner "Starting MasterChief Platform"

# Load environment
load_environment

# Check if already running
if is_platform_running; then
    log_warn "Platform is already running"
    log_info "Use './scripts/restart.sh' to restart or './scripts/stop.sh' to stop first"
    exit 1
fi

# Change to project root
cd "$PROJECT_ROOT"

# Check for Python
PYTHON=$(find_python)
log_info "Using Python: $PYTHON"

# Check if dependencies are installed
if ! $PYTHON -c "import flask" 2>/dev/null; then
    log_warn "Dependencies not installed"
    log_info "Installing dependencies..."
    $PYTHON -m pip install -r requirements.txt
fi

# Start the platform
log_info "Starting MasterChief platform..."

# Run in background or foreground based on argument
if [[ "${1:-}" == "--daemon" || "${1:-}" == "-d" ]]; then
    log_info "Starting in daemon mode..."
    nohup $PYTHON run.py > logs/masterchief.log 2>&1 &
    PID=$!
    echo $PID > data/masterchief.pid
    log_success "Platform started with PID: $PID"
    log_info "Logs: tail -f logs/masterchief.log"
    
    # Wait a bit and verify it started
    sleep 2
    if wait_for_platform 10; then
        log_success "Platform is running!"
    else
        log_error "Platform failed to start. Check logs/masterchief.log"
        exit 1
    fi
else
    log_info "Starting in foreground mode..."
    log_info "Press Ctrl+C to stop"
    $PYTHON run.py
fi
