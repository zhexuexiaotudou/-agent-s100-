# AI-NAS Non-Long Task Completion 2026-06-23

Date: 2026-06-23

## Scope

This note closes the current "do everything except long-running tests" pass.
It covers mechanical tasks that can be implemented and verified quickly without
long soak, large-scale endurance, destructive NAS operations, service restarts,
or unresolved hardware-runtime triage.

## Completed Non-Long Tasks

| Task | Status | Evidence |
| --- | --- | --- |
| D2 Web NAS OS UI improvement | Completed | `scripts/probes/nas_web_os_portal.html` now has tables, filters, loading states, and basic buttons for module pages. |
| D3 Existing-module pages | Completed | Web OS now exposes file, document, backup, snapshot/trash, media, user, ops, app ecosystem, copilot, and audit sections backed by real APIs. |
| D4 Small deterministic fixture expansion | Completed | `scripts/probes/ai_nas_web_os_gate_probe.py` adds small document, photo, video, and OCR-text fixtures under the temporary gate root. |
| D5 Documentation sync | Completed | This file and `docs/ai_nas_next_tasks_model_split_2026-06-23.md` describe current completion and the long-test boundary. |
| D6 Remote evidence collection | Completed for the available non-long route | Full closure refreshed the Qwen2.5 S100P acceptance packet locally; direct SSH read-only capture was attempted but unavailable under BatchMode authentication. |
| D7 Mechanical adapter stubs | Completed | `/api/apps/add-protocol` creates truthful adapter records with `implementation_state=adapter_record_only` and `protocol_daemon_started=false`. |

## Code Changes

- `scripts/probes/ai_nas_operator_portal_server.py`
  - Added non-destructive module APIs:
    - `/api/backup/summary`
    - `/api/media/summary`
    - `/api/ops/summary`
    - `/api/apps/summary`
    - `/api/audit/summary`
  - Added bounded POST endpoints for existing stores:
    - backup task create/run/delete
    - media index and album create
    - ops health check, alert create, alert resolve
    - plugin register, plugin status, protocol adapter record
  - Added optional DB path arguments for backup, media, ops, and app stores.

- `scripts/probes/nas_web_os_portal.html`
  - Replaced placeholder module text with data-backed tables.
  - Added filters for files, documents, users, and media.
  - Added refresh/create/run buttons for existing non-destructive or explicitly
    requested actions.
  - Shows adapter records as records only; it does not claim protocol daemons
    are implemented.

- `scripts/probes/ai_nas_web_os_gate_probe.py`
  - Expanded the short Web OS gate from 19 checks to 34 checks.
  - Verifies new module APIs and adapter truthfulness.
  - Adds only local deterministic fixtures under the temporary gate root.

## Verified

Short verification completed:

```text
python -m py_compile scripts/probes/ai_nas_operator_portal_server.py scripts/probes/ai_nas_web_os_gate_probe.py
```

Using the bundled Codex runtime Python:

```text
C:\Users\zhexu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
```

Short Web OS gate:

```text
scripts/probes/ai_nas_web_os_gate_probe.py --report-root tmp\nas_web_os_gate_local
```

Result:

```text
ok_nas_web_os_gate
Passed: 34/34
```

Latest local evidence:

```text
tmp/nas_web_os_gate_local/web_os_gate_latest.json
tmp/nas_web_os_gate_local/web_os_gate_latest.md
```

Full ten-goal closure was also refreshed after the non-long edits:

```text
tmp/ai_nas_ten_goal_s100p_closure/ten_goal_s100p_closure_gate_latest.json
```

Result:

```text
ok_ai_nas_ten_goal_s100p_closure_gate
goals_ok: 10/10
s100p_model_ok: true
```

Latest Qwen2.5 S100P acceptance packet from that refresh:

```text
tmp/product_guardrail_snapshots/qwen25_ai_nas_acceptance_20260623-121706/qwen25_ai_nas_acceptance.json
```

Read-only SSH health capture was attempted with a short timeout:

```text
ssh -o BatchMode=yes -o ConnectTimeout=8 sunrise@192.168.127.10 "hostname; date -Is; curl -sS --max-time 5 http://127.0.0.1:18080/health; curl -sS --max-time 5 http://127.0.0.1:18080/v1/models"
```

Result:

```text
Permission denied (publickey,password).
```

No service restart, delete, move, overwrite, or systemd change was performed.

## Long Or Excluded Work

These remain outside this pass because they require long-running tests,
external-state changes, hardware-runtime triage, service restarts, or broader
product gates:

- long soak and soak watcher completion;
- full endurance or scale testing beyond the small deterministic fixtures;
- production 1024-profile promotion while
  `blocked_on_current_s100p_common_buffer_allocation` remains true;
- production CLIP/person/photo semantics gates;
- production OCR worker promotion beyond the current bounded route evidence;
- destructive file cleanup, real NAS migration, or service restarts without
  explicit approval;
- claiming full commercial/top-tier NAS replacement.

## Next Safe DeepSeek Step

If switching to DeepSeek, start with:

```powershell
$py='C:\Users\zhexu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py scripts\probes\ai_nas_web_os_gate_probe.py --report-root tmp\nas_web_os_gate_local
```

Then inspect `tmp/nas_web_os_gate_local/web_os_gate_latest.json`. Do not weaken
the gate if it fails.
