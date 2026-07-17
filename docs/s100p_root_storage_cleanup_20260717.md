# S100P root storage cleanup and NAS migration — 2026-07-17

## Scope

This operation reduced S100P root-filesystem pressure without removing system, OpenClaw, BPU, ROS/TROS, or active AI-NAS runtime files. It used two explicit phases:

1. remove low-risk, reproducible caches and old logs;
2. preserve the complete Dream7B HBM tree on NAS, verify every file, then replace the board-local tree with a compatibility symlink.

The live evidence directory is:

```text
/mnt/nas/openclaw/reports/storage/s100p_root_cleanup_20260717
```

## Verified environment

- S100P: Ubuntu 22.04.5 LTS, kernel `6.1.158-rt58-DR-4.0.5-2603031328-g9f678e-g6caa4d`;
- OpenClaw: `2026.6.10 (aa69b12)`, system gateway bound to loopback port `18765`;
- NAS: QNAP TS-264C, NFS export `169.254.143.37:/OpenClawWorkspace`, mounted at `/mnt/nas/openclaw`;
- operator path: `sunrise@192.168.127.10` with key-based SSH;
- review: GPT Pro review is optional for architecture review and is not required for this capacity recovery acceptance.

## Before

- root filesystem: `47,780,933,632` bytes;
- used: `43,552,669,696` bytes;
- available to normal users: `2,177,282,048` bytes;
- usage: `96%`;
- largest removable tree: `/home/sunrise/.cache/openclaw/dream7b-hbm`, `25,586,884,946` bytes across 40 files;
- NAS available: about `1.85 TB`.

## Phase 1: reproducible caches

The operation retained current packages and services while cleaning:

- archived journal entries, retaining about 424 MB of active/current journal data;
- downloaded APT packages;
- root and sunrise npm caches;
- sunrise pip cache;
- Snap download cache and revisions already marked `disabled`.

After phase 1, root usage fell from 96% to 89%, and available space increased from 2.18 GB to 5.46 GB. System OpenClaw, the sunrise AI-NAS portal, and local Qwen remained active.

Evidence:

```text
phase1_before.txt
phase1_after.txt
```

## Phase 2: Dream7B HBM preservation and cutover

The complete local tree was copied without overwriting the existing canonical Dream7B model tree:

```text
source:  /home/sunrise/.cache/openclaw/dream7b-hbm
archive: /mnt/nas/openclaw/models/archive/s100p-local-cache-20260717/dream7b-hbm
```

The copy and deletion gates were:

- source files: 40;
- NAS files: 40;
- source bytes: `25,586,884,946`;
- NAS bytes: `25,586,884,946`;
- source SHA-256 checks: 40/40;
- NAS SHA-256 checks: 40/40;
- manifest SHA-256: `69e105f02ca8e9f01dba652863dd6a1ff7c7e433a5a3fdbf15c58eea3c5480aa`.

Only after all gates passed was the board-local entity removed. The original path now remains compatible through:

```text
/home/sunrise/.cache/openclaw/dream7b-hbm
  -> /mnt/nas/openclaw/models/archive/s100p-local-cache-20260717/dream7b-hbm
```

This preserves historical script defaults, including locally modified calibration and backup variants, instead of redirecting them to a similar but non-identical canonical model tree.

Evidence:

```text
phase2_copy_before.txt
phase2_copy_after.txt
phase2_source.sha256
phase2_source_verify.txt
phase2_nas_verify.txt
phase2_hash_summary.txt
phase2_cutover.txt
phase2_compat_probe.json
```

## Final acceptance

- root usage: 33%;
- root available: `31,023,837,184` bytes, about 31.0 GB;
- total increase in available root space: about 28.85 GB;
- NAS usage: 17%;
- NFS source: `169.254.143.37:/OpenClawWorkspace`;
- link checker: Windows/S100P/NAS/storage/OpenClaw gates passed;
- root compatibility path: readable through the NAS symlink;
- resplit artifact inventory: `ok_dream7b_bpu_resplit_hbm_artifact_inventory_probe`, 8/8 HBM files and manifest hashes verified;
- system OpenClaw, AI-NAS portal and local Qwen: active, HTTP 200.

## Risk and rollback

- Dream7B paths now depend on the NAS mount. This matches the current production runtime design, but Dream7B experiments cannot use the compatibility path while NAS is unavailable.
- The full pre-cutover payload remains under the dated NAS archive path and must not be removed during routine NAS cleanup. The path is evidence-scoped, but no filesystem immutable attribute was applied.
- To roll back, first confirm at least 26 GB of free root space, copy the archive to a temporary board-local directory, verify the same manifest, atomically replace the symlink with the verified local directory, and rerun the compatibility and service gates.
- Gateway exposure, NAS allowlist scope, and robot-control permissions were unchanged.
