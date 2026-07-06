# Demo 1 Recording Script: S100P Link Readiness

## Goal

Show that the PC can reach the S100P, S100P resident services are active, the NAS Personal root is readable, and the OpenClaw product API is reachable without exposing raw storage paths.

## Commands

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 'hostname; whoami; ip route | head -5'
```

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 'systemctl --user is-active openclaw-gateway.service; systemctl --user is-active qwen25-local-openai-gateway.service'
```

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 'curl -fsS http://127.0.0.1:8765/api/health; curl -fsS http://127.0.0.1:8765/api/product/status; curl -fsS http://127.0.0.1:8765/api/harness/status'
```

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 'test -r /mnt/nas/openclaw/Personal && echo NAS_PERSONAL_READABLE'
```

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 'cd /mnt/nas/openclaw && python3 gates/stage8_demo1_link_readiness_gate.py --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas --personal-root /mnt/nas/openclaw/Personal --base-url http://127.0.0.1:8765 --qwen-url http://127.0.0.1:18080/health --timeout 45'
```

## Expected Output

- `openclaw-gateway.service`: `active`
- `qwen25-local-openai-gateway.service`: `active`
- `/api/health`: `ok=true`
- `/api/product/status`: `ok=true`
- `/api/harness/status`: `qwen_execution_authority=false`
- Gate verdict: `ok_stage8_demo1_link_readiness_gate`

## Subtitle

S100P is the resident AI-NAS gateway. The PC is only the operator workstation; OpenClaw and local Qwen stay active on loopback-scoped S100P services.

## Do Not Say

- Do not say the gateway is exposed to the public internet.
- Do not say S100P replaces every PC function.
- Do not show raw NAS paths in product API responses.
