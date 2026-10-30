#!/usr/bin/env bash

set -euo pipefail

if ! command -v coolify >/dev/null 2>&1; then
    echo "Coolify CLI not found in PATH." >&2
    echo "Probe rule: use 'command -v coolify' and 'coolify version'; do not use 'coolify --version'." >&2
    exit 1
fi

COOLIFY_BIN="$(command -v coolify)"

echo "Coolify CLI detected"
echo "Binary: ${COOLIFY_BIN}"
echo "Version output:"
coolify version

echo
if config_path="$(coolify config 2>/dev/null)"; then
    echo "Config: ${config_path}"
else
    echo "Config: unavailable"
fi

echo "Probe rule: use 'coolify version', not 'coolify --version'."
