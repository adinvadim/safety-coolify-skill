#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: coolify_api.sh [--raw] /api/path

Read-only Coolify API helper.

Environment:
  COOLIFY_BASE_URL     Optional override. Example: https://coolify.example.com
  COOLIFY_TOKEN_FILE   Optional override. File containing the API token.
  COOLIFY_API_TOKEN    Optional override when a token file is not available.
  COOLIFY_CONFIG_FILE  Optional config path override. Default: ~/.config/coolify/config.json
  COOLIFY_CONTEXT_NAME Optional context name override for config lookup.

Notes:
  - Only GET requests are supported by this helper.
  - Output is wrapped with untrusted-data markers unless --raw is used.
  - If no overrides are set, the helper reads the default Coolify context from local CLI config.
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

if [[ "${ENDPOINT}" != /* ]]; then
    echo "Endpoint must start with '/'." >&2
    exit 1
fi

if [[ -n "${COOLIFY_TOKEN_FILE:-}" && -n "${COOLIFY_API_TOKEN:-}" ]]; then
    echo "Set either COOLIFY_TOKEN_FILE or COOLIFY_API_TOKEN, not both." >&2
    exit 1
fi

CONFIG_FILE="${COOLIFY_CONFIG_FILE:-${HOME}/.config/coolify/config.json}"
CONTEXT_NAME="${COOLIFY_CONTEXT_NAME:-}"
BASE_URL="${COOLIFY_BASE_URL:-}"
TOKEN=""

resolve_from_config() {
    [[ -r "${CONFIG_FILE}" ]] || return 1
    command -v jq >/dev/null 2>&1 || return 1

    local selector
    if [[ -n "${CONTEXT_NAME}" ]]; then
        selector='.instances // [] | map(select(.name == $context_name)) | .[0]'
    else
        selector='.instances // [] | map(select(.default == true)) | .[0]'
    fi

    local context_json
    context_json="$(
        jq -c --arg context_name "${CONTEXT_NAME}" "${selector}" "${CONFIG_FILE}"
    )"

    [[ -n "${context_json}" && "${context_json}" != "null" ]] || return 1

    if [[ -z "${BASE_URL}" ]]; then
        BASE_URL="$(printf '%s' "${context_json}" | jq -r '.fqdn // empty')"
    fi

    if [[ -z "${TOKEN}" ]]; then
        TOKEN="$(printf '%s' "${context_json}" | jq -r '.token // empty')"
    fi
}

if [[ -n "${COOLIFY_TOKEN_FILE:-}" ]]; then
    if [[ ! -r "${COOLIFY_TOKEN_FILE}" ]]; then
        echo "Token file is not readable: ${COOLIFY_TOKEN_FILE}" >&2
        exit 1
    fi
    TOKEN="$(tr -d '\r\n' < "${COOLIFY_TOKEN_FILE}")"
elif [[ -n "${COOLIFY_API_TOKEN:-}" ]]; then
    TOKEN="${COOLIFY_API_TOKEN//$'\n'/}"
fi

resolve_from_config || true

if [[ -z "${BASE_URL}" ]]; then
    echo "Could not resolve Coolify base URL. Set COOLIFY_BASE_URL or configure a default context in ${CONFIG_FILE}." >&2
    exit 1
fi

BASE_URL="${BASE_URL%/}"
REQUEST_URL="${BASE_URL}${ENDPOINT}"

if [[ -z "${TOKEN}" && "${ENDPOINT}" != "/api/health" ]]; then
    echo "Authenticated endpoints require a token. Set COOLIFY_TOKEN_FILE/COOLIFY_API_TOKEN or configure a token in ${CONFIG_FILE}." >&2
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
