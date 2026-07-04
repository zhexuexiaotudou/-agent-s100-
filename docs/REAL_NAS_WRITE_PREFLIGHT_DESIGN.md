# Real NAS Write Preflight Design

This is design-only. No real NAS write is executed by Stage4.1.

Allowed first candidates:
- Copy only, low-risk, single small file.
- Rename only after copy-stage evidence passes.
- Move only after rename-stage evidence passes.
- Delete remains forbidden.

Required gates:
- Real path allowlist with explicit share and user scope.
- Human confirmation UI with action, source, target, before snapshot, rollback plan, and TTL.
- Before/after snapshot with hash and ACL metadata.
- Rollback execution and verification.
- Immutable audit record.
- Dry-run diff.
- ACL confirmation against real NAS user/group policy.
- Rate limit and small-file-only first stage.

Forbidden:
- Delete, chmod, recursive directory operation, cross-user path, cloud-derived write, Qwen autonomous write, arbitrary shell/script path.
