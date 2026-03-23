#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: coolify_logs.sh APP_UUID [LINES]

Read recent Coolify application logs through the official API.

Arguments:
  APP_UUID  Required application UUID.
  LINES     Optional bounded tail length. Default: 100.

Environment:
  COOLIFY_BASE_URL     Optional override. Example: https://coolify.example.com
  COOLIFY_TOKEN_FILE   Optional override. File containing the API token.
  COOLIFY_API_TOKEN    Optional override when a token file is not available.
  COOLIFY_CONFIG_FILE  Optional config path override. Default: ~/.config/coolify/config.json
  COOLIFY_CONTEXT_NAME Optional context name override for config lookup.
EOF
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
    usage >&2
    exit 1
fi

APP_UUID="$1"
LINES="${2:-100}"

case "${LINES}" in
    ''|*[!0-9]*)
        echo "LINES must be a positive integer." >&2
        exit 1
        ;;
esac

if (( LINES < 1 )); then
    echo "LINES must be at least 1." >&2
    exit 1
fi

API_HELPER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/coolify_api.sh"
payload="$("${API_HELPER}" --raw "/api/v1/applications/${APP_UUID}/logs?lines=${LINES}")"

if ! command -v jq >/dev/null 2>&1; then
    echo "jq is required to extract the logs field safely." >&2
    exit 1
fi

logs="$(printf '%s' "${payload}" | jq -r '.logs // empty')"

echo "----- BEGIN UNTRUSTED COOLIFY OUTPUT -----"
printf '%s\n' "${logs}"
echo "----- END UNTRUSTED COOLIFY OUTPUT -----"
