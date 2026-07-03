# Input Contract Audit

- verdict: `input_contract_valid`
- cases: `3`
- zeros/ramp are diagnostic; short_chinese_prompt_padded is semantic+padded.

## Next Minimal Experiments
- Input metadata is internally consistent; seg0 mismatch should be tested under HF-prefix/BPU-single-segment substitution before attributing root cause to later graph stages.
