# Changelog

## 0.2.0

- Adds secret-free first-run NAS discovery from existing mounts, passive local
  network state, mDNS and explicitly supplied hosts; no subnet scan, login or
  mount occurs during discovery.
- Adds guided candidate selection while keeping the dedicated share scope and
  credentials as explicit user decisions.
- Supports either the S100P local Qwen runtime or an OpenAI-compatible cloud
  provider. Cloud credentials are stored in a protected target-only file and
  private/NAS-scoped prompts are blocked from cloud egress.
- Adds separate clean-install evidence for the cloud-provider path.
- Documents the single-instance systemd invariant for the Qwen gateway and the
  tested rollback-safe migration from a legacy user unit to the system unit.

## 0.1.0

- Adds one-stop S100P release install, upgrade, uninstall, and verification
  helpers.
- Adds demo corpus download/generation scripts and Stage 10 release gates.
- Keeps third-party media, model weights, private user data, and secrets out of
  the default release package.
