#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

scan_paths=(
    "SKILL.md"
    "README.md"
    "AGENTS.md"
    "CLAUDE.md"
    "references"
    "scripts"
    "docs"
)

required_files=(
    "SKILL.md"
    "README.md"
    "AGENTS.md"
    "CLAUDE.md"
    "references/api_endpoints.md"
    "references/cli_commands.md"
    "scripts/check_cli.sh"
    "scripts/coolify_read.py"
    "scripts/coolify_envs.sh"
    "scripts/coolify_deployment.sh"
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
    '^[[:space:]]*coolify --version([[:space:]]|$)'
)

python3 - "${scan_paths[@]}" -- "${forbidden_patterns[@]}" <<'PYSCAN'
from pathlib import Path
import re
import sys
split = sys.argv.index('--')
paths = sys.argv[1:split]
patterns = sys.argv[split + 1:]
for source in paths:
    path = Path(source)
    for entry in path.rglob('*') if path.is_dir() else [path]:
        if not entry.is_file() or '__pycache__' in entry.parts or entry.suffix == '.pyc':
            continue
        text = entry.read_text()
        for pattern in patterns:
            if re.search(pattern.replace('[[:space:]]', r'\s'), text, re.I | re.M):
                raise SystemExit(f'Forbidden pattern detected in {entry}: {pattern}')
PYSCAN

echo "Safety regression checks passed."
