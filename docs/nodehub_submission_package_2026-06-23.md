# NodeHub Submission Package 2026-06-23

## Recommended Project Title

AI-NAS Copilot on RDK S100: Local Qwen2.5 Text Entry plus Official Vision
Evidence for Auditable NAS Workflows

## Repository Structure For Submission

Use the current workspace as the source of truth, but present the submission
around these files:

```text
README.md
docs/competition_delivery_2026-06-23.md
docs/nodehub_submission_package_2026-06-23.md
docs/project_retrospective_2026-06-23.md
docs/reusable_toolchain_map_2026-06-23.md
docs/qwen25_ai_nas_text_entry_2026-06-23.md
docs/ai_nas_official_vision_route_2026-06-23.md
scripts/qwen25_openai_gateway.py
scripts/probes/qwen25_ai_nas_acceptance_packet.py
scripts/probes/ai_nas_official_vision_route_packet.py
scripts/probes/ai_nas_competition_final_acceptance_packet.py
configs/qwen25_official_route_policy.json
configs/qwen25_512_multichat_config.json
configs/systemd/qwen25-local-openai-gateway.service
```

Keep large generated artifacts, HBM files, WSL images, and raw `tmp/` payloads
out of the public package unless NodeHub explicitly asks for evidence assets.
Include selected evidence paths and rendered JPEGs in the demo section instead.

## Environment Assumptions

- RDK S100/S100P board is available at `192.168.127.10`.
- NAS is mounted at `/mnt/nas/openclaw`.
- Qwen2.5 gateway service runs on S100P user systemd:
  `qwen25-local-openai-gateway.service`.
- Official S100 model package is installed under `/opt/hobot/model/s100/basic`.
- TROS/Humble environment exists under `/opt/tros/humble`.

## Quick Start

1. Check Qwen2.5 gateway:

   ```bash
   curl -sS http://127.0.0.1:18080/health
   curl -sS http://127.0.0.1:18080/v1/models
   ```

2. Generate text evidence:

   ```powershell
   py -3 scripts\probes\qwen25_ai_nas_acceptance_packet.py
   ```

3. Generate vision evidence:

   ```powershell
   py -3 scripts\probes\ai_nas_official_vision_route_packet.py --report-root tmp\ai_nas_official_vision_20260623
   ```

4. Generate final acceptance evidence:

   ```powershell
   py -3 scripts\probes\ai_nas_competition_final_acceptance_packet.py
   ```

## Evaluation Points

Engineering completeness:

- Official model path, not an unsupported Dream7B path.
- Separate text and vision routes.
- S100P-side service health and model list.
- Bounded NAS tool execution.
- Markdown/JSON reports for traceability.

Safety:

- Read-only or copy-only workflows.
- No delete, move, overwrite, arbitrary shell, or hidden destructive action.
- Explicit warnings for incomplete OCR wrapper and Qwen 1024 HBM memory limit.

Innovation:

- RDK S100 acts as an attachable AI layer for an existing NAS.
- The system combines text, document, photo, screenshot, and video-frame
  evidence in an auditable local workflow.

## Demo Narrative

Use this short script in the presentation:

1. A low-cost NAS stores personal files. RDK S100 adds local AI and tool
   execution without replacing the NAS OS.
2. A Chinese request enters through official Qwen2.5.
3. The gateway routes evidence requests to allowlisted AI-NAS tools.
4. The tools return inventory, search, case packet, and folder RAG reports.
5. Official S100 YOLO detects objects in images and extracted video frames.
6. The final acceptance packet links all evidence and lists remaining risks.

## Files Not To Submit As Core Source

These are useful local or historical assets, but not core NodeHub source:

- `tmp/`
- `product/`
- `downloads/`
- `logs/`
- Dream7B-specific deployment artifacts
- WSL VHDX or build roots
- raw HBM blobs unless NodeHub asks for model artifacts
