# Real NAS Write Human Confirmation Spec

Every future real-write request must show:
- action type, source, target, workspace, user identity, ACL basis, and risk class
- before-state hash and rollback-plan hash
- exact confirmation phrase bound to the signed approval token
- expiration time and nonce
- statement that Qwen cannot execute the write directly

The first accepted phrase should be scoped per action, for example:
`I_APPROVE_REAL_NAS_COPY_<approval_id>`.
