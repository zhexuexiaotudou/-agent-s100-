# GPT Pro Evaluation Prompt

You are reviewing a Digua AI-NAS / OpenClaw / S100P real-NAS-write preflight package.

Context:
- Stage4.1 passed expanded synthetic sandbox write canaries and failure injection.
- The operator has approved continuing only into real NAS preflight dry-run design.
- No real NAS write has been executed.
- `ai_nas_action_execute_copy_probe.py` and `ai_nas_action_rollback_copy_probe.py` were not invoked.
- The current package verdict is `real_nas_preflight_dryrun_approved_locked_missing_explicit_candidate`.

Please evaluate:

1. Is it reasonable to keep real NAS writes locked until one explicit low-risk copy candidate is provided?
2. Is the candidate schema strict enough for a first real NAS copy dry-run?
3. Are the forbidden actions complete enough: delete/chmod/chown/recursive/move/rename/overwrite/cross-user/cloud-derived/Qwen-autonomous/arbitrary-shell?
4. Should the first materialized dry-run require a readonly source hash check and target non-existence check before displaying an approval phrase?
5. What exact gates should Codex implement before the first real copy execution?
6. What rollback evidence is required before allowing execution?
7. Are there any additional ACL, privacy, audit, or UX checks needed for OpenClaw + NAS baseline?

Return:
- final recommendation: keep locked / allow materialized dry-run only / allow first real copy execution later
- required fixes before materialized dry-run
- required fixes before real execution
- a concise staged roadmap Codex can implement with repo-verifiable evidence
