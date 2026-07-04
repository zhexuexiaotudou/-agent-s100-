# stage4_1_baseline_lock

- verdict: `ok_stage4_1_baseline_lock`
- generated_at: `2026-07-04T11:38:47.522035+08:00`
- passed: `6/6`

## Checks

- `PASS` required prior Stage4 artifacts readable
- `PASS` prior final verdict is sandbox canary pass
- `PASS` prior real NAS write remains false
- `PASS` prior sandbox canary executed and rollback restored
- `PASS` prior Stage3.1 safety counters zero
- `PASS` prior package exists

## Failures

- none

## Detail

```json
{
  "prior_final_verdict": "stage4_sandbox_write_canary_passed_ready_for_gptpro_review",
  "prior_package": {
    "path": "F:\\Project\\Digua\\evidence_for_gptpro\\digua_ai_nas_harness_aggressive_progression_for_gptpro_20260704-112214.zip",
    "sha256": "5c7df04b3c1197b38c28a600b939242b98e65120081057fb137c58ce8b86c8f1"
  },
  "sandbox_canary": {
    "verdict": "ok_stage4_sandbox_write_canary_gate",
    "sandbox_write_executed": true,
    "real_nas_write_executed": false,
    "rollback_executed": true,
    "rollback_restored_before_manifest": true,
    "approval_artifact": "operator_approval/stage4_sandbox_write_canary_operator_approval.json",
    "blocked_reason": null
  },
  "approved_actions": [
    "copy"
  ],
  "stage4_1_candidate_actions": [
    "batch_copy",
    "copy",
    "move",
    "rename"
  ],
  "forbidden_actions": [
    "chmod",
    "delete",
    "permission_mutation",
    "real_nas_write",
    "recursive_delete",
    "shell_bypass"
  ],
  "hard_constraints": [
    "Do not replace OpenClaw.",
    "Do not replace Qwen.",
    "Do not modify 8765, 18080, 18888, or 18889.",
    "Do not let sidecar or harness become foreground route.",
    "Do not give Qwen tool execution authority.",
    "Do not execute real NAS writes.",
    "Do not touch real family/user data for writes.",
    "Do not write to /mnt/nas/Personal or any real user data path.",
    "Do not execute delete.",
    "Do not execute chmod or permission mutation.",
    "Do not execute recursive destructive operations.",
    "All sandbox writes require a signed approval token.",
    "All sandbox writes require before/after state and rollback.",
    "Cloud must not see private NAS raw content."
  ],
  "current_sandbox_manifest": {
    "generated_at": "2026-07-04T11:22:14.077634+08:00",
    "sandbox_root": "F:\\Project\\Digua\\tmp\\digua_ai_nas_write_sandbox",
    "sandbox_root_relative": "tmp/digua_ai_nas_write_sandbox",
    "real_nas_path": false,
    "file_count": 5,
    "files": [
      {
        "relative_path": "nested/file.md",
        "size": 46,
        "sha256": "f34de816e9dfae640d9a52aada2a94efbce6594eceea673d6fb1b9647d4e56db"
      },
      {
        "relative_path": "source/large_dummy.bin",
        "size": 65536,
        "sha256": "1f8745f0d2d1387ec1af2211a3cf417b2e9e885e853472649c1d979d0e9370e3"
      },
      {
        "relative_path": "source/photo_placeholder.jpg",
        "size": 38,
        "sha256": "818c4dce70cb15d77f74e45026d3953450339e09119d1e50a5b813583bf11ed1"
      },
      {
        "relative_path": "source/private_like_doc.txt",
        "size": 57,
        "sha256": "f39fa1f5076fed2c753ea099c0558960f68179ab8c4265583494203b31bcb3b2"
      },
      {
        "relative_path": "source/public_doc.txt",
        "size": 25,
        "sha256": "3b96300402065947c4d31532645c6baa06cdf27c3b6102da9a72a330aca3b52f"
      }
    ],
    "manifest_hash": "c96409768b8f76fbfe88934159d2f52f27f47efd703185c59547eaafc9d2b5f4"
  }
}
```
