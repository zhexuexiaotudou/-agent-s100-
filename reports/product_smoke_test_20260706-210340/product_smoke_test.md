# Product Smoke Test

- verdict: `ok_product_smoke_test`
- generated_at: `2026-07-06T21:03:40.640115+08:00`
- base_url: `http://127.0.0.1:8765`
- failure_count: `0`
- warning_count: `4`
- production_ready: `True`
- readiness_verdict: `ready_ai_nas_production_readiness_gate`
- yolo_runtime_target: `s100p_bpu_hbm`
- yolo_detection_count: `0`

## Failures

- None.

## Warnings

- `degraded_modules:person_attribute,yolo`
- `yolo_detection_count_empty_real_s100p_backend_completed_without_boxes`
- `person_attribute_degraded_without_yolo_person_boxes`
- `person_attribute_detection_count_empty`

## Endpoints

- `health` 200 982.87ms `/api/health`
- `product_status` 200 5232.583ms `/api/product/status`
- `product_evidence` 200 374.434ms `/api/product/evidence/latest`
- `harness` 200 64.929ms `/api/harness/status`
- `yolo_status` 200 60.401ms `/api/yolo-index/status`
- `multimodal_status` 200 1395.507ms `/api/multimodal-search/status`
- `person_attribute_status` 200 14.303ms `/api/person-attribute/status`
- `ai_space_status` 200 14.643ms `/api/ai-space/status`
- `smart_classification_status` 200 27.384ms `/api/smart-classification/status`
- `smart_naming_status` 200 17.265ms `/api/smart-naming/status`
- `auto_organizer_status` 200 19.615ms `/api/auto-organize/status`
- `assistant_trace_status` 200 382.488ms `/api/assistant/trace/status`
- `document_rag_status` 200 12.187ms `/api/document-rag/status`
- `subtitle_status` 200 13.44ms `/api/subtitle/status`
- `jobs_status` 200 8.833ms `/api/jobs/status`

## Audit

- method: `HTTP GET smoke only`
- source_files_modified: `False`
- personal_source_modified: `False`
- service_restart_performed: `False`
- delete_performed: `False`
- uncontrolled_move_performed: `False`
- overwrite_performed: `False`
- writes: `product smoke JSON/Markdown report only`
