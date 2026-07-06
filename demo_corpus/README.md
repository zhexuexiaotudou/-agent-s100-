# Digua Demo Corpus

This directory defines the reproducible media corpus used by the Stage 10
release gates. It contains recipes, downloaders, generated-document builders,
manifests, and license notices. Third-party media files are never committed to
the repo; `downloaded/` is ignored and release packages include manifest files
and download scripts by default.

## Workflow

```bash
python3 demo_corpus/scripts/generate_synthetic_docs.py \
  --recipe demo_corpus/recipes/target_classes.yaml \
  --output-dir demo_corpus/samples_generated \
  --manifest-out demo_corpus/manifests/synthetic_docs_manifest.jsonl

python3 demo_corpus/scripts/download_wikimedia_subset.py \
  --recipe demo_corpus/recipes/target_classes.yaml \
  --output-dir demo_corpus/downloaded/wikimedia \
  --manifest-out demo_corpus/manifests/wikimedia_manifest.jsonl \
  --max-per-class 4

python3 demo_corpus/scripts/build_demo_corpus.py \
  --personal-root /mnt/nas/openclaw/Personal \
  --report-root /mnt/nas/openclaw/reports/qwen25_ai_nas \
  --write-to-personal

python3 demo_corpus/scripts/verify_demo_corpus.py \
  --manifest demo_corpus/manifests/demo_corpus_manifest.jsonl
```

## Release Boundary

- Third-party images stay under `demo_corpus/downloaded/` and are ignored by
  git.
- Third-party manifests must include source URL, source ID, license, author,
  attribution, SHA256, and whether redistribution is allowed.
- Project-owned synthetic documents can be regenerated and may be copied into
  a Personal demo root for OCR/RAG validation.
- CI fallback images are marked `fixture_only_for_ci=true` and must not be used
  as proof that real photos produced YOLO boxes.

