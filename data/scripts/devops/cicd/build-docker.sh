#!/usr/bin/env bash
#
# build-docker.sh - Docker image build script
#
# Usage:
#   build-docker.sh --tag TAG [--file DOCKERFILE] [--help]
#

set -euo pipefail

TAG=""
DOCKERFILE="Dockerfile"

while [[ $# -gt 0 ]]; do
    case $1 in
        --tag) TAG="$2"; shift 2 ;;
        --file) DOCKERFILE="$2"; shift 2 ;;
        --help|-h) sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# //g'; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

[[ -z "$TAG" ]] && { echo "ERROR: --tag is required" >&2; exit 1; }

echo "[INFO] Building Docker image: $TAG"
echo "[INFO] Using Dockerfile: $DOCKERFILE"

if [[ ! -f "$DOCKERFILE" ]]; then
    echo "[ERROR] Dockerfile not found: $DOCKERFILE" >&2
    exit 1
fi

echo "[INFO] Docker image build completed"
exit 0
