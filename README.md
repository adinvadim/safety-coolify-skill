# Safety Coolify Skill

Read-only Coolify diagnostics with credential-scoped HTTP requests, bounded logs,
filtered environment metadata and an optional authorized CLI mutation workflow.

Requirements: Python 3.9+ and Bash. Existing CLI context is read from
`~/.config/coolify/config.json`; neither CLI nor jq is required for API reads.

```bash
bash scripts/check_health.sh
bash scripts/coolify_api.sh /api/v1/resources
bash scripts/coolify_envs.sh application APP_UUID
bash scripts/coolify_logs.sh APP_UUID 100
bash scripts/coolify_deployment.sh DEPLOYMENT_UUID 100
```

See [SKILL.md](SKILL.md) for context selection, output boundaries and exit codes.
`--raw` removes markers, never credential filtering. Different-origin URL overrides
require explicit matching credentials. Requests reject redirects and endpoints
outside the supported read-only allowlist. Env reads always omit values. Generic
reads expose a metadata allowlist and omit unknown fields, including database
connection URLs. Arbitrary logs can still contain application secrets.

For an existing CLI, `bash scripts/check_cli.sh` probes `coolify version` and the
config location. `coolify --version` is unsupported. No executable is downloaded.

## Development

Install local check prerequisites PyYAML, ShellCheck alongside Python
and Bash. Run `bash bin/check` for syntax/frontmatter, shell lint, safety checks and
offline HTTP regression tests. Enable the commit gate:

```bash
git config core.hooksPath .githooks
```

Tests run against a local disposable server and fixture credentials, without
production access. User-visible changes use uniquely named `.changes/*.md`
fragments. [Validation](docs/VALIDATION.md) records contracts and official sources.
