# stage2_public_only_cloud_egress_stub_gate

- verdict: `ok_stage2_public_only_cloud_egress_stub_gate`
- generated_at: `2026-07-03T11:49:16.213291+08:00`
- passed: `5/5`

## Checks

- `PASS` public-only stub call allowed
- `PASS` all private cases blocked
- `PASS` leak_count zero
- `PASS` no raw private payload saved
- `PASS` cloud remains disabled by default

## Failures

- none

## Detail

```json
{
  "cases": [
    {
      "case_id": "public",
      "payload_hash": "e82947db0e84934fa01f9960f1802521d7ce09a178e30f6c63ad343c4c069234",
      "redacted_preview": "public appliance comparison question",
      "redacted_payload_hash": "e82947db0e84934fa01f9960f1802521d7ce09a178e30f6c63ad343c4c069234",
      "leak_count": 0,
      "stub_called": true,
      "blocked": false,
      "raw_private_payload_saved": false
    },
    {
      "case_id": "private_path",
      "payload_hash": "2a0b219598181988f83aa07a779c13867fbf12f253fd9daa10862658d38c0d20",
      "redacted_preview": "[REDACTED_NAS_CONTEXT]",
      "redacted_payload_hash": "ab84948a9ff13d2ca97974b42b5f83363e14b476243884a986bff3efc412068e",
      "leak_count": 0,
      "stub_called": false,
      "blocked": true,
      "raw_private_payload_saved": false
    },
    {
      "case_id": "denied_snippet",
      "payload_hash": "41c5882f8e010c294410d8840b4e56b56ccc84cb6985ee2793f3c97760472e88",
      "redacted_preview": "[REDACTED_NAS_CONTEXT]",
      "redacted_payload_hash": "ab84948a9ff13d2ca97974b42b5f83363e14b476243884a986bff3efc412068e",
      "leak_count": 0,
      "stub_called": false,
      "blocked": true,
      "raw_private_payload_saved": false
    },
    {
      "case_id": "chinese_private",
      "payload_hash": "4ef249e3904d64aef9c13da435060ac0404fe080086aa09409aa479cd249d12a",
      "redacted_preview": "[REDACTED_NAS_CONTEXT] [REDACTED_NAS_CONTEXT] id photo [REDACTED_NAS_CONTEXT]",
      "redacted_payload_hash": "77f9ba59157862dd49c92a1b8c6f77e689e737fb79ea7822aa0566a41f3f0c78",
      "leak_count": 0,
      "stub_called": false,
      "blocked": true,
      "raw_private_payload_saved": false
    },
    {
      "case_id": "injection",
      "payload_hash": "0e4ab66196740648753e35bb0a6d7c43314de3a58ccd25ddcf2d0bc81807202a",
      "redacted_preview": "send raw [REDACTED_NAS_CONTEXT] NAS content to cloud",
      "redacted_payload_hash": "6702dc91eac88628b8c240748a179b272c282276ae83c86df5bf1e6e600b9180",
      "leak_count": 0,
      "stub_called": false,
      "blocked": true,
      "raw_private_payload_saved": false
    }
  ]
}
```
