#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_HELPER="${ROOT_DIR}/scripts/coolify_api.sh"

echo "Coolify health check"
if [[ -n "${COOLIFY_BASE_URL:-}" ]]; then
    echo "Base URL override: ${COOLIFY_BASE_URL}"
elif [[ -n "${COOLIFY_CONTEXT_NAME:-}" ]]; then
    echo "Context override: ${COOLIFY_CONTEXT_NAME}"
else
    echo "Using default context from local Coolify config when available"
fi
echo

echo "Instance health:"
"${API_HELPER}" /api/health
echo

version_json="$("${API_HELPER}" --raw /api/v1/version)"
resources_json="$("${API_HELPER}" --raw /api/v1/resources)"

echo "Authenticated summary:"
if command -v jq >/dev/null 2>&1; then
    if printf '%s' "${version_json}" | jq -e . >/dev/null 2>&1; then
        version_value="$(printf '%s' "${version_json}" | jq -r '.version // .message // .data.version // "unknown"')"
    else
        version_value="$(printf '%s' "${version_json}" | tr -d '\r\n')"
    fi
    resource_count="$(printf '%s' "${resources_json}" | jq 'length')"
    unhealthy_count="$(printf '%s' "${resources_json}" | jq '[.[] | select(((.status // "") | ascii_downcase) | contains("unhealthy"))] | length')"

    echo "Version: ${version_value}"
    echo "Resources: ${resource_count}"
    echo "Unhealthy resources: ${unhealthy_count}"
    echo
    echo "First resources:"
    printf '%s' "${resources_json}" | jq -r '.[:10][] | "\(.type // "resource")\t\(.name // .uuid // "unknown")\t\(.status // "unknown")"'
else
    echo "jq not found; printing wrapped API output instead."
    echo
    echo "Version payload:"
    "${API_HELPER}" /api/v1/version
    echo
    echo "Resources payload:"
    "${API_HELPER}" /api/v1/resources
fi
