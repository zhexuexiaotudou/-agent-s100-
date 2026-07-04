# Real NAS Write Gate Plan

1. GPT Pro/human reviews Stage4.1 package.
2. Implement real-path allowlist in design-only mode.
3. Run dry-run diff on one low-risk copy candidate.
4. Add immutable audit sink.
5. Add rollback storage and verified rollback execution.
6. Only then request a separate real-write approval packet.

Stage4.1 does not grant that approval.
