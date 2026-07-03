# stage2_rollback_gate

- verdict: `ok_stage2_rollback_gate`
- generated_at: `2026-07-03T01:33:40.466018+08:00`
- passed: `5/5`

## Checks

- `PASS` bash available for stop command
- `PASS` stop command returns zero
- `PASS` dispatcher hash recorded
- `PASS` protected ports listed unchanged
- `PASS` stage1 baseline gates still pass

## Failures

- none

## Detail

```json
{
  "asset_hashes": {
    "dispatcher": "e62f2278e1264519ee4e4cd13df44bd34d4375a989715cce3b6223f44c1c21e2",
    "qwen_gateway": "3c75b901126e8783f0e3e36803b902eb1bef09507c7d4a27931834ba6577081f",
    "openclaw_service": "efc108f1b8df688edb9a4aa31677e5519bec34e36d6b9878a922de1e80d48ed6",
    "qwen_service": "16c71a0a8b41f46072f74163e8cf1d01a25a89dcb355186d7139f75f1f2aac9f",
    "qwen_policy": "2e6da77dbb462e7ad930ceabef2f96ca03ff27bc35a651ab997b8819abcb50f7",
    "dream7b_service": "833a44e1b5a19addf7f20dcc927f0d20099542cac348820fdddf4f67bb5d5209",
    "dream7b_18889_service": "13f993a457889a399e136d3bc4d83b76d3fa3150bca9ab6c00a143d6f759fb2a"
  }
}
```
