# Stage4 Write Action Risk Register

| Risk | Boundary |
| --- | --- |
| Real NAS data loss | Real NAS writes are rejected by this packet. |
| Approval spoofing | Token requires HMAC signature, expiry, nonce, target hash, before hash, rollback hash, and exact human confirmation. |
| Destructive action creep | Delete remains blocked for first canary and requires a separate destructive-action gate. |
| Qwen tool authority drift | Qwen remains a router/advisor only and never directly executes tools. |
| Cloud/private leakage | Private raw context cannot leave local policy path; adversarial suite keeps cloud calls at zero. |
