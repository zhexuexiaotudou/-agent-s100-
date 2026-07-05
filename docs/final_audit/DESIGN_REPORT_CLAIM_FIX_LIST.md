# Design Report Claim Fix List

- Use these replacements before GPT Pro or formal submission.

| claim | problem | recommended wording | avoid |
| --- | --- | --- | --- |
| Mobile browser basic access | partially_supported | Mobile responsive core pages have prior screenshot evidence; this audit did not rerun fresh mobile Playwright. | All mobile production workflows are fully accepted. |
| NAS SQLite metadata index | partially_supported | SQLite metadata/index flow exists; current UI packet noted inventory degraded. | SQLite inventory is always healthy in every environment. |
| embedding optional | should_reword | Embedding is optional/feature-flagged, not default production semantic search. | Production-grade embedding RAG is on by default. |
| Document RAG / Q&A | partially_supported | FTS-first document Q&A/eval is supported. | Complete embedding RAG with reranker is default. |
| UI v2 mobile core flows | partially_supported | Two mobile screenshot flows exist; not six fresh mobile flows this audit. | Mobile production full flow acceptance is complete. |
| Multimodal NAS index | partially_supported | Metadata index for documents/images/video/audio/code/archive is live. | OCR/thumbnail/embedding/transcript extraction is default enabled. |
| OpenTelemetry-like trace | should_reword | Local OpenTelemetry-like trace schema exists. | A full OpenTelemetry collector/backend is deployed. |
| Dream7B research branch | research_only | Dream7B has research truth-set evidence but remains blocked at BPU operator alignment. | Dream7B is current product front-end model. |
