# Dream 7B OpenClaw Gateway Candidate

## Status

OpenClaw is temporarily pointed at a local Dream 7B candidate provider:

```text
dream7b-local/Dream7B-S100P-local
```

The original MiniMax provider is still present as a fallback. The previous
OpenClaw config was backed up on S100P at:

```text
/root/.openclaw/openclaw.json.before-dream7b-local-candidate-20260611-134402
```

## Candidate Provider

The candidate provider is a loopback OpenAI-compatible HTTP service:

```text
http://127.0.0.1:18888/v1
```

Installed script on S100P:

```text
/root/.openclaw/workspace/scripts/dream7b_local_openai_gateway.py
```

Repo source:

```text
scripts/dream7b_local_openai_gateway.py
```

The service exposes:

- `/health`
- `/v1/models`
- `/v1/chat/completions`

Normal text calls delegate to:

```text
dream7b-text
```

## Verification Evidence

Direct provider checks passed:

- `/health` returned `{"ok": true, "model": "Dream7B-S100P-local"}`.
- Direct chat returned: `Dream 7B runs locally on S100P`.
- Direct OpenAI-style tool-call response can emit `s100p_run_probe` with `{"tool_id":"personal_data_sort_probe"}`.

OpenClaw model discovery passed:

```text
openclaw models list
```

reported:

```text
dream7b-local/Dream7B-S100P-local
available=true
default
```

OpenClaw agent metadata also showed:

```text
provider=dream7b-local
model=Dream7B-S100P-local
```

## Tool Execution Result

The OpenClaw custom `openai-completions` adapter did not execute the candidate's
native OpenAI `tool_calls` response in the tested CLI path. The candidate
therefore uses a fixed, local, allowlisted fallback for the teacher demo. The
recommended recording path now uses the dry-run entry first:

```text
bash /root/.openclaw/workspace/scripts/run_allowlisted_tool.sh \
  personal_data_sort_dry_run_probe \
  Personal \
  Movies \
  Sorted \
  /mnt/nas/openclaw/reports/personal-data-sort-dry-run
```

This creates a preview plan and report only. It does not upload sorted copies
and does not change `Personal/Sorted`.

The older apply/copy entry remains available for explicit operator-approved
runs:

```text
bash /root/.openclaw/workspace/scripts/run_allowlisted_tool.sh \
  personal_data_sort_probe \
  Personal \
  Movies \
  Sorted \
  /mnt/nas/openclaw/reports/personal-data-sort
```

Both entries go through the same safe allowlisted runner and fixed NAS scope.
It does not accept arbitrary commands, arbitrary shares, or arbitrary output
paths from the model.

Verified dry-run result:

```text
/mnt/nas/openclaw/reports/personal-data-sort-dry-run/personal_data_sort_20260611-232515/personal_data_sort.md
```

Key fields:

```text
file_count: 20
copy_count: 20
dry_run: True
upload_performed: False
delete_or_move_performed: False
overwrite_source_performed: False
```

The earlier apply/copy verification generated `Personal/Sorted/Movies/` with
genre folders, then the sorted demo output was cleared again so the recording
can show the preview workflow cleanly.

## Recording Guidance

For the recording, refresh the OpenClaw UI and check the model selector. It
should show the Dream 7B local candidate rather than MiniMax.

Then ask:

```text
请整理 Personal/Movies 里的电影文件，保留原文件，复制分类到 Sorted。
```

Expected visible result:

```text
Personal -> Sorted -> Movies
```

with genre folders such as `Action`, `Animation`, `Sci-Fi`, `Drama`, and
`Documentary`.

## Important Caveat

This candidate proves that OpenClaw can be temporarily routed through local
Dream 7B and still trigger the safe Personal/Movies sorting workflow. It does
not yet prove that Dream 7B can replace MiniMax as a general OpenClaw tool-call
reasoning model, because the native OpenAI `tool_calls` response was not
executed by the tested OpenClaw custom-provider adapter.

For a rigorous final claim, phrase it as:

```text
Dream 7B has been connected as a local OpenClaw candidate and can drive the
Personal/Movies sorting demo through a fixed allowlisted runner. MiniMax remains
the mature fallback for general tool orchestration.
```
