# Stage 4.4 UI Wireframe Text

## Copy Preview

Header: `Review copy candidate`

Fields:

- Action: `Copy`
- Source: `Selected file`
- Target: `Selected collection target`
- Source hash: `prefix only`
- Size: `bytes`
- Risk: `single-file bounded copy`

Primary button: `Dry-run`

Secondary button: `Cancel`

## Copy Dry-Run

Header: `Dry-run result`

Summary:

- `No write has occurred.`
- `One target file would be created if still absent.`
- `Source remains unchanged.`
- `Rollback can remove only the created target after hash verification.`

Input: `Approval phrase`

Primary button: `Confirm phrase`

Secondary button: `Back`

## Copy Confirmed

Header: `Approval token issued`

Summary:

- `Token is candidate-bound.`
- `Token expires soon.`
- `Execution is disabled in Stage 4.4 unless the operator enables a separate execute gate.`

Primary button disabled label: `Execute locked`

Secondary button: `Close`
