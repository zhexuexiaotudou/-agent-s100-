# Harness Default Service Defense QA

Q: Does Stage 5 allow arbitrary NAS writes?
A: No. The only enabled write action is bounded single-file copy through policy, token, hash, and dispatcher checks.

Q: Can Qwen execute file tools?
A: No. Qwen execution authority remains false.

Q: Are delete, move, rename, chmod, overwrite, or recursive copy supported?
A: No.
