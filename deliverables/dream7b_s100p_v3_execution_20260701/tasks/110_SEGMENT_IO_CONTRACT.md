# Task 110 — Segment IO contract audit

## Hypothesis

The all-zero final logits may result from an input contract mismatch between `seg26_27` output and `seg27_28` input: layout, dtype, quantization, shape, tensor name, scale, or runtime descriptor interpretation.

## Required tool

Create or update:

```text
tools/inspect_segment_io_contract.py
```

You may start from `tools_scaffold/inspect_segment_io_contract.py`, but must adapt it to the actual runtime API and manifest format.

## Required fields per segment 0..27

- `segment_index`
- `model_name`
- `hbm_path`
- `hbm_size_bytes`
- `hbm_sha256`
- `hbo_path` if applicable
- `input_tensor_names`
- `output_tensor_names`
- `declared_input_shapes`
- `declared_output_shapes`
- `input_dtype`
- `output_dtype`
- `input_quant_params`
- `output_quant_params`
- `runtime_model_info`
- `runtime_tensor_descriptors`
- `unavailable_fields`
- `exceptions`

Do not read only `output_quants`. Try all available model-info/tensor-descriptor APIs exposed by the runtime.

## Special focus

Compare:

```text
seg26_27 output contract
seg27_28 input contract
```

Report whether they agree on:

- shape
- dtype
- signedness
- quantization scale/zero-point
- memory layout
- batch/sequence/channel axis order
- last-token vs full-sequence expectation

## Outputs

- `reports/110_segment_io_contract.json`
- `reports/110_segment_io_contract.md`

## Verdict

```json
{
  "segment_io_contract_verdict": "pass|fail|inconclusive",
  "seg26_to_seg27_contract_match": "pass|fail|inconclusive",
  "blocking_fields_missing": []
}
```
