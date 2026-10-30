- Bind inherited credentials to the selected server origin and reject redirects; preserve public health without credentials.
- Add filtered env metadata and bounded deployment diagnostics with explicit pending/failure/not-found states; retain API/log shell entry points without jq/CLI dependencies.
- Enforce supported read-only endpoints, response/log limits and credential-field filtering; shorten agent guidance and honor existing task-specific mutation authorization.
- Add offline HTTP regression coverage and a local pre-commit validation gate.

RU: Диагностика Coolify связывает токен с выбранным сервером, скрывает env-значения, различает состояния деплоя и корректно проверяет health без авторизации. Добавлены ограниченные логи, регрессионные тесты и локальный commit gate.
