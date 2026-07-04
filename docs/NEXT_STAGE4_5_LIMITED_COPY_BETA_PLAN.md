# Next Stage 4.5 Limited Copy Beta Plan

Goal: expose one limited beta copy path only after GPT Pro/human review of Stage 4.4.

Entry requirements:

1. Keep `execute_enabled=false` until a new operator approval packet is committed.
2. Add a real UI candidate selector that cannot browse the whole NAS.
3. Keep source and target allowlists narrow; do not widen to full `Personal/`.
4. Execute only through `ai_nas_action_execute_copy`.
5. Require fresh signed token, nonce, expiry, operator identity, source hash, target absence, and rollback manifest.
6. Run one real route-level copy canary on a Codex synthetic source only.
7. Roll back the copied target and retain source evidence.
8. Re-run OpenClaw/Qwen health, protected-port, dispatcher-hash, privacy, and adversarial gates.

Exit condition:

- one synthetic route-level execute canary passes and target is rolled back, or
- execute remains safely blocked with clear reason codes.

Still forbidden:

- arbitrary NAS copy
- user-file copy without explicit file selection
- overwrite
- delete
- move/rename
- chmod/chown
- recursive copy
- Qwen direct execution authority
- cloud private payload egress
