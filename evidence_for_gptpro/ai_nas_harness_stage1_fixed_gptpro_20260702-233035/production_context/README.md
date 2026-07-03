# Digua S100P / OpenClaw AI-NAS Demo

This workspace is the evidence and demo repo for turning an S100P board into an
always-on AI-NAS gateway: OpenClaw provides the NAS-facing experience, Qwen runs
locally on S100P, and an edge-cloud router decides when a request can leave the
device.

## Current Status

Status timestamp: 2026-06-29 21:00 CST.

The three demo expectations are now satisfied on the S100P test machine:

| Demo | Expected behavior | Current result | Evidence |
| --- | --- | --- | --- |
| 1. S100P as resident gateway | S100P keeps the AI gateway online after login/logout and exposes a stable local entry point | `openclaw-gateway.service` and `qwen25-local-openai-gateway.service` are both `active/enabled`; `loginctl` linger is `yes` | OpenClaw `/api/health` on `127.0.0.1:8765`; Qwen `/health` on `127.0.0.1:18080` |
| 2. OpenClaw implements AI-NAS | OpenClaw can drive NAS operations, not just chat | `ok_ai_nas_openclaw_nas_control_gate`, 10/10 checks passed | `/mnt/nas/openclaw/reports/qwen25_ai_nas/openclaw_nas_control_gate_20260629-210023-832862/openclaw_nas_control_gate.json` |
| 3. Edge + cloud routing | Every query first enters local Qwen; private/simple requests stay on S100P; public complex requests can use a controlled cloud endpoint | `ok_ai_nas_edge_cloud_router`; 3/3 classifications came from `qwen_structured_json`; 2 local, 1 cloud; no privacy query was sent to cloud | `/mnt/nas/openclaw/reports/qwen25_ai_nas/edge_cloud_router_20260629-210034-495865/edge_cloud_router.json` |

The latest Qwen AI-NAS acceptance packet also passed:

- Verdict: `ok_qwen25_ai_nas_acceptance_packet`
- Route: `ai_nas_allowlisted_tools`
- Generated reports: personal inventory, evidence report, case packet, folder RAG, and gateway turn reports
- Evidence: `/mnt/nas/openclaw/reports/models/qwen25_ai_nas_acceptance_20260629-210016/qwen25_ai_nas_acceptance.json`

## Demo Story

The project story should be told as a progression from "running a model on a
board" to "shipping a private AI-NAS appliance".

1. The S100P is not a one-off accelerator demo. It is the resident gateway that
   stays online through systemd user services and becomes the local AI control
   plane for a NAS.
2. OpenClaw is the NAS product surface. It turns user intent into real NAS
   workflows: list files, search folders, generate evidence packets, copy/rename
   files, block unauthorized writes, and require confirmation for destructive
   actions.
3. Qwen is the local decision layer. All user queries first enter local Qwen.
   The router asks Qwen whether the request is simple enough to handle locally
   and whether it is privacy-sensitive. Only public, complex work is allowed to
   go to a controlled cloud endpoint.
4. The value proposition is token saving plus privacy protection: the endpoint
   keeps private NAS context on the device and uses cloud only as overflow, not
   as the default path.

Recommended one-line pitch:

> S100P + OpenClaw turns a normal NAS into a privacy-first AI-NAS: local Qwen
> handles private file intelligence on the device, while cloud is used only for
> public complex tasks that pass the local router.

## Highlights

- **Resident gateway**: `qwen25-local-openai-gateway.service` serves the local
  OpenAI-compatible Qwen endpoint at `127.0.0.1:18080`; `openclaw-gateway.service`
  serves the AI-NAS Web OS / operator portal at `127.0.0.1:8765`.
- **Real NAS actions**: the OpenClaw gate validates login, directory listing,
  rename, copy, delete confirmation, viewer read-only behavior, ACL-protected
  copy targets, and direct storage mutation ACL enforcement.
- **Local-first router**: the edge-cloud probe requires Qwen to produce
  structured JSON. Policy is only a privacy/failure fallback.
- **Privacy floor**: invoice, family photo, chat screenshot, NAS folder, finance,
  and other private requests are forced local even if the cloud path exists.
- **Evidence-first delivery**: every demo claim is backed by JSON/Markdown
  reports on `/mnt/nas/openclaw/reports/...`, not by screenshots alone.
- **Model pivot is clear**: Dream7B artifacts are retained as toolchain history;
  the current product route is Qwen + OpenClaw + AI-NAS gates.

## Repository Layout

| Path | Role |
| --- | --- |
| `scripts/qwen25_openai_gateway.py` | Local Qwen OpenAI-compatible gateway and structured edge-cloud classifier entry |
| `scripts/probes/ai_nas_edge_cloud_router_probe.py` | End-to-end local-first edge-cloud router gate |
| `scripts/probes/qwen25_ai_nas_acceptance_packet.py` | Qwen AI-NAS acceptance packet generator |
| `scripts/probes/ai_nas_openclaw_nas_control_gate_probe.py` | OpenClaw NAS control, ACL, and destructive-action gate |
| `scripts/probes/ai_nas_operator_portal_server.py` | AI-NAS Web OS / operator portal server |
| `configs/systemd/qwen25-local-openai-gateway.service` | S100P resident Qwen gateway unit |
| `configs/systemd/openclaw-gateway.service` | S100P resident OpenClaw AI-NAS portal gateway unit |
| `docs/` | Project decisions, runbooks, acceptance notes, and demo scripts |
| `tmp/demo_three_features_final_recheck/` | Local copies of the latest recheck reports |

## Verification Commands

Run these from `F:\Project\Digua` on the Windows host.

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  'systemctl --user is-active openclaw-gateway.service; systemctl --user is-active qwen25-local-openai-gateway.service; curl -fsS http://127.0.0.1:8765/api/health; curl -fsS http://127.0.0.1:18080/health'
```

```powershell
py -3 scripts\probes\qwen25_ai_nas_acceptance_packet.py --out-root tmp\demo_three_features_final_recheck
```

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  'cd /mnt/nas/openclaw/scripts/probes && python3 ai_nas_openclaw_nas_control_gate_probe.py --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas'
```

```powershell
ssh -i C:\Users\zhexu\.ssh\s100p_linkcheck_ed25519 sunrise@192.168.127.10 `
  'cd /mnt/nas/openclaw/scripts/probes && python3 ai_nas_edge_cloud_router_probe.py --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas --use-qwen-classifier --require-qwen-touch --qwen-base-url http://127.0.0.1:18080 --execute-cloud --use-local-cloud-stub --require-cloud-call --timeout 180'
```

## Boundaries

- The router demo uses a controlled local cloud stub unless `--cloud-base-url`
  is explicitly pointed at a real cloud service.
- Qwen `/health` still contains historical model/profile metadata fields that
  can look inconsistent. For acceptance, use the gate verdicts and generated
  report paths above as the source of truth.
- Dream7B is no longer the promoted product path. It remains useful as runtime,
  batching, telemetry, and validation history.
- `F:\Project\Digua\.git` is currently an empty/broken git directory. Local git
  commands fail with `fatal: not a git repository`, so the latest progress has
  not been verified as uploaded from this workspace. Restore the real git
  metadata or provide the remote before committing and pushing.
