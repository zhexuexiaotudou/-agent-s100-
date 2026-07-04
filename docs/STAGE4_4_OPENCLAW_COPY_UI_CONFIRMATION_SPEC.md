# Stage 4.4 OpenClaw Copy UI Confirmation Spec

The OpenClaw UI should expose copy as a high-friction operator confirmation flow, not as a chat-autonomous action.

## Preview Screen

Show:

- action: copy
- source display name from the user's selected candidate, with raw path hidden by default
- target collection name
- file size
- source hash prefix
- target existence status
- risk class: bounded single-file copy
- statement that no write has occurred

Do not show:

- raw private file content
- full NAS absolute paths
- any global NAS browse scope
- buttons for delete, move, rename, chmod, chown, overwrite, or recursive operations

## Dry-Run Screen

Show:

- planned effect: create one target file if absent
- blocked alternatives: delete, move, rename, overwrite, chmod, chown, recursive
- rollback plan: remove only the created target after hash verification
- approval phrase
- token expiry window
- audit trail destination

The primary command is confirm. There is no execute button before the phrase is accepted.

## Confirm Screen

Require:

- exact phrase match
- operator identity
- visible TTL
- one candidate fingerprint
- one action type

After confirmation, the UI can show token issued, but execute remains disabled unless the backend feature flag and approval file are present.

## Execute Screen

Stage 4.4 default state is disabled. When disabled, show:

- copy execution is locked
- preview, dry-run, and confirm are available for review
- execution requires a separate operator approval packet
