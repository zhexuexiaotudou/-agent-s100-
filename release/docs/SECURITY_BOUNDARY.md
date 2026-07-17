# Security Boundary

The release defaults to loopback/LAN access, admin token auth, NAS path
allowlists, delete disabled, overwrite disabled, no uncontrolled move/rename,
no Qwen autonomous execution, no hidden chain-of-thought storage, and no private
raw cloud egress.

Cloud API keys are read from a protected target-only file and are never emitted
in install reports, environment summaries, support bundles or release archives.
Cloud mode forwards only public, non-NAS prompts; privacy-classified and
NAS-scoped prompts remain on the local allowlisted tool path.
