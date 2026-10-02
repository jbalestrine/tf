#!/bin/bash
# MasterChief - Health Check
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common/functions.sh"

print_banner "MasterChief Health Check"

EXIT_CODE=0

# Check if platform is running
log_info "Checking if platform is running..."
if is_platform_running; then
    log_success "✓ Platform is running"
else
    log_error "✗ Platform is not running"
    EXIT_CODE=1
fi

# Check API health endpoint
log_info "Checking API health..."
HEALTH=$(get_platform_status 2>/dev/null)
if [[ $? -eq 0 && -n "$HEALTH" ]]; then
    log_success "✓ API is responding"
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"
else
    log_error "✗ API is not responding"
    EXIT_CODE=1
fi

# Check required directories
log_info "Checking directories..."
for dir in data logs plugins backups; do
    if [[ -d "$PROJECT_ROOT/$dir" ]]; then
        log_success "✓ Directory exists: $dir"
    else
        log_error "✗ Missing directory: $dir"
        EXIT_CODE=1
    fi
done

# Check Python dependencies
log_info "Checking Python dependencies..."
PYTHON=$(find_python)
REQUIRED_PACKAGES=("flask" "flask_socketio" "flask_cors" "jinja2" "pyyaml")

for package in "${REQUIRED_PACKAGES[@]}"; do
    if $PYTHON -c "import ${package}" 2>/dev/null; then
        log_success "✓ Package installed: $package"
    else
        log_error "✗ Missing package: $package"
        EXIT_CODE=1
    fi
done

# Summary
echo ""
if [[ $EXIT_CODE -eq 0 ]]; then
    log_success "All health checks passed!"
else
    log_error "Some health checks failed"
fi

exit $EXIT_CODE
