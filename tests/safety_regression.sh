#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

scan_paths=(
    "SKILL.md"
    "README.md"
    "CLAUDE.md"
    "references"
    "scripts"
    "docs"
)

required_files=(
    "SKILL.md"
    "README.md"
    "CLAUDE.md"
    "references/api_endpoints.md"
    "references/cli_commands.md"
    "scripts/coolify_api.sh"
    "scripts/coolify_logs.sh"
    "scripts/check_health.sh"
    "docs/VALIDATION.md"
)

for path in "${required_files[@]}"; do
    [[ -e "${path}" ]] || {
        echo "Missing required file: ${path}" >&2
        exit 1
    }
done

first_line="$(sed -n '1p' SKILL.md)"
fourth_line="$(sed -n '4p' SKILL.md)"
[[ "${first_line}" == "---" && "${fourth_line}" == "---" ]] || {
    echo "SKILL.md must start with YAML front matter." >&2
    exit 1
}

[[ ! -e "scripts/install_coolify_cli.sh" ]] || {
    echo "Legacy installer still present." >&2
    exit 1
}

[[ ! -e "references/wordpress_fixes.md" ]] || {
    echo "Legacy CMS reference still present." >&2
    exit 1
}

for script in scripts/*.sh tests/*.sh; do
    bash -n "${script}"
done

forbidden_patterns=(
    'curl[[:space:]]+-fsSL[[:space:]].*\|[[:space:]]*bash'
    'install_coolify_cli\.sh'
    'wordpress'
    'wp-json'
    'coolify app logs'
    'Authorization:[[:space:]]+Bearer[[:space:]]+(YOUR|API_|TOKEN|<)'
    'YOUR_API_TOKEN'
    'YOUR_TOKEN'
    'coolify context add'
    '--show-sensitive'
    '--follow'
    '--debuglogs'
)

for pattern in "${forbidden_patterns[@]}"; do
    if rg -n -i --glob '!tests/**' -- "${pattern}" "${scan_paths[@]}" >/tmp/safety-regression-rg.txt; then
        echo "Forbidden pattern detected: ${pattern}" >&2
        cat /tmp/safety-regression-rg.txt >&2
        exit 1
    fi
done

echo "Safety regression checks passed."
