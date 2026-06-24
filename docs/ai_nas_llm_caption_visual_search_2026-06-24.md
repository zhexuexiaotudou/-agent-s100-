# AI-NAS LLM Caption Visual Search

Date: 2026-06-24

## Decision

The visual search path should be caption-first.

Whole-image color histograms, filename labels, and local visual embeddings are
not sufficient for queries such as:

```text
find photos of people wearing white tops
```

The production path is:

1. A large vision model generates a structured caption for each photo.
2. AI-NAS stores the caption, objects, generic people, upper-clothing color,
   visible text, model identity, and privacy flags in SQLite.
3. Search uses caption/attribute evidence first.
4. Local visual embeddings remain fallback/plumbing evidence, not the source of
   clothing/person semantics.

## Runtime Configuration

The caption worker uses an OpenAI-compatible chat-completions endpoint with
image input.

Required environment:

```powershell
$env:AI_NAS_VISION_CAPTION_ENDPOINT = "http://127.0.0.1:18080/v1/chat/completions"
$env:AI_NAS_VISION_CAPTION_MODEL = "<vision-caption-model-id>"
```

Optional environment:

```powershell
$env:AI_NAS_VISION_CAPTION_API_KEY = "<provider key if required>"
$env:AI_NAS_VISION_CAPTION_TIMEOUT_SECONDS = "120"
```

If `AI_NAS_VISION_CAPTION_ENDPOINT` is not set, the code can derive the endpoint
from `AI_NAS_VISION_CAPTION_BASE_URL` or `OPENAI_BASE_URL`. If only
`OPENAI_API_KEY` is present, it uses `https://api.openai.com/v1/chat/completions`.
The model id is intentionally explicit; do not hard-code a stale default.

## Code Changes

- `scripts/probes/ai_nas_common.py`
  - adds `image_captions` SQLite table;
  - adds `run_image_caption_for_record`;
  - adds `ensure_image_captions_for_photos`;
  - adds `image_caption_summary`;
  - makes clothing/color queries require caption evidence.
- `scripts/probes/ai_nas_operator_portal_server.py`
  - runs caption indexing from `/api/vision/index`;
  - includes caption runtime status and search-result caption evidence;
  - removes visual-search hidden-result counts from user-facing responses.
- `scripts/probes/nas_web_os_portal.html`
  - shows caption provider readiness;
  - displays caption/evidence in visual search results.
- `scripts/probes/ai_nas_llm_caption_visual_search_gate_probe.py`
  - verifies white-top search using injected large-model-style captions.

## Acceptance Evidence

Local regression run:

```text
ok_ai_nas_llm_caption_visual_search_gate
```

Report:

```text
tmp\ai_nas_llm_caption_visual_search_gate_local\llm_caption_visual_search_gate_20260624-144915-244471\llm_caption_visual_search_gate.json
```

The gate checks:

- Chinese query: `穿白色上衣的照片`
- English query: `photos of people wearing white tops`
- positive fixture: generic person wearing a white top
- negative fixtures: white car, white wall, white document screenshot, blue top
- no face recognition or identity matching

## Product Boundary

Allowed claim after this change:

> AI-NAS now has a caption-first visual-search contract and a verified local
> gate showing that white-top queries are separated from whole-image white
> distractors.

Not allowed until a real caption provider is configured and production gates
pass:

> All real photos are production-captioned, all clothing/person semantics are
> production reliable, or person identity recognition is supported.
