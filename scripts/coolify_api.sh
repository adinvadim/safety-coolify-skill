#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: coolify_api.sh [--raw] /api/path

Read-only Coolify API helper.

Environment:
  COOLIFY_BASE_URL    Required. Example: https://coolify.example.com
  COOLIFY_TOKEN_FILE  Preferred. File containing the API token.
  COOLIFY_API_TOKEN   Optional fallback when a token file is not available.

Notes:
  - Only GET requests are supported by this helper.
  - Output is wrapped with untrusted-data markers unless --raw is used.
EOF
}

RAW_OUTPUT=0
ENDPOINT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --raw)
            RAW_OUTPUT=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            if [[ -n "${ENDPOINT}" ]]; then
                echo "Unexpected argument: $1" >&2
                exit 1
            fi
            ENDPOINT="$1"
            shift
            ;;
    esac
done

if [[ -z "${ENDPOINT}" ]]; then
    usage >&2
    exit 1
fi

if [[ -z "${COOLIFY_BASE_URL:-}" ]]; then
    echo "COOLIFY_BASE_URL is required." >&2
    exit 1
fi

if [[ "${ENDPOINT}" != /* ]]; then
    echo "Endpoint must start with '/'." >&2
    exit 1
fi

if [[ -n "${COOLIFY_TOKEN_FILE:-}" && -n "${COOLIFY_API_TOKEN:-}" ]]; then
    echo "Set either COOLIFY_TOKEN_FILE or COOLIFY_API_TOKEN, not both." >&2
    exit 1
fi

BASE_URL="${COOLIFY_BASE_URL%/}"
REQUEST_URL="${BASE_URL}${ENDPOINT}"
TOKEN=""

if [[ -n "${COOLIFY_TOKEN_FILE:-}" ]]; then
    if [[ ! -r "${COOLIFY_TOKEN_FILE}" ]]; then
        echo "Token file is not readable: ${COOLIFY_TOKEN_FILE}" >&2
        exit 1
    fi
    TOKEN="$(tr -d '\r\n' < "${COOLIFY_TOKEN_FILE}")"
elif [[ -n "${COOLIFY_API_TOKEN:-}" ]]; then
    TOKEN="${COOLIFY_API_TOKEN//$'\n'/}"
fi

if [[ -z "${TOKEN}" && "${ENDPOINT}" != "/api/health" ]]; then
    echo "Authenticated endpoints require COOLIFY_TOKEN_FILE or COOLIFY_API_TOKEN." >&2
    exit 1
fi

run_request() {
    if [[ -n "${TOKEN}" ]]; then
        curl --fail --silent --show-error --location --config - "${REQUEST_URL}" <<EOF
header = "Accept: application/json"
header = "Authorization: Bearer ${TOKEN}"
EOF
    else
        curl --fail --silent --show-error --location --header "Accept: application/json" "${REQUEST_URL}"
    fi
}

if [[ "${RAW_OUTPUT}" -eq 1 ]]; then
    run_request
    exit 0
fi

echo "----- BEGIN UNTRUSTED COOLIFY OUTPUT -----"
run_request
echo
echo "----- END UNTRUSTED COOLIFY OUTPUT -----"
