# real_nas_execution_block_gate

- verdict: `ok_real_nas_execution_block_gate`
- generated_at: `2026-07-04T11:48:24.712249+08:00`
- passed: `4/4`

## Checks

- `PASS` execute_copy probe exists and was not invoked
- `PASS` rollback_copy probe exists and was not invoked
- `PASS` real NAS write executed flag false
- `PASS` copy/delete/source-modification counters false

## Failures

- none

## Detail

```json
{
  "generated_at": "2026-07-04T11:48:24.712209+08:00",
  "real_nas_write_executed": false,
  "approval_manifest_probe_invoked": false,
  "execute_copy_probe_invoked": false,
  "rollback_copy_probe_invoked": false,
  "copy_performed": false,
  "target_delete_performed": false,
  "source_modified": false,
  "probes_hashed": {
    "approval_manifest_probe": {
      "path": "scripts/probes/ai_nas_action_approval_manifest_probe.py",
      "exists": true,
      "sha256": "b1a9ebc23b0bd19ad3f3dddea329c5dcf46c42dd0b53d9f51349061e4c64a6c7"
    },
    "execute_copy_probe": {
      "path": "scripts/probes/ai_nas_action_execute_copy_probe.py",
      "exists": true,
      "sha256": "37dd46f53b827cd694d8785eccdda7d19db959709871c48dd1891945a1b2e9e9"
    },
    "rollback_copy_probe": {
      "path": "scripts/probes/ai_nas_action_rollback_copy_probe.py",
      "exists": true,
      "sha256": "575ae95639e608c1b441e403e59ae5921d42857389f649d41e854655af9b0cae"
    }
  },
  "reason": "this gate records preflight lock state and never calls execute/rollback probes"
}
```
