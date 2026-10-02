#!/bin/bash
# Common functions for all MasterChief scripts
# Source this file in all scripts: source "$(dirname "$0")/../common/functions.sh"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load environment
load_environment() {
    local env="${MASTERCHIEF_ENV:-local}"
    local env_file="$PROJECT_ROOT/config/environments/${env}.env"
    
    if [[ -f "$env_file" ]]; then
        set -a
        source "$env_file"
        set +a
        log_info "Loaded environment: $env"
    fi
}

# Logging functions
log_info() { 
    echo -e "${BLUE}[INFO]${NC} $1" 
}

log_success() { 
    echo -e "${GREEN}[SUCCESS]${NC} $1" 
}

log_warn() { 
    echo -e "${YELLOW}[WARN]${NC} $1" 
}

log_error() { 
    echo -e "${RED}[ERROR]${NC} $1" 
}

log_debug() {
    if [[ "${DEBUG:-false}" == "true" ]]; then
        echo -e "${CYAN}[DEBUG]${NC} $1"
    fi
}

# Check dependencies
require_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "Required command not found: $1"
        log_info "Please install $1 and try again"
        exit 1
    fi
}

# Check if platform is running
is_platform_running() {
    local port="${PORT:-8080}"
    if command -v lsof &> /dev/null; then
        lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1
    else
        # Fallback method
        curl -s "http://localhost:$port/api/v1/health" > /dev/null 2>&1
    fi
}

# Wait for platform to be ready
wait_for_platform() {
    local max_wait="${1:-30}"
    local wait_time=0
    local port="${PORT:-8080}"
    
    log_info "Waiting for platform to be ready..."
    
    while [ $wait_time -lt $max_wait ]; do
        if curl -s "http://localhost:$port/api/v1/health" > /dev/null 2>&1; then
            log_success "Platform is ready!"
            return 0
        fi
        sleep 1
        wait_time=$((wait_time + 1))
    done
    
    log_error "Platform failed to start within ${max_wait}s"
    return 1
}

# API calls
api_call() {
    local method="$1"
    local endpoint="$2"
    local data="$3"
    local host="${HOST:-localhost}"
    local port="${PORT:-8080}"
    local url="http://${host}:${port}/api/v1${endpoint}"
    
    if [[ -n "$data" ]]; then
        curl -s -X "$method" -H "Content-Type: application/json" -d "$data" "$url"
    else
        curl -s -X "$method" "$url"
    fi
}

# Get platform status
get_platform_status() {
    api_call "GET" "/health"
}

# Print a banner
print_banner() {
    local title="$1"
    local width=60
    echo ""
    echo -e "${BLUE}$(printf '=%.0s' $(seq 1 $width))${NC}"
    echo -e "${BLUE}  $title${NC}"
    echo -e "${BLUE}$(printf '=%.0s' $(seq 1 $width))${NC}"
    echo ""
}

# Confirm action
confirm() {
    local prompt="$1"
    local default="${2:-n}"
    
    if [[ "$default" == "y" ]]; then
        prompt="$prompt [Y/n]: "
    else
        prompt="$prompt [y/N]: "
    fi
    
    read -p "$prompt" -n 1 -r
    echo
    
    if [[ "$default" == "y" ]]; then
        [[ ! $REPLY =~ ^[Nn]$ ]]
    else
        [[ $REPLY =~ ^[Yy]$ ]]
    fi
}

# Check if running as root
check_not_root() {
    if [[ $EUID -eq 0 ]]; then
        log_warn "Running as root is not recommended"
        if ! confirm "Continue anyway?" "n"; then
            exit 1
        fi
    fi
}

# Find Python executable
find_python() {
    if command -v python3 &> /dev/null; then
        echo "python3"
    elif command -v python &> /dev/null; then
        # Check if it's Python 3
        if python --version 2>&1 | grep -q "Python 3"; then
            echo "python"
        else
            log_error "Python 3 is required but not found"
            exit 1
        fi
    else
        log_error "Python is not installed"
        exit 1
    fi
}

# Get platform PID
get_platform_pid() {
    local port="${PORT:-8080}"
    if command -v lsof &> /dev/null; then
        lsof -ti:$port 2>/dev/null
    else
        ps aux | grep "[p]ython.*run.py" | awk '{print $2}'
    fi
}

# Export functions for use in other scripts
export -f log_info
export -f log_success
export -f log_warn
export -f log_error
export -f log_debug
export -f require_command
export -f is_platform_running
export -f wait_for_platform
export -f api_call
export -f get_platform_status
export -f print_banner
export -f confirm
export -f check_not_root
export -f find_python
export -f get_platform_pid
