# Stage4 Write Action Gate Plan

1. Keep Stage3.1 readonly shadow running until GPT Pro accepts the extended evidence.
2. Review the signed approval token schema and dry-run planner.
3. If approved, set `AI_NAS_OPERATOR_APPROVED_SANDBOX_WRITE_CANARY=1` for one local synthetic sandbox canary only.
4. Re-run the aggressive progression gates and inspect before/after manifest plus rollback evidence.
5. Do not move to real NAS writes without a new signed scope, destructive-action policy, and GPT Pro/human review.
