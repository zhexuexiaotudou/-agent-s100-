# AI-NAS Hard Failure Triage Runbook

Date: 2026-06-23

## Scope

Use this runbook for failures that require GPT-5.5-class reasoning before a
DeepSeek-class model implements or reruns anything:

- S100P runtime failures
- BPU/common-buffer allocation failures
- Qwen2.5 1024 HBM route
- OCR wrapper and official PP-OCRv3 integration
- service interactions between Qwen gateway, OpenClaw, vision workers, and
  NAS report writers

## Safety Rules

- Start read-only.
- Do not restart services unless the failure mode and rollback are documented.
- Do not delete, move, overwrite, or clean NAS files without explicit approval.
- Do not weaken a gate to make it pass.
- Do not update a gate's expected verdict until current evidence proves the new
  behavior.
- Preserve failed logs and artifacts before retrying.

## Standard Evidence Bundle

For every hard failure, collect:

| Item | Required detail |
| --- | --- |
| Failure ID | Date/time, host, command, service, user |
| Expected behavior | Gate or doc section that defines success |
| Actual behavior | Return code, stderr, logs, health response |
| Affected profile | HBM path, config path, model alias, service name |
| Resource state | memory, BPU/common-buffer, disk, mount, permissions |
| Last known good | Previous passing JSON/Markdown evidence |
| Rollback | Exact service/config/file state to restore |
| Gate impact | Which gate becomes blocked, limited, or still valid |

## S100P Runtime Triage

Read-only commands:

```bash
hostname
date -Is
df -h
free -h
systemctl --user status qwen25-local-openai-gateway.service --no-pager
curl -sS http://127.0.0.1:18080/health
curl -sS http://127.0.0.1:18080/v1/models
```

If runtime fails:

1. Save the exact command and return code.
2. Save service logs before restart:

```bash
journalctl --user -u qwen25-local-openai-gateway.service --no-pager -n 200
```

3. Compare against the latest accepted packet:

```text
tmp/product_guardrail_snapshots/qwen25_ai_nas_acceptance_20260623-114806/qwen25_ai_nas_acceptance.json
```

4. Decide whether this is a service failure, model runtime failure, NAS report
   path failure, or prompt/tool route failure.

Do not restart until the failure class is known. If restart is approved, record
the before/after health and the service unit path.

## Qwen2.5 1024 And Common-Buffer Triage

Known current state:

- official 1024 HBM loads
- prefill/decode init is observed
- runtime completion fails
- return code: `-11`
- failure class: S100P BPU/common-buffer allocation

Evidence:

```text
/mnt/nas/openclaw/reports/models/s100_official_qwen_runtime_20260623-004222/official_qwen_runtime_probe.json
docs/qwen25_ai_nas_text_entry_2026-06-23.md
tmp/ai_nas_ten_goal_s100p_closure/ten_goal_s100p_closure_gate_latest.json
```

Triage sequence:

1. Confirm the active service is still using the 512/128 profile before testing
   1024, so production demo behavior is not disrupted.
2. Run the 1024 probe only in an isolated shell/session.
3. Capture HBM path, config, common-buffer logs, return code, and memory state.
4. If the failure remains allocation-related, keep status as
   `blocked_on_current_s100p_common_buffer_allocation`.
5. Only promote 1024 after a new acceptance packet proves health, model list,
   chat, and AI-NAS evidence flow under the 1024 profile.

Required promotion gate:

```text
ok_qwen25_1024_s100p_acceptance_gate
```

## OCR Wrapper Triage

Known current state:

- Official PP-OCRv3 HBM files are present and model-info evidence exists.
- The vision route still marks production OCR wrapper risk.
- Product closure has temporary wrapper evidence, but a persistent production
  worker must still be treated carefully.

Read-only checks:

```powershell
rg -n "PP-OCR|ocr|wrapper|paddle" docs scripts tmp
```

Remote checks should record:

- HBM det/rec paths
- sample image path
- wrapper command
- raw OCR output
- normalized OCR JSON
- permission scope used for publishing output

Failure classification:

| Failure | Meaning | Next step |
| --- | --- | --- |
| HBM missing | model artifact problem | Do not change AI-NAS code; restore or locate artifact |
| Runtime import missing | environment problem | Document packages/env before installing |
| OCR returns boxes but no text | det/rec pipeline mismatch | Capture intermediate outputs |
| OCR output writes globally | permission bug | Block release and fix report scoping |
| OCR works only on one fixture | coverage gap | Add fixture class before claiming broad OCR |

Promotion gate:

```text
ok_ai_nas_ocr_worker_gate
```

## Service Interaction Triage

Service interaction failures usually appear as "model works alone, but product
flow fails." Split the route:

| Segment | Check |
| --- | --- |
| Gateway health | `curl http://127.0.0.1:18080/health` |
| Model catalog | `curl http://127.0.0.1:18080/v1/models` |
| Single chat turn | Qwen gateway turn JSON under `/mnt/nas/openclaw/reports/qwen25_gateway/` |
| Tool route | AI-NAS report paths under `/mnt/nas/openclaw/reports/qwen25_ai_nas/` |
| Local retention | copied packets under `tmp/product_guardrail_snapshots/` |
| Portal contract | `ai_nas_operator_portal_contract_probe.py` output |
| Ten-goal closure | `ai_nas_ten_goal_s100p_closure_gate.py` output |

If a segment fails, fix only that segment. Do not modify unrelated gate
expectations or fallback to stale evidence.

## Gate Update Rule

A gate may be updated only when all are true:

- The old behavior is obsolete for a product reason documented in `docs/`.
- A new probe proves the replacement behavior.
- The new JSON includes paths, commands, return codes, and failure details.
- The release claim audit is updated if claim wording changes.
- The ten-goal closure or product closure gate is rerun if the change affects
  the product boundary.

## Rollback Boundary

Any change touching these files or services needs a rollback note:

- `configs/systemd/qwen25-local-openai-gateway.service`
- `scripts/qwen25_openai_gateway.py`
- S100P remote copies under `/mnt/nas/openclaw/scripts/`
- model configs under `/mnt/nas/openclaw/configs/`
- portal/server probes under `scripts/probes/`
- report roots under `/mnt/nas/openclaw/reports/`

Rollback can be a config restore, service restart to a prior unit, or restoring
the active profile to `cache_len_512_chunk_128_q8`. It must not delete evidence
directories unless the user explicitly approves cleanup.
