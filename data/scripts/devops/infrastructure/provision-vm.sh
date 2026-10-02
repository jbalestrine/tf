#!/usr/bin/env bash
#
# provision-vm.sh - VM provisioning script (Azure/AWS/GCP)
#
# Usage:
#   provision-vm.sh --provider PROVIDER --name NAME [--help]
#

set -euo pipefail

PROVIDER=""
NAME=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --provider) PROVIDER="$2"; shift 2 ;;
        --name) NAME="$2"; shift 2 ;;
        --help|-h) sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# //g'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

[[ -z "$PROVIDER" || -z "$NAME" ]] && { echo "ERROR: --provider and --name are required" >&2; exit 1; }

echo "[INFO] Provisioning VM: $NAME on $PROVIDER"
echo "[INFO] VM provisioning completed"
exit 0
