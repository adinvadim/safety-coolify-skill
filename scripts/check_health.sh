#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_HELPER="${ROOT_DIR}/scripts/coolify_api.sh"

if [[ -z "${COOLIFY_BASE_URL:-}" ]]; then
    echo "COOLIFY_BASE_URL is required." >&2
    exit 1
fi

echo "Coolify health check"
echo "Base URL: ${COOLIFY_BASE_URL}"
echo

echo "Instance health:"
"${API_HELPER}" /api/health
echo

if [[ -z "${COOLIFY_TOKEN_FILE:-}" && -z "${COOLIFY_API_TOKEN:-}" ]]; then
    echo "Authenticated checks skipped: set COOLIFY_TOKEN_FILE for version and resource checks."
    exit 0
fi

version_json="$("${API_HELPER}" --raw /api/v1/version)"
resources_json="$("${API_HELPER}" --raw /api/v1/resources)"

echo "Authenticated summary:"
if command -v jq >/dev/null 2>&1; then
    version_value="$(printf '%s' "${version_json}" | jq -r '.version // .message // .data.version // "unknown"')"
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
