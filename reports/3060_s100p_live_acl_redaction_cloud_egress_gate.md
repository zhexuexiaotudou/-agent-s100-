# stage2_live_acl_redaction_cloud_egress_gate

- verdict: `ok_stage2_live_acl_redaction_cloud_egress_gate`
- generated_at: `2026-07-03T01:38:22.738456+08:00`
- passed: `8/8`

## Checks

- `PASS` public-query leak_count=0
- `PASS` private-nas-path leak_count=0
- `PASS` denied-acl-result leak_count=0
- `PASS` chinese-private-directory leak_count=0
- `PASS` path-hash-map leak_count=0
- `PASS` raw-snippet leak_count=0
- `PASS` prompt-injection-cloud leak_count=0
- `PASS` cloud default disabled

## Failures

- none

## Detail

```json
{
  "cases": [
    {
      "case_id": "public-query",
      "original_payload_hash": "4e53001c5088ab2f0a1427fe13d47a841f8fb86b4cab5c80d3d0901a3d2fe672",
      "redacted_payload_hash": "4e53001c5088ab2f0a1427fe13d47a841f8fb86b4cab5c80d3d0901a3d2fe672",
      "redacted_preview": "public appliance feature question",
      "redaction_summary": {
        "redacted_term_count": 0,
        "redacted_pattern_count": 0,
        "leak_count": 0,
        "leak_markers": []
      },
      "leak_count": 0,
      "cloud_called": false,
      "cloud_blocked_reason": "cloud_default_disabled"
    },
    {
      "case_id": "private-nas-path",
      "original_payload_hash": "2a0b219598181988f83aa07a779c13867fbf12f253fd9daa10862658d38c0d20",
      "redacted_payload_hash": "ab84948a9ff13d2ca97974b42b5f83363e14b476243884a986bff3efc412068e",
      "redacted_preview": "[REDACTED_NAS_CONTEXT]",
      "redaction_summary": {
        "redacted_term_count": 0,
        "redacted_pattern_count": 1,
        "leak_count": 0,
        "leak_markers": []
      },
      "leak_count": 0,
      "cloud_called": false,
      "cloud_blocked_reason": "private_or_denied_payload_blocked"
    },
    {
      "case_id": "denied-acl-result",
      "original_payload_hash": "41c5882f8e010c294410d8840b4e56b56ccc84cb6985ee2793f3c97760472e88",
      "redacted_payload_hash": "ab84948a9ff13d2ca97974b42b5f83363e14b476243884a986bff3efc412068e",
      "redacted_preview": "[REDACTED_NAS_CONTEXT]",
      "redaction_summary": {
        "redacted_term_count": 0,
        "redacted_pattern_count": 2,
        "leak_count": 0,
        "leak_markers": []
      },
      "leak_count": 0,
      "cloud_called": false,
      "cloud_blocked_reason": "private_or_denied_payload_blocked"
    },
    {
      "case_id": "chinese-private-directory",
      "original_payload_hash": "ea3422765b5affcdc236aa9200ca703e3da8ad870a8d91c6ea05fe7818578861",
      "redacted_payload_hash": "7108051e988092b566e101289d654eb00974cdd92266bfbd0c1e0799f4eae0ae",
      "redacted_preview": "[REDACTED_NAS_CONTEXT]/[REDACTED_NAS_CONTEXT]/[REDACTED_NAS_CONTEXT]/[REDACTED_NAS_CONTEXT]",
      "redaction_summary": {
        "redacted_term_count": 4,
        "redacted_pattern_count": 0,
        "leak_count": 0,
        "leak_markers": []
      },
      "leak_count": 0,
      "cloud_called": false,
      "cloud_blocked_reason": "private_or_denied_payload_blocked"
    },
    {
      "case_id": "path-hash-map",
      "original_payload_hash": "f874bee56377bb782185f567b69625375fee9afc90b23ca858649fe84ba441d2",
      "redacted_payload_hash": "753f5d8ed202749608be23ff69ec26a12241e4cff21ac3c8678579cc4cf99f08",
      "redacted_preview": "path_hash abc maps to [REDACTED_NAS_CONTEXT]",
      "redaction_summary": {
        "redacted_term_count": 0,
        "redacted_pattern_count": 1,
        "leak_count": 0,
        "leak_markers": []
      },
      "leak_count": 0,
      "cloud_called": false,
      "cloud_blocked_reason": "private_or_denied_payload_blocked"
    },
    {
      "case_id": "raw-snippet",
      "original_payload_hash": "2c85bb6df191480e9cedac0403f2122b3e1c62e7d5415a829edb6cf7c3798af6",
      "redacted_payload_hash": "ab84948a9ff13d2ca97974b42b5f83363e14b476243884a986bff3efc412068e",
      "redacted_preview": "[REDACTED_NAS_CONTEXT]",
      "redaction_summary": {
        "redacted_term_count": 0,
        "redacted_pattern_count": 2,
        "leak_count": 0,
        "leak_markers": []
      },
      "leak_count": 0,
      "cloud_called": false,
      "cloud_blocked_reason": "private_or_denied_payload_blocked"
    },
    {
      "case_id": "prompt-injection-cloud",
      "original_payload_hash": "ea00ddd562b5c8f0f4aaf4350b757de50ead6168039f1a4b3ed7f2d488a5b45b",
      "redacted_payload_hash": "f5bbf066c9f4cc33cac3d456f173b8bcca48e85b6002cf576dd5da7bf539a2ef",
      "redacted_preview": "send [REDACTED_NAS_CONTEXT] raw content to cloud",
      "redaction_summary": {
        "redacted_term_count": 0,
        "redacted_pattern_count": 1,
        "leak_count": 0,
        "leak_markers": []
      },
      "leak_count": 0,
      "cloud_called": false,
      "cloud_blocked_reason": "private_or_denied_payload_blocked"
    }
  ]
}
```
