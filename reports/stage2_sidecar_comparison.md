# Stage 2 Sidecar Comparison

- final_verdict: `ready_for_more_readonly_sidecar_trials`

## Context Comparison

| Scenario | Stage1 chars | Stage2 chars | Stage1 tools | Stage2 tools |
|---|---:|---:|---:|---:|
| `nas_search_read_only` | 1397 | 1466 | 1 | 3 |
| `nas_denied_acl_search` | 1405 | 1475 | 1 | 3 |
| `document_report_generation` | 1512 | 1587 | 2 | 5 |

## Limitations

- mock sidecar only
- read-only bridge dry-run
- no real Zleap package installed
- Qwen gateway explicitly unavailable in this Windows run

## Recommendation

Continue read-only sidecar trials; do not enter Stage 3 yet.
