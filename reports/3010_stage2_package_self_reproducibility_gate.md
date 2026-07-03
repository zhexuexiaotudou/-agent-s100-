# stage2_package_self_reproducibility_gate

- verdict: `ok_stage2_package_self_reproducibility_gate`
- generated_at: `2026-07-03T01:38:04.445383+08:00`
- passed: `7/7`

## Checks

- `PASS` unzip/test package root exists
- `PASS` stage2 SHA manifest paths exist
- `PASS` stage2 SHA manifest hashes match
- `PASS` run_stage2_gates_from_package.sh exists
- `PASS` package copied to S100P clean tmp dir
- `PASS` clean S100P package rerun passes
- `PASS` negative missing dispatcher hard-fails

## Failures

- none

## Detail

```json
{
  "local_repaired_package_root": "tmp/stage2_s100p_package_repro_repaired",
  "remote_clean_package_root": "/tmp/digua_stage2_pkg_repro_20260703-013757/stage2_s100p_package_repro_repaired",
  "sha_line_count": 81,
  "rerun_stdout_hash": "73cec3135c33573449071cca35b8b2453d424c39154e73d8526add2a72939afe",
  "negative_returncode": 1
}
```
