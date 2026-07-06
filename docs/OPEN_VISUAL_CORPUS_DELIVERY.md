# Open Visual Corpus Delivery

Stage 10 adds `demo_corpus/` as the reproducible recording corpus workflow.

## Delivered

- Recipes for image classes, synthetic documents, video keyframes, audio
  transcripts, expected categories, and golden queries.
- Wikimedia Commons downloader with Commons API license/author/source capture.
- Open Images seed-manifest downloader to avoid unbounded upstream CSV pulls in
  release gates.
- Synthetic Chinese invoice, contract, course-note, screenshot-note, video
  keyframe, and transcript generators.
- Manifest merger, attribution generator, and corpus verifier.

## Boundary

Third-party media is not committed and is not bundled in release packages by
default. `demo_corpus/downloaded/` is ignored. CI fallback images are marked
`fixture_only_for_ci=true` and cannot be used as proof of real YOLO detections.

