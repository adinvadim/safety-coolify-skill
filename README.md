# Safety Coolify Skill

Safer fork of `ajmcclary/coolify-manager`. This version keeps validated Coolify API and CLI guidance, removes legacy CMS-specific workflows, and strips the unsafe installer/bootstrap patterns that caused the skill checker findings.

## What Changed

- Removed bundled CLI download/install automation
- Removed inline secret examples from commands
- Removed legacy CMS troubleshooting content
- Switched to API-first, read-only defaults
- Added a safe bounded workflow for application log review
- Added validated CLI guidance for environment-variable changes
- Added explicit handling rules for untrusted remote output
- Added a regression check for the previously flagged patterns

## Quick Start

Store the token in a local file instead of placing it on the command line:

```bash
mkdir -p "$HOME/.config/coolify"
chmod 700 "$HOME/.config/coolify"
printf '%s' '<paste token once>' > "$HOME/.config/coolify/token"
chmod 600 "$HOME/.config/coolify/token"

export COOLIFY_BASE_URL="https://coolify.example.com"
export COOLIFY_TOKEN_FILE="$HOME/.config/coolify/token"
```

If `coolify` is already configured locally, you usually do not need those exports. The helper scripts auto-read the default context from `~/.config/coolify/config.json`.

Run the bundled checks:

```bash
bash scripts/check_health.sh
bash scripts/coolify_api.sh /api/v1/resources
bash scripts/coolify_logs.sh APP_UUID 100
```

## Safety Model

- Read-only first
- No automated executable downloads
- No `curl | bash`
- No raw token in examples
- No automatic ingestion of remote logs as instructions
- Any start, stop, restart, deploy, create, update, or delete action requires explicit user approval

## Included Files

```text
safety-coolify-skill/
├── README.md
├── SKILL.md
├── CLAUDE.md
├── docs/
│   └── VALIDATION.md
├── references/
│   ├── api_endpoints.md
│   └── cli_commands.md
├── scripts/
│   ├── check_health.sh
│   └── coolify_api.sh
│   └── coolify_logs.sh
└── tests/
    └── safety_regression.sh
```

## Validated Surfaces

API guidance in this fork is validated against the official Coolify docs:

- Authorization model and API base paths
- Health and version checks
- Application log retrieval
- Environment variable CRUD and bulk update endpoints
- Resource, application, service, database, deployment, and env metadata endpoints

CLI guidance in this fork is validated against the official `coollabsio/coolify-cli` README and release metadata, but this fork intentionally does not automate upstream installation flows.

## Development

Run the local gate:

```bash
bash tests/safety_regression.sh
docs-list
```

`docs-list` is optional in the environment but should pass when available.

## Resources

- [Coolify Docs](https://coolify.io/docs)
- [Coolify API Reference](https://coolify.io/docs/api-reference/api/)
- [Coolify CLI Repository](https://github.com/coollabsio/coolify-cli)
