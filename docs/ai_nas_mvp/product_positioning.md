# Product Positioning

## Positioning Statement

低成本 AI-NAS Copilot is the local AI intelligence layer for a cheap NAS. It lets an existing NAS keep doing storage work while S100P and OpenClaw provide the high-end intelligent layer: file understanding, semantic-ish search, summaries, duplicate reports, safe organization suggestions, and auditable tool calls.

## What We Replace

We replace only the high-end NAS intelligent layer:

- Natural-language file finding.
- Document OCR/extraction, summary, and folder Q&A, with explicit failure logs when extraction is not available.
- Movie organization suggestions and non-destructive copy sorting.
- Photo metadata/category indexing, bounded photo semantic search, and a path toward production CLIP-style image retrieval.
- Duplicate/similar-file reports.
- Human-reviewed cleanup suggestions.
- Natural-language operation through OpenClaw with fixed allowlisted tools.

## What We Do Not Replace

The NAS vendor still owns:

- RAID, snapshots, backup, sync, permissions, SMB/NFS/WebDAV, mobile apps, NVR, and storage health.
- Vendor account, app store, remote access, and disk-management UX.
- Final destructive cleanup actions.

## Why S100P + OpenClaw Matters

S100P is the local inference and control host. It keeps the intelligence layer near the NAS data without requiring a high-end NAS CPU/NPU. OpenClaw is the natural-language operator, but it is constrained by an allowlist and produces reports and manifests for every operation.

The practical split is:

- Cheap NAS: durable bytes and vendor storage features.
- S100P: local model/runtime, scans, summaries, and controlled file intelligence jobs.
- OpenClaw: conversational entry, tool routing, audit logs, and human-visible reports.

## P0/P1/P2/P3 Boundary

P0:

- Scan `Personal/Movies`, `Personal/Documents`, `Personal/Photos`, and `Personal/Inbox`.
- Build file inventory with path, size, mtime, SHA256, type, extension, tags, keywords, summaries, and parse failures.
- Natural-language file search over metadata and extracted text previews.
- Folder summary and deterministic Q&A for demo text documents.
- Movie report and copy-only organization into `Personal/Sorted/Movies`.
- SHA256 duplicate report, no delete.
- OpenClaw allowlisted trigger path.

P1:

- OCR for scanned PDFs/images.
- Embedding search for documents and photos.
- pHash/similar image grouping.
- Better movie metadata enrichment through local rules or reviewed metadata files.

P2:

- Incremental indexing with change detection.
- Vector database or SQLite FTS index.
- Role-based review workflow for cleanup actions.
- Better OpenClaw dialogue templates and task status cards.

P3:

- Mobile companion UI.
- Multi-user permission-aware search.
- Full photo album UX and background services.
- Integration with vendor NAS app APIs where available.

## Demo Claim Discipline

Current claim:

> We have a reproducible local AI-NAS MVP that demonstrates the intelligent layer: file inventory, natural-language search, folder summary/Q&A, movie copy organization, and duplicate reporting, all through safe report-first tools.

Do not claim:

- Mature commercial NAS replacement.
- Full OCR quality parity.
- Full Synology/QNAP/UGREEN UX parity.
- Automatic safe deletion.
- Universal semantic understanding before embeddings/OCR are connected.
