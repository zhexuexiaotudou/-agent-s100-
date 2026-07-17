# Offline deployment-wizard hardening (2026-07-17)

## Scope

This change repairs the non-Dream7B S100P/NAS deployment path while both devices
are offline. It adds a truthful clean-install simulation but does not claim real
hardware, NAS, model inference, systemd persistence, reboot survival or
production acceptance.

## Repaired items 1-7

1. NAS apply now writes one managed fstab block, backs up the previous fstab,
   mounts the target and verifies `findmnt` source/type plus a Personal-root
   write as the unprivileged service user. A created local directory cannot
   masquerade as NAS.
2. Required Qwen model/runtime paths are validated and written to the same
   environment file consumed by all rendered service units.
3. Qwen health separates process liveness from inference readiness and returns
   503 when runtime/config/lib/HBM inputs are absent.
4. First run initializes the portal's actual identity SQLite database; the
   disconnected random admin-token file was removed.
5. Install verification and product smoke obtain/use a real bearer session.
   Tokens and passwords are excluded from reports.
6. `--rollback-from` is implemented, unsafe uninstall roots are rejected, and
   the deleted nightly timer is no longer referenced.
7. Real installation preflight blocks on S100P/BPU/systemd/NAS requirements;
   simulation explicitly bypasses hardware and always reports
   `production_verified=false`.

## Offline acceptance

GitHub Actions now syntax-checks every release shell script and runs
`stage10_release_clean_install_gate.py`. The gate creates fake path fixtures,
then verifies app/venv copy, simulated fstab, rendered units, real administrator
identity database, absence of the obsolete token file, and the non-production
label. The full Python regression suite and model-free package build remain in
the same workflow.

## Deferred live gates

After S100P and NAS return online, run in order:

1. `s100p_connectivity_verified`
2. `nas_mount_acl_verified`
3. `clean_install_verified`
4. `services_persistent_verified` (including reboot)
5. `local_model_paths_verified` and Qwen inference
6. `authenticated_product_smoke_verified`
7. `upgrade_rollback_verified`
8. `production_acceptance_verified`
