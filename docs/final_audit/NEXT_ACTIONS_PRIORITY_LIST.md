# Next Actions Priority List

| priority | item | recommended fix |
| --- | --- | --- |
| P0 | Repo has substantial modified and untracked files | Review, remove private/heavy artifacts, stage scoped deliverables, and commit intentionally. |
| P0 | Security review required for suspicious file-name patterns | Audit suspicious paths and ensure final package excludes runtime DBs, redaction maps, keys, tokenizer raw assets, and model weights. |
| P1 | Fresh UI Playwright could not run in this audit | Install Node/npm or run browser automation from an environment with Playwright. |
| P1 | Tracked Python compile has one Dream7B research probe syntax error | Fix or quarantine the historical research probe. |
| P1 | UI v2 rollout evidence should be reconciled | Run a fresh S100P UI v2 default-service gate and update the UI packet. |
| P2 | SQLite inventory degraded in prior UI API smoke | Refresh inventory DB or make degradation reason visible in report. |
| P2 | Multimodal/OCR/embedding features are default-off | Keep safe wording or create separate feature-flag gate. |
| Research | Dream7B BPU operator alignment remains blocked | Collect true per-op BPU outputs, layout records, and quant scale evidence. |
