# stage2_7_package_self_rerun_repair_gate

- verdict: `ok_stage2_7_package_self_rerun_repair_gate`
- generated_at: `2026-07-03T13:03:11.521307+08:00`
- passed: `7/7`

## Checks

- `PASS` bash available
- `PASS` clean extract rerun passes
- `PASS` all rerun outputs have JSON/Markdown reports
- `PASS` previous_stage2_6_input package present
- `PASS` previous_stage2_5_input can be recognized
- `PASS` negative missing-policy test fails
- `PASS` negative missing-dispatcher test fails

## Failures

- none

## Detail

```json
{
  "candidate_root": "F:\\Project\\Digua\\tmp\\stage2_7_package_rerun_candidate_20260703-130304",
  "clean": {
    "returncode": 0,
    "stdout_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "",
    "stderr_tail": ""
  },
  "previous_stage2_5_input": {
    "returncode": 0,
    "stdout_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "",
    "stderr_tail": ""
  },
  "negative_missing_policy": {
    "returncode": 1,
    "stdout_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "",
    "stderr_tail": ""
  },
  "negative_missing_dispatcher": {
    "returncode": 1,
    "stdout_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "",
    "stderr_tail": ""
  },
  "package_runner_external_path_dependency": false
}
```
