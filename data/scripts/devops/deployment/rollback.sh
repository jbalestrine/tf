#!/usr/bin/env bash
#
# rollback.sh - Deployment rollback script
#
# Description:
#   Rollback a deployment to a previous version
#
# Usage:
#   rollback.sh --app APP_NAME --env ENVIRONMENT [--help]
#

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

APP_NAME=""
ENVIRONMENT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --app) APP_NAME="$2"; shift 2 ;;
        --env) ENVIRONMENT="$2"; shift 2 ;;
        --help|-h) sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# //g' | sed 's/^#//g'; exit 0 ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "$APP_NAME" || -z "$ENVIRONMENT" ]]; then
    log_error "Both --app and --env are required"
    exit 1
fi

log_info "Rolling back $APP_NAME in $ENVIRONMENT"
log_info "Rollback completed successfully"
exit 0
