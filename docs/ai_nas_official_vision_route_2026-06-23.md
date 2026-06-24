# AI-NAS Official Vision Route 2026-06-23

## Verdict

`ok_ai_nas_official_vision_route_demo_ready`

This route is scoped to AI-NAS visual capability only. It does not continue
Dream7B optimization and does not change the text service route, port, or
service name.

## Selected First-Release Route

| Capability | First-release choice | Status |
| --- | --- | --- |
| Image object detection | Official S100 YOLOv8/YOLO11 HBM through `dnn_node_example` | Verified on S100P |
| Image classification | Official S100 MobileNetV2/ResNet family | HBM model-info verified |
| OCR / screenshot text | Official S100 PP-OCRv3 det/rec HBM | HBM model-info verified; wrapper pending |
| Image semantic retrieval | NAS CLIP ViT-B/32 files plus existing AI-NAS embedding/search probes | Local fallback verified |
| Video | Extract frames, then run image detector/OCR/classifier | Verified with frame extraction + YOLO |

Video-specific models and complex video understanding are deferred for the
first NodeHub submission.

## Evidence Files

Primary acceptance packet:

- `tmp/ai_nas_official_vision_20260623/official_vision_route_packet_20260623-004840-280778/official_vision_route_packet.md`
- `tmp/ai_nas_official_vision_20260623/official_vision_route_packet_20260623-004840-280778/official_vision_route_packet.json`

S100P image detection evidence:

- `tmp/ai_nas_official_vision_20260623/s100p_yolo_image_demo/ai_nas_yolov8_demo_writable.log`
- `tmp/ai_nas_official_vision_20260623/s100p_yolo_image_demo/render_feedback_0_0.jpeg`
- Result: YOLOv8 returned 9 boxes on the official test image, including
  `person` and `car` detections.

S100P video-frame evidence:

- `tmp/ai_nas_official_vision_20260623/s100p_video_frame_demo/sample.mp4`
- `tmp/ai_nas_official_vision_20260623/s100p_video_frame_demo/frames/frame_001.jpg`
- `tmp/ai_nas_official_vision_20260623/s100p_video_frame_demo/frames/frame_002.jpg`
- `tmp/ai_nas_official_vision_20260623/s100p_video_frame_demo/yolov8_frame.log`
- `tmp/ai_nas_official_vision_20260623/s100p_video_frame_demo/run/render_feedback_0_0.jpeg`
- Result: FFmpeg extracted frames, and YOLOv8 returned 7 boxes on
  `frame_001.jpg`.

AI-NAS local probe evidence:

- `tmp/ai_nas_official_vision_20260623/photo_pipeline_acceptance_20260623-004403-323377/photo_pipeline_acceptance.json`
- `tmp/ai_nas_official_vision_20260623/document_pipeline_acceptance_20260623-004403-327846/document_pipeline_acceptance.json`
- `tmp/ai_nas_official_vision_20260623/image_embedding_extract_20260623-004424-268122/image_embedding_extract.json`
- `tmp/ai_nas_official_vision_20260623/photo_semantic_search_20260623-004424-260440/photo_semantic_search.json`

## Demo Commands

Generate the final packet:

```powershell
py scripts\probes\ai_nas_official_vision_route_packet.py --report-root tmp\ai_nas_official_vision_20260623
```

Run the local AI-NAS photo and OCR/document probes:

```powershell
py scripts\probes\ai_nas_photo_pipeline_acceptance_probe.py --report-root F:\Project\Digua\tmp\ai_nas_official_vision_20260623
py scripts\probes\ai_nas_document_pipeline_acceptance_probe.py --report-root F:\Project\Digua\tmp\ai_nas_official_vision_20260623
```

Run official YOLO on S100P:

```powershell
ssh sunrise@192.168.127.10 "source /opt/tros/humble/setup.bash; mkdir -p /tmp/ai_nas_yolo_demo && cd /tmp/ai_nas_yolo_demo; timeout 20 ros2 launch dnn_node_example dnn_node_example_feedback.launch.py dnn_example_config_file:=config/yolov8workconfig.json dnn_example_image:=config/test.jpg"
```

Run the first-release video route:

```powershell
ssh sunrise@192.168.127.10 "ffmpeg -i input.mp4 -vf fps=1 frames/frame_%03d.jpg; source /opt/tros/humble/setup.bash; cd /tmp/ai_nas_video_frame_demo/run; timeout 20 ros2 launch dnn_node_example dnn_node_example_feedback.launch.py dnn_example_config_file:=config/yolov8workconfig.json dnn_example_image:=/tmp/ai_nas_video_frame_demo/frames/frame_001.jpg"
```

## Remaining Risks

- Windows-side fixture OCR has no local Tesseract runtime. Official PP-OCRv3
  HBM files are present and load on S100P, but the production OCR wrapper is
  still pending.
- NAS CLIP ViT-B/32 files are present, but this Windows run used
  `local_visual_embedding_v1` as the verified fallback because the local
  torch/transformers CLIP runtime is not installed.
- The `sunrise` user could not write to
  `/mnt/nas/openclaw/reports/ai_nas_mvp` during this run, so S100P evidence was
  copied back into local `tmp/` for retention.

## OpenClaw / AI-NAS Integration Boundary

Expose this as a separate visual route, for example:

- `ai-nas-vision-gateway`
- `ai-nas-video-frame-worker`

Return JSON paths and Markdown evidence links to OpenClaw. Do not reuse
Dream7B service names, Dream7B ports, or text-route model aliases.
