# Final Release Repo Security Cleanup

Generated on 2026-07-05 for the final release cleanup gate.

## Scope

This cleanup only changes release hygiene. It does not add product features and
does not widen OpenClaw, NAS, Qwen, or robot-control permissions.

## What Changed

- Historical binary/model-runtime dumps, SQLite runtime traces, and old review
  package files whose paths matched the release forbidden-path scan were removed
  from the Git-tracked release tree.
- The removed tracked files were exported from `HEAD` before removal to:
  `F:\Project\Digua_external_artifacts\final_release_cleanup_20260705\tracked_removed_artifacts_from_HEAD.zip`
- The export manifest with per-file SHA256 values is:
  `F:\Project\Digua_external_artifacts\final_release_cleanup_20260705\tracked_removed_artifacts_manifest.json`
- A small set of untracked research logs with forbidden path names was moved to:
  `F:\Project\Digua_external_artifacts\final_release_cleanup_20260705\untracked_moved_artifacts`
- Source files that were still useful but had forbidden release-scan names were
  renamed without changing their behavior:
  - `ai_nas_harness/privacy_filter.py`
  - `gates/cloud_egress_privacy_gate.py`
  - `scripts/probes/ai_nas_index_integrity_contract_probe.py`
  - `scripts/probes/dream7b_reference_param_matrix_probe.py`
  - `tools/export_reference_matrix.py`

## Dream7B Boundary

Dream7B artifacts remain research-only. The release product route is still
S100P + OpenClaw + Qwen + AI-NAS permission gates. Dream7B HBM dumps,
reference-matrix evidence, GGUF/reference logs, and runtime DB traces must stay
outside the tracked release tree unless a future review explicitly accepts them
as external artifacts.

## Verification

The cleanup target is the strict path scan used by the final release prompt:

```bash
git ls-files | grep -Ei "sqlite|sqlite3|redaction|secret|credential|\.env|gguf|safetensors|\.bin|\.pt|\.pth|tokenizer\.json|vocab\.json|merges\.txt" || true
git status --short | grep -Ei "sqlite|sqlite3|redaction|secret|credential|\.env|gguf|safetensors|\.bin|\.pt|\.pth|tokenizer\.json|vocab\.json|merges\.txt" || true
```

After the cleanup commit, both commands must return no matches before the final
release package can claim repo-security cleanup.
