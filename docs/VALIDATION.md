---
summary: "Official contracts and offline validation for Coolify reads."
read_when: [validation, security, release]
---

# Validation

Validated 2026-10-30 against official sources:

- [Deployment detail](https://coolify.io/docs/api/endpoints/deployments/get-deployment-by-uuid): GET `/api/v1/deployments/{uuid}`; status, commit, timestamps, logs string; 401/404 errors.
- [Application env list](https://coolify.io/docs/api/endpoints/applications/list-envs-by-application-uuid): GET `/api/v1/applications/{uuid}/envs`; the helper intentionally projects metadata instead of exposing values.
- [Application logs](https://coolify.io/docs/api-reference/api/operations/get-application-logs-by-uuid): GET `/api/v1/applications/{uuid}/logs?lines=100`.
- [CLI README](https://github.com/coollabsio/coolify-cli#readme): `version` subcommand, config location and file-based env sync. Installed versions differ; use local help for mutation flags.

## Local gate

`bash bin/check` parses Python and skill YAML, checks shell syntax/lint, runs
static safety checks and `tests/test_reads.py` against a real local HTTP server.
The `.githooks/pre-commit` invokes that gate when `core.hooksPath=.githooks`.
Runtime needs only Python 3.9+ and Bash. Checks additionally need PyYAML,
ShellCheck. No hosted CI is added.

Behavioral contracts include origin/token pairing, explicit file credentials,
public health without auth, named-context errors, rejected redirects and mutation
paths, env-value omission even with `--raw`, reflected-token filtering, bounded
application/deployment logs, hidden-record omission, structured application logs preserved as text, unknown
configuration state when values are withheld, the upstream `is_buildtime` flag,
JSON/text deployment log
forms, non-success HTTP/status handling and malformed payloads.

The retrospective's fake-token reproduction demonstrated origin mixing and
unauthenticated-health failure on the previous implementation. The new HTTP
regression suite also runs against a disposable archive of the pinned baseline
for red/green evidence. Test outputs and review reports remain outside Git.

## Limits

Common sensitive JSON fields are redacted recursively; env routes project an
allowlist. This is not general secret detection for arbitrary logs or free-form
remote text. Endpoint filtering and markers do not make output trusted. HTTP is
supported for explicitly configured private-network instances; TLS verification
is retained for HTTPS. Redirects fail closed. The 20-second timeout is per socket
operation, with a separate 8 MiB response cap; this is not a wall-clock job deadline.
