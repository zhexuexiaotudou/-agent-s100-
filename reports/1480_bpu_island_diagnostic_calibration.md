# BPU Island Diagnostic Calibration

- verdict: `runtime_timeout_no_rows_after_model_load`
- rows: `0/None`

## Blocking or Failure Reasons
- No deployable known-scale/no-fit early BPU island calibration passed strict logits validity across all three cases.
- The remote HF suffix calibration attempt loaded the model and started zeros island=[1], but produced no result rows before manual stop; v13 island suffix timing indicates the full 60-row v14 sweep is not practical in this runtime.
