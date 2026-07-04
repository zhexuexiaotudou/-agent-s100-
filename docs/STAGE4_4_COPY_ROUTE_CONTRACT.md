# Stage 4.4 Copy Route Contract

Stage 4.4 introduces a route-level contract for bounded NAS copy exposure. It does not modify OpenClaw on port 8765, Qwen on port 18080, Dream routes, or protected ports 18888/18889. The contract is implemented as a guard/simulator first; production service wiring remains a later stage.

## Routes

`POST /api/nas/copy/preview`

- Accepts exactly one copy candidate.
- Returns redacted path hashes, size, source hash prefix, and whether dry-run/confirm are required.
- Performs no file system write.

`POST /api/nas/copy/dry-run`

- Validates the same candidate against the copy route policy.
- Returns a planned single-file create effect, rollback summary, approval phrase, and approval phrase hash.
- Performs no file system write.

`POST /api/nas/copy/confirm`

- Requires the exact approval phrase from dry-run.
- Issues a short-lived signed approval token bound to the candidate fingerprint, args hash, path hashes, source hash, target hash, nonce, and expiry.
- Performs no file system write.

`POST /api/nas/copy/execute`

- Default disabled.
- Requires all of: feature flag, explicit execute env, operator approval file, operator approval state, valid signed token, fresh nonce, and the same validated candidate.
- The Stage 4.4 guard authorizes only a future allowlisted dispatcher call. It does not perform copy directly.

`POST /api/nas/copy/rollback`

- Default disabled.
- Requires a dedicated rollback approval and allowlisted dispatcher path.
- The Stage 4.4 guard does not remove files directly.

## Policy Boundary

Allowed in Stage 4.4:

- action type: `copy`
- source prefix: `Collections/CodexPreflight/source/`
- target prefix: `Collections/CodexPreflight/target/`
- target root: `Collections/`
- source owner scope: `operator_visible` or `codex_synthetic`
- size limit: 1 MiB
- target must not already exist
- target parent must exist

Forbidden in Stage 4.4:

- delete, move, rename, chmod, chown, overwrite, recursive operation, arbitrary shell
- absolute paths, path traversal, URL-encoded traversal, empty path segments, control characters
- symlink source or symlink target parent
- Qwen autonomous execution authority
- cloud-derived writes
- private raw path or private content in route responses and audit traces
- OpenClaw/Qwen/protected-port mutation

## Authority Model

Qwen may summarize or advise only. It cannot call execute/rollback directly and cannot mint approval. The final authority chain is:

1. deterministic route guard
2. copy route policy
3. operator confirmation phrase
4. signed approval token
5. feature flags and operator approval file
6. allowlisted dispatcher

Stage 4.4 proves the contract and dry-run route. It does not grant general NAS write access.
