# Baseline Progress: Browser Smoke

Date: 2026-05-27

## Status

| Item | Status | Evidence |
| --- | --- | --- |
| A-007 local browser smoke | verified path | `browser_smoke_probe` opened a local page, verified the marker, captured a PNG, and returned `verdict: ok`. |
| A-007 OpenClaw plugin trigger | verified path | `s100p_run_probe` ran `browser_smoke_probe` and returned the report and screenshot paths. |
| A-007 NAS-backed output | pending | `/mnt/nas/openclaw/reports` is not mounted yet. |

## Runtime Discovery

Initial board state:

```text
chromium=missing
chromium-browser=missing
google-chrome=missing
firefox=/usr/bin/firefox
browser plugin=loaded
```

The stock OpenClaw browser plugin first returned:

```text
verdict: no_browser_installed
```

because it requires a Chromium-family browser. Firefox being present was not enough.

## Chromium Installation

Installed:

```bash
DEBIAN_FRONTEND=noninteractive apt-get install -y chromium-browser
```

Result:

```text
/usr/bin/chromium-browser
Chromium 148.0.7778.167 snap
```

The Ubuntu package installs Chromium as a snap. Direct screenshots to `/root/.openclaw/...` fail under snap confinement, so the probe captures under `/root/snap/chromium/common` and then copies the PNG into the OpenClaw workspace.

## Direct Headless Evidence

Direct Chromium test using the snap common directory succeeded:

```text
direct_exit=0
/root/snap/chromium/common/openclaw-browser-smoke/direct_chromium.png 25085 bytes
/root/.openclaw/workspace/reports/browser-smoke/direct_chromium_common.png 25085 bytes
magic=89504e470d0a1a0a
```

## Allowlist Runner Evidence

Runner command:

```bash
/root/.openclaw/workspace/scripts/run_allowlisted_tool.sh \
  browser_smoke_probe \
  /root/.openclaw/workspace/reports/browser-smoke
```

Report:

```text
/root/.openclaw/workspace/reports/browser-smoke/browser_smoke_20260527-042032.md
```

Observed report facts:

```text
visible_marker: yes
screenshot_status: captured
screenshot_path: /root/.openclaw/workspace/reports/browser-smoke/browser_smoke_20260527-042032.png
png_magic: 89504e470d0a1a0a
verdict: ok
```

Screenshot:

```text
/root/.openclaw/workspace/reports/browser-smoke/browser_smoke_20260527-042032.png
size: 25855 bytes
```

## OpenClaw Plugin Evidence

The OpenClaw agent used the real `s100p_run_probe` tool:

```text
runId: ba47a596-91af-4773-bad2-30d72bafc893
tool_id: browser_smoke_probe
report: /root/.openclaw/workspace/reports/browser-smoke/browser_smoke_20260527-042131.md
screenshot: /root/.openclaw/workspace/reports/browser-smoke/browser_smoke_20260527-042131.png
screenshot_status: captured
visible_marker: yes
verdict: ok
```

## Current A-007 Verdict

A-007 is verified for the local workspace fallback path.

It is not yet NAS-backed because `/mnt/nas/openclaw` is not mounted. After A-003 completes, re-run `browser_smoke_probe` with output under `/mnt/nas/openclaw/reports`.
