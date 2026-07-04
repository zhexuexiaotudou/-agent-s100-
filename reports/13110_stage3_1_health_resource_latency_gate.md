# stage3_1_health_resource_latency_gate

- verdict: `ok_stage3_1_health_resource_latency_gate`
- generated_at: `2026-07-04T11:21:22.294318+08:00`
- passed: `8/8`

## Checks

- `PASS` dispatcher p50/p95/p99 latency captured
- `PASS` dispatcher p99 below 2000 ms
- `PASS` Qwen/OpenClaw health p99 captured
- `PASS` Qwen service active/enabled before and after
- `PASS` protected ports unchanged
- `PASS` no OOM or Dream process interference
- `PASS` harness RSS growth under 128 MiB
- `PASS` health before/after OK

## Failures

- none

## Detail

```json
{
  "latency_summary": {
    "dispatcher_p50_ms": 160.778,
    "dispatcher_p95_ms": 232.263,
    "dispatcher_p99_ms": 927.191,
    "qwen_health_p99_ms": 1.233,
    "openclaw_health_p99_ms": 733.461
  },
  "resource_summary": {
    "rss_before_kb": 20608,
    "rss_after_kb": 25472,
    "rss_growth_kb": 4864,
    "oom_count": 0,
    "dream_process_observed": true,
    "dream_process_interference_count": 0
  }
}
```
