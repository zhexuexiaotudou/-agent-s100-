# stage2_package_release_integrity_gate

- verdict: `ok_stage2_package_release_integrity_gate`
- generated_at: `2026-07-03T11:48:42.681949+08:00`
- passed: `8/8`

## Checks

- `PASS` top-level MANIFEST exists
- `PASS` top-level SHA256SUMS exists
- `PASS` manifest paths and hashes pass
- `PASS` SHA256SUMS paths and hashes pass
- `PASS` no Windows-only paths
- `PASS` nested input paths are package-local
- `PASS` clean package rerun passes
- `PASS` negative missing input package fails

## Failures

- none

## Detail

```json
{
  "candidate": {
    "root": "F:\\Project\\Digua\\tmp\\stage2_5_release_candidate_20260703-114833",
    "file_count": 411,
    "manifest": "F:\\Project\\Digua\\tmp\\stage2_5_release_candidate_20260703-114833\\MANIFEST.json",
    "sha256sums": "F:\\Project\\Digua\\tmp\\stage2_5_release_candidate_20260703-114833\\SHA256SUMS.txt"
  },
  "verification": {
    "manifest_file_count": 411,
    "sha_line_count": 411,
    "manifest_missing": [],
    "manifest_mismatched": [],
    "sha_missing": [],
    "sha_mismatched": [],
    "windows_paths": [],
    "inputs": {
      "stage1_input": "stage1_input/ai_nas_harness_stage1_fixed_gptpro_20260702-233035.zip",
      "previous_stage2_input": "previous_stage2_input/digua_ai_nas_harness_stage2_s100p_live_for_gptpro_20260703-013757.zip"
    }
  },
  "remote_root": "/tmp/digua_stage2_5_release_20260703-114833/stage2_5_release_candidate_20260703-114833",
  "scp": {
    "returncode": 0,
    "stdout_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stderr_tail": ""
  },
  "rerun": {
    "returncode": 0,
    "elapsed_ms": 2422.003,
    "stdout_hash": "73cec3135c33573449071cca35b8b2453d424c39154e73d8526add2a72939afe",
    "stderr_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stdout_tail": "{\n  \"verdict\": \"ok_stage2_readiness_gates\",\n  \"failed\": []\n}\n"
  },
  "negative": {
    "returncode": 2,
    "elapsed_ms": 274.675,
    "stdout_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "stderr_hash": "56c11860b8243187e2f59511d539c428d70777fdba4914630697d4b25d955f39",
    "stdout_tail": "",
    "stderr_tail": "missing stage1 input package under /tmp/digua_stage2_5_release_20260703-114833/negative/stage1_input\n"
  }
}
```
