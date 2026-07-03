# stage2_6_sidecar_resource_under_research_load_gate

- verdict: `ok_stage2_6_sidecar_resource_under_research_load_gate`
- generated_at: `2026-07-03T12:29:47.729200+08:00`
- passed: `7/7`

## Checks

- `PASS` Dream/llama processes observed before and after
- `PASS` Dream/llama processes not stopped by sidecar
- `PASS` sidecar RSS <= 512 MB
- `PASS` sidecar CPU recorded and bounded for test process
- `PASS` no OOM signal observed
- `PASS` Qwen/OpenClaw health remains OK
- `PASS` Qwen/OpenClaw p95 latency regression <= 10 percent or documented

## Failures

- none

## Detail

```json
{
  "derived": {
    "sidecar_rss_mb": 17.5,
    "sidecar_cpu": 0.0,
    "before_dream_pids": [
      41889,
      697792,
      697793,
      697794
    ],
    "after_dream_pids": [
      41889,
      697792,
      697793,
      697794
    ],
    "latency_regression_within_10_percent": false,
    "latency_regression_documented": true
  },
  "soak_summary": {
    "mode": "soak",
    "run_count": 100,
    "concurrency": 4,
    "allowed_count": 85,
    "denied_count": 15,
    "allowed_success_rate": 1.0,
    "allowed_qwen_http_ok_rate": 0.9411764705882353,
    "allowed_qwen_semantic_success_rate": 0.0,
    "valid_structured_response_rate": 0.0,
    "denial_correctness": 1.0,
    "leak_count": 0,
    "fallback_count": 85,
    "qwen_latency_ms": {
      "p50": 3136.682,
      "p95": 3255.102,
      "p99": 3261.594
    },
    "dispatcher_latency_ms": {
      "p50": 165.117,
      "p95": 265.669,
      "p99": 957.572
    },
    "qwen_health_ms_before": {
      "p50": 2.047,
      "p95": 4.201,
      "p99": 4.201,
      "ok": true
    },
    "qwen_health_ms_during": {
      "p50": 1.997,
      "p95": 5.427,
      "p99": 6.522,
      "ok": true
    },
    "qwen_health_ms_after": {
      "p50": 1.144,
      "p95": 1.46,
      "p99": 1.46,
      "ok": true
    },
    "openclaw_health_ms_before": {
      "p50": 439.711,
      "p95": 462.548,
      "p99": 462.548,
      "ok": true
    },
    "openclaw_health_ms_during": {
      "p50": 1268.321,
      "p95": 1461.163,
      "p99": 1530.898,
      "ok": true
    },
    "openclaw_health_ms_after": {
      "p50": 605.446,
      "p95": 612.098,
      "p99": 612.098,
      "ok": true
    }
  }
}
```
