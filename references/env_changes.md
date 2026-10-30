# Environment changes

1. Confirm application versus service, exact UUID, keys, preview/runtime/build-time
   scope and expected side effect. Existing authorization for this task is enough;
   obtain authorization for any extra deploy/restart or unrelated change.
2. Inspect `coolify_envs.sh application APP_UUID` or `coolify_envs.sh service SERVICE_UUID`.
   Run `check_health.sh` and record its normalized `server` origin.
3. Bind CLI writes to that same server before preparing a mutation. The API helper's
   `COOLIFY_CONTEXT_NAME`, `COOLIFY_CONFIG_FILE`, `COOLIFY_BASE_URL` and token overrides
   do not select a CLI context. Resolve the CLI's own config location with
   `coolify config` (its output can include an update notice). Inspect only context
   names and instance URLs, never tokens or the whole config. Choose an existing
   equivalent CLI context; compare its normalized scheme, host and port with the
   helper's `server`, then verify it explicitly:

   ```bash
   coolify --context CLI_CONTEXT context verify
   ```

   Names may differ, but origins must match. A different config-file override or
   URL override requires this comparison too. If no matching CLI context exists,
   stop writes and explain the missing mapping; arrange it through the approved
   credential workflow. Keep all subsequent CLI commands explicitly scoped.
4. Verify installed CLI syntax with the relevant `--help`. Versions differ; helper
   env metadata deliberately contains no secret values.
5. For sensitive values use a private temporary directory and a 0600 env file,
   populated by the approved credential workflow without printing contents:

   ```bash
   coolify --context CLI_CONTEXT app env sync APP_UUID --file PATH
   coolify --context CLI_CONTEXT service env sync SERVICE_UUID --file PATH
   ```

   Sync updates/creates supplied keys and does not delete omitted keys. Select
   runtime/build-time/preview flags deliberately; inspect the installed help.
6. For one non-sensitive key, `env create` uses `--key KEY --value VALUE`; `env update`
   takes the exact env UUID/key and `--value VALUE`. Some versions also require
   `--key KEY` on update; check help before execution. Prefix every command with
   `coolify --context CLI_CONTEXT`. Resolve exact UUIDs before delete. Never place
   sensitive values in `--value` process arguments.
7. Re-read metadata with the same helper selection and run health after the change.
   Metadata proves presence and flags, not secret equality or successful rollout;
   validate the authorized application behavior separately. Remove task-created
   secret files once verified. Report changed keys and verification, not values.
