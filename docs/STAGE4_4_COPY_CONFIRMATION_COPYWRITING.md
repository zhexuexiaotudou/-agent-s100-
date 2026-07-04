# Stage 4.4 Copy Confirmation Copywriting

Use short, literal wording.

## Preview

Title: `Review copy candidate`

Body: `This will prepare a dry-run for one file. No file will be copied at this step.`

Blocked action note: `Delete, move, rename, overwrite, permission changes, and recursive actions are not available.`

## Dry-Run

Title: `Dry-run result`

Body: `The planned action is to create one target file if the target is still absent. The source file will not be changed.`

Rollback note: `Rollback can remove only the target created by this approved action after hash verification.`

Approval prompt: `Type the exact approval phrase to request a signed approval token.`

## Confirm

Title: `Confirm copy token`

Body: `The token is bound to this candidate, this target, this source hash, and this expiry time. It cannot be reused for another file.`

## Execute Disabled

Title: `Copy execution locked`

Body: `Preview, dry-run, and confirmation are ready. Execution is disabled until a separate operator approval file and feature flag are present.`

## Error States

Path rejected: `This path is outside the copy allowlist.`

Target exists: `The target already exists. Overwrite is not allowed.`

Qwen rejected: `Qwen can advise, but it cannot execute copy actions.`

Cloud rejected: `Cloud-derived private write requests are not allowed.`

Token expired: `The approval token has expired. Run dry-run and confirm again.`

Token mismatch: `The token does not match this copy candidate.`
