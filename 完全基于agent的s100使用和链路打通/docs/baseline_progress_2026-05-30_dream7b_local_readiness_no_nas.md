# Baseline Progress: Dream 7B Local Readiness Without NAS

Date: 2026-05-30

The half-hour audit gate currently allows only non-NAS read-only work:

```text
audit report: logs/baseline-audit/baseline_audit_20260530-151903.md
decision: continue-non-nas-readonly-only
NAS: unreachable from S100P
OpenClaw: active
S100P SSH: ok
```

## Script Update

`scripts/probes/dream7b_readiness_probe.sh` now skips
`/mnt/nas/openclaw/models` unless `/mnt/nas/openclaw` is a real NFS/CIFS mount.
This avoids blocking on the current autofs-only NAS mount point.

Validation:

```text
remote bash -n: pass
remote install path: /root/.openclaw/workspace/scripts/probes/dream7b_readiness_probe.sh
```

## Read-Only B-003 Evidence

Command path:

```text
sudo -n bash /root/.openclaw/workspace/scripts/run_allowlisted_tool.sh \
  dream7b_readiness_probe \
  /root/.openclaw/workspace/reports/models
```

Report:

```text
/root/.openclaw/workspace/reports/models/dream7b_readiness_20260530-152249.md
```

Key result:

```text
verdict: blocked_no_model
memory total: 21.3 GiB
memory available: 19.1 GiB
runtime summary: llama.cpp,torch-transformers
candidate model-like files: 0
Dream-named files: 0
/mnt/nas/openclaw/models: skipped_not_mounted (current fstype: autofs)
/root/.openclaw/workspace/models: missing
/home/sunrise/models: missing
```

## Known NAS Address Recheck

Targeted checks from S100P did not find the NAS at the prior static IP or common
fallback addresses:

```text
169.254.110.209: ping_no
169.254.100.100: ping_no
169.254.8.1: ping_no
169.254.8.100: ping_no
169.254.8.254: ping_no
192.168.137.100: ping_no
192.168.137.101: ping_no
192.168.137.254: ping_no
```

Windows-side TCP checks to the previous NAS target also failed for:

```text
169.254.110.209:80
169.254.110.209:443
169.254.110.209:8080
169.254.110.209:445
```

## Tracking Impact

B-003 remains `doing`. The S100P has local runtime candidates for a bounded
Dream 7B/local DLM smoke test, but no model files are available in approved
local paths. NAS-backed model discovery remains held until the NAS direct link
responds again.
