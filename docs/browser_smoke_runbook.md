# Browser Smoke Runbook

This runbook supports A-007: browser automation smoke testing on the S100P.

## Goal

Open a local test page, verify a visible marker, capture a screenshot, and write the result under the OpenClaw workspace or NAS reports directory.

The first verified implementation uses a narrow allowlisted probe instead of unrestricted shell:

```text
scripts/probes/browser_smoke_probe.sh
```

## Execution

Through the allowlist runner:

```bash
scripts/run_allowlisted_tool.sh browser_smoke_probe /root/.openclaw/workspace/reports/browser-smoke
```

Through the OpenClaw plugin:

```text
s100p_run_probe tool_id=browser_smoke_probe
```

## Output

The probe writes:

```text
browser_smoke_YYYYmmdd-HHMMSS.md
browser_smoke_YYYYmmdd-HHMMSS.png
browser_smoke_YYYYmmdd-HHMMSS.log
```

The report includes:

- URL.
- Browser command and version.
- Marker visibility.
- Screenshot status.
- Screenshot path.
- PNG magic bytes.
- Verdict.

## Implementation Notes

On this S100P, Ubuntu's `chromium-browser` package installs Chromium as a snap. The snap is allowed to write under:

```text
/root/snap/chromium/common
```

The probe captures the screenshot there first, then copies the PNG into:

```text
/root/.openclaw/workspace/reports/browser-smoke
```

This avoids snap confinement denying writes directly into `/root/.openclaw`.

## Acceptance

A-007 local fallback is verified when:

- `visible_marker: yes`
- `screenshot_status: captured`
- `png_magic: 89504e470d0a1a0a`
- `verdict: ok`
- The screenshot path exists and has non-zero size.

NAS-backed acceptance still requires re-running the same probe with output under:

```text
/mnt/nas/openclaw/reports
```
