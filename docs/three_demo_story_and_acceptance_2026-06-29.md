# Three-Demo Story and Acceptance, 2026-06-29

This note summarizes the current demo story, highlight claims, and acceptance
evidence for the S100P + OpenClaw AI-NAS project.

## Executive Conclusion

All three requested demo functions are implemented and passed live S100P
acceptance on 2026-06-29 around 21:00 CST.

| Function | Acceptance result | Latest evidence |
| --- | --- | --- |
| S100P as resident gateway | `openclaw-gateway.service` and `qwen25-local-openai-gateway.service` are `active/enabled`; linger is enabled | S100P health check: OpenClaw `127.0.0.1:8765/api/health`, Qwen `127.0.0.1:18080/health` |
| S100P OpenClaw as AI-NAS | `ok_ai_nas_openclaw_nas_control_gate`, 10/10 checks passed | `/mnt/nas/openclaw/reports/qwen25_ai_nas/openclaw_nas_control_gate_20260629-210023-832862/openclaw_nas_control_gate.json` |
| Edge + cloud privacy/token router | `ok_ai_nas_edge_cloud_router`; all three classifications came from Qwen structured JSON; private queries stayed local; public complex query called a controlled cloud endpoint | `/mnt/nas/openclaw/reports/qwen25_ai_nas/edge_cloud_router_20260629-210034-495865/edge_cloud_router.json` |

The Qwen AI-NAS acceptance packet also passed:

- `ok_qwen25_ai_nas_acceptance_packet`
- `/mnt/nas/openclaw/reports/models/qwen25_ai_nas_acceptance_20260629-210016/qwen25_ai_nas_acceptance.json`

## Story Arc

### Scene 1: S100P Becomes the Resident Gateway

Start with the device rather than the model. The point is that S100P is not a
benchmark board sitting next to a NAS; it is the always-on local AI control
plane.

Visual idea:

- show the S100P/NAS setup;
- show `systemctl --user is-active` for OpenClaw and Qwen;
- show OpenClaw Web OS loading from `127.0.0.1:8765`;
- show Qwen health from `127.0.0.1:18080`.

Message:

> The board is now a resident gateway: it runs the local model endpoint and the
> AI-NAS product surface as managed services.

### Scene 2: OpenClaw Turns NAS Into AI-NAS

The second scene should prove that this is not only chat. The OpenClaw AI-NAS
surface can map intent to NAS operations while respecting permissions.

Validated behaviors:

- admin login;
- directory listing;
- rename;
- copy;
- destructive delete confirmation;
- viewer read-only path;
- ACL enforcement on copy target;
- direct storage mutation ACL enforcement.

Message:

> OpenClaw is the NAS operator interface. It converts natural-language intent
> into bounded NAS actions with permission checks and audit evidence.

### Scene 3: Local Qwen Routes Every Query Before Cloud

The third scene is the privacy and token-saving story. Every request first
enters local Qwen. Qwen returns structured JSON that decides:

- whether the task is simple enough to handle locally;
- whether the query contains private NAS content;
- whether cloud is allowed.

Latest router result:

- classifier count: `qwen_structured_json = 3`;
- route count: `local = 2`, `cloud = 1`;
- privacy count: `high = 2`, `none = 1`;
- cloud call count: `1`;
- controlled cloud call count: `1`;
- privacy query sent to cloud: `false`.

Message:

> Cloud is an overflow path, not the default path. Private NAS intelligence
> stays on the S100P; public complex work can be delegated after local Qwen
> approves it.

## Recommended Pitch

S100P + OpenClaw turns a normal NAS into a privacy-first AI-NAS. Local Qwen
handles private file intelligence on the device, OpenClaw exposes real NAS
actions with ACL and confirmation gates, and cloud is used only for public
complex tasks after local routing.

## Differentiated Highlights

1. **Local-first by architecture**: all queries hit S100P/Qwen before any cloud
   path exists.
2. **Privacy floor**: policy can override only to keep private requests local;
   it cannot force private data to cloud.
3. **Actionable NAS workflow**: the demo includes file operations and ACL checks,
   not only text generation.
4. **Evidence-based delivery**: every claim maps to JSON/Markdown reports under
   `/mnt/nas/openclaw/reports/...`.
5. **Clear model pivot**: Dream7B work produced reusable runtime and validation
   tooling, but the live product route is now Qwen + OpenClaw.

## Demo Boundaries

- The cloud endpoint in the latest router test is a controlled local stub unless
  a real `--cloud-base-url` is supplied.
- Qwen health metadata still includes historical model/profile fields; for demo
  claims, cite acceptance reports and gate verdicts.
- The local Windows directory has a broken empty `.git` directory, so upload
  status cannot be verified from this checkout until the real git metadata or
  remote is restored.
