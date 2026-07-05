# 130 Unfinished Items And Risk Register

| priority | item | status | fix |
| --- | --- | --- | --- |
| P0 | Repo has substantial modified and untracked files | modified=4, untracked=139 | Review, remove private/heavy artifacts, stage scoped deliverables, and commit intentionally. |
| P0 | Security review required for suspicious file-name patterns | repo_security_review_required | Audit suspicious paths and ensure final package excludes runtime DBs, redaction maps, keys, tokenizer raw assets, and model weights. |
| P1 | Fresh UI Playwright could not run in this audit | Node/npm/npx missing on Windows PATH | Install Node/npm or run browser automation from an environment with Playwright. |
| P1 | Tracked Python compile has one Dream7B research probe syntax error | scripts/probes/dream7b_gguf_param_matrix_probe.py line 2 IndentationError | Fix or quarantine the historical research probe. |
| P1 | UI v2 rollout evidence should be reconciled | Current /ui responds on 8765, but previous UI packet says 8765 rollout was pending operator approval. | Run a fresh S100P UI v2 default-service gate and update the UI packet. |
| P2 | SQLite inventory degraded in prior UI API smoke | UI packet reports sqlite_readonly_inventory_status=degraded | Refresh inventory DB or make degradation reason visible in report. |
| P2 | Multimodal/OCR/embedding features are default-off | metadata-only multimodal index; thumbnail/OCR/embedding false | Keep safe wording or create separate feature-flag gate. |
| Research | Dream7B BPU operator alignment remains blocked | bpu_operator_alignment_failed_review_required | Collect true per-op BPU outputs, layout records, and quant scale evidence. |
