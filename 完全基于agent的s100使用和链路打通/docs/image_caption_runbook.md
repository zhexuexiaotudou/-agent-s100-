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

For semantic-caption readiness only, use:

```json
{"tool_id":"vision_caption_readiness_probe"}
```

This readiness probe is read-only. It checks local image counts, installed
vision/runtime libraries, and model-like files under approved model directories.
It does not upload images or call an external vision API.

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

## 2026-05-28 Semantic Readiness Result

Current NAS and OpenClaw tool evidence both return:

```text
verdict: blocked_no_semantic_runtime
image files: 1
runtime libraries: PIL/cv2/torch/transformers/onnxruntime/openvino present
local model-like files: 0
semantic runtime: no
```

Evidence files:

```text
/mnt/nas/openclaw/reports/image-captions/vision_caption_readiness_20260528-230810.md
/root/.openclaw/workspace/reports/image-captions/vision_caption_readiness_20260528-230826.md
```

Tracking decision: metadata image caption and JSONL indexing are verified for
the current baseline. Semantic captions remain blocked until a local vision
model is installed or mounted, unless the first baseline explicitly scopes B-003
to metadata-only indexing.
