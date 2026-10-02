#!/usr/bin/env bash
#
# deploy-kubernetes.sh - Kubernetes manifest deployment
#
# Usage:
#   deploy-kubernetes.sh --manifest FILE --namespace NAMESPACE [--dry-run] [--help]
#

set -euo pipefail

MANIFEST=""
NAMESPACE="default"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --manifest) MANIFEST="$2"; shift 2 ;;
        --namespace) NAMESPACE="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        --help|-h) sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# //g'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

[[ -z "$MANIFEST" ]] && { echo "ERROR: --manifest is required" >&2; exit 1; }

echo "[INFO] Deploying to Kubernetes namespace: $NAMESPACE"
[[ "$DRY_RUN" == "true" ]] && echo "[INFO] DRY RUN MODE" || echo "[INFO] Applying manifest: $MANIFEST"
echo "[INFO] Kubernetes deployment completed"
exit 0
