# Image Caption Baseline Runbook

This runbook supports B-003: image caption baseline.

## Goal

Create a low-risk searchable image index before adding semantic vision
captioning.

The first baseline does not send images to an external model. It generates:

- A Markdown image index.
- A JSONL index for later vector indexing.
- File path, size, mtime, SHA256, and dimensions when available.
- A deterministic caption from the directory and file name.

This gives the NAS photo workflow a verifiable local fallback while keeping
privacy and cost under control.

## Entry Point

Use the allowlist runner:

```bash
scripts/run_allowlisted_tool.sh image_caption_probe [photos_dir] [report_dir]
```

Default local fallback:

```text
photos_dir: /root/.openclaw/workspace/photos
report_dir: /root/.openclaw/workspace/reports/image-captions
```

NAS-backed path after A-003 is mounted:

```text
photos_dir: /mnt/nas/openclaw/photos
report_dir: /mnt/nas/openclaw/reports/image-captions
```

## OpenClaw Tool

The narrow OpenClaw plugin exposes the same workflow through:

```text
s100p_run_probe
```

with:

```json
{"tool_id":"image_caption_probe"}
```

## Output

The probe writes:

```text
image_caption_index_*.md
image_caption_index_*.jsonl
```

Supported extensions:

```text
.jpg .jpeg .png .gif .webp .bmp
```

## Acceptance

Local readiness is verified when:

- The runner writes a Markdown report under `/root/.openclaw/workspace/reports/image-captions`.
- The runner writes a JSONL sidecar with one record per supported image.
- The OpenClaw agent can call `s100p_run_probe` with `tool_id=image_caption_probe`.

B-003 is not complete until NAS-backed photos are indexed and the project either
adds semantic captions or explicitly accepts metadata captions as the intended
baseline.
