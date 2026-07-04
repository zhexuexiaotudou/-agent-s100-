# Next Stage 4.6 Operator-Selected Fixture Route Canary Plan

Goal: move from Codex-created synthetic source to one operator-selected fixture file without expanding to arbitrary NAS copy.

Entry requirements:

1. Keep global `execute_enabled=false` and use a scoped canary only.
2. Add an operator selector that can choose exactly one fixture file, not browse or grant the whole NAS.
3. Record source owner, relative path, source hash, size, ACL scope, target absence, and rollback plan before confirm.
4. Require fresh signed token, manifest id, approval phrase, operator approval file, and allowlisted dispatcher execution.
5. Re-check source hash and target absence immediately before execute.
6. Roll back the copied target and prove the source hash is unchanged.
7. Re-run adversarial privacy regression, protected-port health, dispatcher hash, and readonly mini-soak.

Exit condition:

- one operator-selected fixture route copy passes and target is rolled back, or
- route execute remains safely blocked with explicit reason codes.

Still forbidden:

- full-NAS copy
- recursive copy
- overwrite
- delete or move source
- Qwen-selected source/target
- cloud-derived private write requests
- public gateway exposure
