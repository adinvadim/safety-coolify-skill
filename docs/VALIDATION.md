---
summary: "Official-source validation and safety deltas for the hardened Coolify skill fork."
read_when: [validation, security, release]
---

# Validation

This repository was revalidated against official Coolify sources and then intentionally narrowed to a safer operating model.

## Official Sources Used

- Coolify API authorization docs: `https://coolify.io/docs/api-reference/authorization`
- Coolify API version endpoint docs: `https://coolify.io/docs/api-reference/api/operations/version`
- Coolify API application logs docs: `https://coolify.io/docs/api-reference/api/operations/get-application-logs-by-uuid`
- Coolify CLI upstream repository: `https://github.com/coollabsio/coolify-cli`

## Confirmed Facts

- Coolify API auth uses a bearer token generated from `Keys & Tokens` / `API tokens`.
- The API root is `/api`.
- Authenticated endpoints live under `/api/v1`.
- Health is outside the `/v1` prefix.
- Application logs are available at `GET /applications/{uuid}/logs` with a `lines` query parameter and default `100`.
- The upstream CLI documents context verification, version checks, resource listing, and object inspection commands.
- The upstream CLI repository showed `v1.4.0` as the latest release at validation time.

## Safety Deltas From Upstream

This fork intentionally does not mirror upstream installation or bootstrap guidance when that guidance conflicts with the skill safety policy.

Specifically, this fork removes or avoids:

- remote install-script execution
- automated executable downloads
- inline secret values in command examples
- legacy CMS-specific operational playbooks
- default mutating workflows

## Local Validation Gate

Run:

```bash
bash tests/safety_regression.sh
docs-list
```

`docs-list` is optional in the environment but should pass when present.
