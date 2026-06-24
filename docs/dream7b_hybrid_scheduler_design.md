# Dream7B Hybrid Scheduler Design

Date: 2026-06-19

This design keeps the current queue baseline as the production default and
introduces true-batch only as an isolated experimental backend.

## Target Architecture

```text
production queue baseline
+ experimental true-batch backend
+ hybrid scheduler
+ unified telemetry
+ safe promotion gate
```

Current production endpoint remains:

```text
http://127.0.0.1:18888/v1
```

Experimental endpoint, if installed later:

```text
http://127.0.0.1:18889/v1
```

## Backend Options

Supported backend modes:

- `queue_baseline`
- `true_batch_b4_seq16`
- `hybrid`

Environment flags for a future isolated service:

```text
DREAM7B_BACKEND=queue_baseline
DREAM7B_BACKEND=true_batch_b4_seq16
DREAM7B_BACKEND=hybrid
```

Do not replace `dream7b-bpu-batch-queue.service`. A future experiment should
use a separate service such as:

```text
dream7b-true-batch-experimental.service
```

## Routing Policy

Default routing:

- Single request: `queue_baseline`
- Low concurrency: `queue_baseline`
- Latency-sensitive request: `queue_baseline`
- Prefill phase: `queue_baseline`
- Decode phase with enough batchable requests: `true_batch_b4_seq16`
- True-batch error: fallback to `queue_baseline`
- Queue wait beyond threshold: route to `queue_baseline`

Pseudo-logic:

```python
if request.phase == "prefill":
    route = "queue_baseline"

elif request.latency_sensitive:
    route = "queue_baseline"

elif queue_wait_ms > max_batch_wait_ms:
    route = "queue_baseline"

elif decode_queue.batchable_count >= min_true_batch_slots:
    route = "true_batch_b4_seq16"

else:
    wait_briefly_or_route_baseline()
```

## Policy Parameters

- `max_batch_wait_ms`
- `min_true_batch_slots`
- `max_padding_ratio`
- `max_queue_depth`
- `fallback_on_error`
- `fallback_on_latency_spike`
- `enable_true_batch_decode`
- `enable_true_batch_prefill`
- `experimental_port`
- `production_port`
- `true_batch_artifact_root`
- `queue_baseline_api_base`
- `promotion_gate_profile`

Initial suggested values are in `configs/dream7b_backend_policy.yaml`.

## Failure Handling

Fallback is mandatory.

Fallback triggers:

- true-batch runtime exception
- missing HBM artifact
- shape mismatch
- manifest/hash verification failure
- BPU lock timeout
- failed job count above zero
- latency spike against policy threshold
- queue wait exceeds `max_batch_wait_ms`

Fallback action:

1. Mark request with fallback reason.
2. Route to `queue_baseline`.
3. Preserve OpenAI-compatible API response shape.
4. Emit telemetry event.
5. Do not retry true-batch indefinitely.

## Unified Telemetry

Every backend comparison must include:

- full-window `avg_bpu_loading`
- `avg_nonzero_bpu_loading`
- tokens/s
- TTFT
- TPOT
- P50/P95/P99 latency
- queue wait time
- failed jobs
- final logits time
- CPU/RAM usage

Do not judge promotion using only active-window or nonzero BPU metrics.

## Promotion Rule

True-batch can be discussed for broader routing only if it clears the promotion
gate across multiple full-window runs:

- `failed_jobs = 0`
- `avg_bpu_loading >= queue_baseline - 1%`
- `tokens/s >= queue_baseline + 15%`
- P95 TTFT degradation <= `10%`
- P95 TPOT degradation <= `10%`
- no obvious final logits regression

Preferred target:

- `avg_bpu_loading >= 93.5%`
- `tokens/s >= queue_baseline + 20%`
- `failed_jobs = 0`
- no material P95 latency regression
