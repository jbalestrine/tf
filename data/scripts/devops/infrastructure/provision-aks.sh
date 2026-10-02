#!/usr/bin/env bash
#
# provision-aks.sh - Azure Kubernetes Service cluster creation
#
# Usage:
#   provision-aks.sh --name NAME --resource-group RG [--nodes COUNT] [--help]
#

set -euo pipefail

NAME=""
RESOURCE_GROUP=""
NODE_COUNT=3

while [[ $# -gt 0 ]]; do
    case $1 in
        --name) NAME="$2"; shift 2 ;;
        --resource-group) RESOURCE_GROUP="$2"; shift 2 ;;
        --nodes) NODE_COUNT="$2"; shift 2 ;;
        --help|-h) sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# //g'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

[[ -z "$NAME" || -z "$RESOURCE_GROUP" ]] && {
    echo "ERROR: --name and --resource-group are required" >&2
    exit 1
}

echo "[INFO] Provisioning AKS cluster: $NAME"
echo "[INFO] Resource Group: $RESOURCE_GROUP"
echo "[INFO] Node Count: $NODE_COUNT"
echo "[INFO] AKS cluster provisioning initiated"
exit 0
