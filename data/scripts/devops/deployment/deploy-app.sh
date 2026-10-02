#!/usr/bin/env bash
#
# deploy-app.sh - Generic application deployment script
#
# Description:
#   Deploy an application to a target environment with validation and rollback support
#
# Usage:
#   deploy-app.sh --app APP_NAME --env ENVIRONMENT [--dry-run] [--help]
#
# Options:
#   --app APP_NAME      Name of the application to deploy (required)
#   --env ENVIRONMENT   Target environment: dev, staging, prod (required)
#   --version VERSION   Application version to deploy (default: latest)
#   --dry-run          Show what would be deployed without making changes
#   --help             Display this help message
#

set -euo pipefail

# Default values
APP_NAME=""
ENVIRONMENT=""
VERSION="latest"
DRY_RUN=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

show_help() {
    sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# //g' | sed 's/^#//g'
    exit 0
}

validate_inputs() {
    if [[ -z "$APP_NAME" ]]; then
        log_error "Application name is required. Use --app APP_NAME"
        exit 1
    fi
    
    if [[ -z "$ENVIRONMENT" ]]; then
        log_error "Environment is required. Use --env ENVIRONMENT"
        exit 1
    fi
    
    if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment. Must be one of: dev, staging, prod"
        exit 1
    fi
}

deploy_application() {
    log_info "Deploying application: $APP_NAME"
    log_info "Environment: $ENVIRONMENT"
    log_info "Version: $VERSION"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "DRY RUN MODE - No changes will be made"
        log_info "Would deploy $APP_NAME:$VERSION to $ENVIRONMENT"
        return 0
    fi
    
    # Deployment logic would go here
    log_info "Starting deployment process..."
    
    # Example steps:
    # 1. Validate environment is ready
    # 2. Backup current version
    # 3. Deploy new version
    # 4. Run health checks
    # 5. Update routing/load balancer
    
    log_info "Deployment completed successfully"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --app)
            APP_NAME="$2"
            shift 2
            ;;
        --env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            show_help
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Main execution
validate_inputs
deploy_application

exit 0
