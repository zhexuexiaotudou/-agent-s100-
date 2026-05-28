# Baseline Progress: B-003 Semantic Vision Caption Readiness

Date: 2026-05-28

This note records the B-003 follow-up after the NAS-backed metadata image
caption index was already working. The purpose was to answer whether the board
is ready for semantic image captions, not just deterministic metadata captions.

## New Probe

```text
script: scripts/probes/vision_caption_readiness_probe.sh
tool_id: vision_caption_readiness_probe
mode: read-only
default input: /mnt/nas/openclaw/photos
default output: /mnt/nas/openclaw/reports/image-captions
```

The probe checks:

- Supported image count under the approved photos directory.
- Python/Node availability.
- Local Python vision/runtime modules: PIL, cv2, torch, transformers,
  onnxruntime, and openvino.
- Local model-like files under approved model directories.
- Whether the host has a candidate local semantic caption runtime.

It does not call external APIs, upload images, or infer image content.

## NAS Runner Evidence

```text
report: /mnt/nas/openclaw/reports/image-captions/vision_caption_readiness_20260528-230810.md
verdict: blocked_no_semantic_runtime
image files: 1
python3: yes
node: yes
PIL: yes
cv2: yes
torch: yes
transformers: yes
onnxruntime: yes
openvino: yes
local model-like files: 0
semantic runtime: no
```

## OpenClaw Tool Evidence

After restarting `openclaw-gateway.service`, the narrow OpenClaw tool path also
called the same probe:

```text
tool_id: vision_caption_readiness_probe
report: /root/.openclaw/workspace/reports/image-captions/vision_caption_readiness_20260528-230826.md
verdict: blocked_no_semantic_runtime
image count: 1
local model-like file count: 0
semantic runtime: no
```

## Tracking Impact

B-003 remains `doing`.

What is verified:

- NAS-backed metadata caption and JSONL indexing are working.
- The OpenClaw allowlisted tool path can run the B-003 readiness check.
- The board has useful runtime libraries, but no local vision model files were
  found in the checked model directories.

Remaining gap:

- Semantic image captioning requires an installed or mounted local vision model,
  or a deliberate baseline decision that B-003 v1 is metadata-only.

Current recommendation:

- Do not mark semantic captions as verified.
- For the teacher-facing baseline, report B-003 as "metadata image indexing
  verified; semantic captioning blocked by missing local model".
