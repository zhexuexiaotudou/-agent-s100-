# Dream7B Route A Quality Boundary Packet

- generated_at: `2026-06-22T18:39:39.040065+08:00`
- verdict: `ok_dream7b_route_a_quality_boundary_packet`
- ready_for_demo: `True`
- error_count: `0`
- warning_count: `0`
- route_a_product_path: `OpenClaw -> 18888 -> diffuse-resident -> Dream7B GGUF`

## Fast Path

- ready: `True`
- case_count: `4`
- max_first_content_ms: `2.713`

| id | path | backend_invoked | first_content_ms | content | errors |
| --- | --- | --- | ---: | --- | --- |
| ready_probe | gateway_fast_ready | False | 2.713 | Ready | [] |
| english_identity | gateway_fast_identity | False | 2.619 | 我是 Dream7B-S100P-local，本地运行在 S100P 上，通过 OpenClaw 网关提供对话能力。 | [] |
| chinese_identity | gateway_fast_identity | False | 2.445 | 我是 Dream7B-S100P-local，本地运行在 S100P 上，通过 OpenClaw 网关提供对话能力。 | [] |
| local_status | gateway_fast_local_status | False | 2.378 | 是的，我通过本地 S100P 上的 Dream7B 网关运行；通用回答会交给本地 Dream7B 文本后端。 | [] |

## Generic Generation Boundary

- tracked: `True`
- promotion_claim: `False`
- interpretation: `generic resident output is recorded as a latency/quality boundary, not as a solved product-quality path`

| id | path | backend_invoked | elapsed_ms | content | warnings |
| --- | --- | --- | ---: | --- | --- |
| generic_math_boundary | gateway_diffuse_resident | True | 6688.118 | 2 | [] |

## Source Reports

- fast_path_regression: exists=`True` verdict=`ok_dream7b_fast_path_regression` path=`/mnt/nas/openclaw/reports/models/dream7b_fast_path_regression_20260622-174547/dream7b_fast_path_regression.json`
- first_response_slo: exists=`True` verdict=`ok_dream7b_first_response_slo_tier_guard` path=`/mnt/nas/openclaw/reports/models/dream7b_first_response_slo_tier_guard_20260622-174823/dream7b_first_response_slo_tier_guard.json`
- openclaw_entry_demo: exists=`True` verdict=`ok_openclaw_entry_demo_probe` path=`/mnt/nas/openclaw/reports/models/openclaw_entry_demo_20260622-174732/openclaw_entry_demo.json`
- route_a_demo_readiness: exists=`True` verdict=`ok_ai_nas_route_a_demo_readiness_packet` path=`/mnt/nas/openclaw/reports/models/ai_nas_route_a_demo_readiness_packet_20260622-182319/ai_nas_route_a_demo_readiness_packet.json`

## Errors

- none

## Warnings

- none
