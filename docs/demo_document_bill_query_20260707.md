# Demo Document Bill Query 2026-07-07

## Scope

This note records the third demo path: a user places a household expense bill
document in NAS storage and asks the AI assistant to find the bill amount.

Created NAS demo documents:

- `Documents/DemoDocs/family_expense_bill_20260520_1314.docx`
- `Documents/DemoDocs/family_expense_bill_20260520_1314.md`

Document content:

- Date: `2026-05-20`
- Subject: family expense bill
- Amount: `1314元`

The `.md` copy is the stable text source for the current SQLite FTS path. The
`.docx` copy verifies the same content can also be extracted through the local
DOCX text reader.

## Fixes

The first live attempt exposed three product issues:

1. Chinese PowerShell JSON needed explicit UTF-8 bytes for reliable API tests.
2. Copilot questions containing `文档` plus `多少` could be misrouted to storage
   inventory before document RAG.
3. Document RAG listed evidence refs but did not surface detected amounts in
   the answer.

Implemented changes:

- Document-query intent now takes precedence over storage inventory when the
  query contains document terms plus `查` / `找` / `问` / summary intent.
- Document RAG recall filters SQLite FTS results by requested relative path and
  de-duplicates repeated chunks before returning evidence.
- Document answers extract money-like amounts from evidence snippets and show
  them in the assistant response.

Follow-up after browser testing:

- Natural bill queries without the word `文档`, such as
  `2026年5月20日家庭开支账单信息`, are also routed to document RAG.
- Chinese document queries are expanded with date, bill, household expense, and
  amount keywords so a nearby natural phrase can still retrieve the bill.

## S100P Acceptance

Environment:

- Host: `sunrise@192.168.127.10`
- Portal: `http://127.0.0.1:8765`
- Personal root: `/mnt/nas/openclaw/Personal`
- Query route: `POST /api/copilot/chat`

Prompt:

```text
请查询文档：2026年5月20日家庭开支账单金额是多少？
```

Result:

```text
route=local_document_query
assistant_mode=local_document_query
local_tool_id=local_document_rag
evidence_count=2
amount_hits=1314元,1314CNY
cloud_used=false
raw_path_returned=false
```

Assistant answer included:

```text
命中金额：1314元
```

Browser acceptance prompt:

```text
2026年5月20日家庭开支账单信息
```

Browser result:

```text
badge=本地文档返回
evidence_count=2
answer_contains=合计金额：1314元
cloud_used=false
generic_bank_refusal=false
```

Regression tests passed locally and on S100P:

```text
python3 -m unittest -v tests.test_document_fts_rag tests.test_copilot_local_qwen_chat
Ran 12 tests OK
```

## Boundary

This closes the small demo path for text-extractable documents. Scanned image
PDFs still depend on the OCR bridge and should be demonstrated through the
existing OCR/RAG path, not this plain-text FTS path.

## Follow-up: Grounded Qwen Answer and Openable Evidence

User acceptance exposed two remaining product gaps in the assistant document
result card:

- Evidence cards were displayed as static references and could not be opened
  from the assistant answer.
- The assistant answer was assembled by the portal from recalled snippets,
  instead of asking local Qwen to answer from the recalled document content.

Implemented path:

1. SQLite FTS still performs the local document recall and ACL-scoped evidence
   selection.
2. Each evidence item now carries a controlled `open_url` for
   `/api/storage/download?preview=1`; the browser fetches it with the saved
   identity token, so raw NAS absolute paths are not exposed.
3. The copilot document branch sends the recalled redacted snippets to local
   Qwen with `disable_ai_nas_tools=true` and
   `qwen_execution_authority=false`.
4. Qwen returns the final user-facing answer. For money questions, the first
   Qwen answer prompt uses compressed evidence facts containing the detected
   amount instead of long document chunks. If Qwen is unavailable, or if a
   money-question answer fails to mention the detected evidence amount exactly,
   the portal retries the same evidence-fact prompt up to three more times. If
   that also fails, the deterministic evidence answer remains a direct bill
   conclusion rather than a long evidence dump. Ungrounded greetings, generic
   answers, approximate amounts, CNY-only answers, and follow-up clarification
   language are not shown to the user. When Qwen says `1314人民币`, the portal
   normalizes the display back to the source document unit `1314元`. If Qwen
   uses an odd but amount-matching phrase, the final display is normalized to a
   direct bill answer.

Local regression:

```text
py -3 -m py_compile scripts/probes/ai_nas_operator_portal_server.py
node --check web/static/digua_ai_nas_v2.js
py -3 -m unittest -v tests.test_document_fts_rag tests.test_copilot_local_qwen_chat
Ran 20 tests OK
```

Follow-up hardening:

- Amount-sensitive document prompts now include a short target answer sentence
  extracted from the local evidence facts and instruct Qwen to return that
  sentence exactly. This keeps Qwen in the grounded document-answer path while
  reducing unstable generic or approximate local-model output.
