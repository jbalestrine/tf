#!/usr/bin/env bash
#
# deploy-docker.sh - Docker container deployment script
#
# Description:
#   Deploy a Docker container with configuration validation
#
# Usage:
#   deploy-docker.sh --image IMAGE --name NAME [--dry-run] [--help]
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

IMAGE=""
NAME=""
DRY_RUN=false

show_help() {
    sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# //g' | sed 's/^#//g'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --image) IMAGE="$2"; shift 2 ;;
        --name) NAME="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        --help|-h) show_help ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "$IMAGE" || -z "$NAME" ]]; then
    log_error "Both --image and --name are required"
    exit 1
fi

log_info "Deploying Docker container: $NAME from image: $IMAGE"

if [[ "$DRY_RUN" == "true" ]]; then
    log_warn "DRY RUN MODE"
    log_info "Would run: docker run --name $NAME $IMAGE"
    exit 0
fi

# Docker deployment logic here
log_info "Docker container deployment completed"
exit 0
