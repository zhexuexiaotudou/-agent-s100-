# seg00_01 Position Input Audit

- verdict: `position_input_contract_suspicious`
- max_delta_abs: `0.6751194000244141`

## Blocking or Failure Reasons
- Changing _input_1 position vectors produces material seg00_01 output deltas, but HF code does not expose a learned absolute position add at this boundary.
