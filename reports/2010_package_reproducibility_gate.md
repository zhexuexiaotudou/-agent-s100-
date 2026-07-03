# stage1_package_reproducibility_gate

- verdict: `ok_stage1_package_reproducibility_gate`
- generated_at: `2026-07-03T01:33:34.502342+08:00`
- passed: `7/7`

## Checks

- `PASS` package zip exists
- `PASS` MANIFEST.json exists after extract
- `PASS` SHA256SUMS.txt generated
- `PASS` production context assets resolve
- `PASS` stage1 gate runner exists in package
- `PASS` stage1 gates rerun from clean package
- `PASS` missing dispatcher hard-fails resolver

## Failures

- none

## Detail

```json
{
  "package_zip": "evidence_for_gptpro\\ai_nas_harness_stage1_fixed_gptpro_20260702-233035.zip",
  "stage1_gate_rerun": {
    "returncode": 0,
    "stdout_tail": "F:\\Project\\Digua\\tmp\\stage1_package_repro_check\\reports\\harness_stage1_gate_report.json\nF:\\Project\\Digua\\tmp\\stage1_package_repro_check\\reports\\harness_stage1_gate_report.md\n",
    "stderr_tail": ""
  },
  "extracted_file_count": 87
}
```
