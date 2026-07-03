# Task 620 Final Segment Function Boundary Audit

- verdict: `partial_exact_boundary_blocked_final_head_only_is_candidate`
- inferred boundary: seg27_28 name/path and input/output shape indicate final decoder layer 27 through final norm/lm_head, not final norm/lm_head only; exact isolation requires HF layer27+norm+lm_head.
- exact isolated rows: `0`
- comparison rows: `42`
