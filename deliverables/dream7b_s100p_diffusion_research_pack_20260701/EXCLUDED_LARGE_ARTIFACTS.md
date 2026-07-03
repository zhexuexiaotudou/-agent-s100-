# Excluded Large Artifacts

The following large binary artifact was intentionally excluded from the zip package:

- `F:\Project\Digua\tmp\cloud_seq128_results\dream7b_seq128_b1_lmheadq16_lasttoken_hbm_20260623.tar`
- Size: 8,567,367,680 bytes
- Expected SHA256: `c0e7d6c31af17871cf550ceec88c1bf1ec8de33f30f4d75a9f7b31aa1b73e1b1`

The package includes the artifact metadata instead:

- `05_artifact_metadata/dream7b_seq128_b1_lmheadq16_lasttoken_hbm_20260623.tar.sha256`
- `05_artifact_metadata/seq128_b1_lmheadq16_lasttoken_hbm_manifest.tsv`
- `05_artifact_metadata/seq128_b1_lmheadq16_lasttoken_summary.json`

Reason for exclusion:

The tar is an 8 GB deployment artifact and is not useful for direct GPT Pro text review. The review package focuses on provenance, hashes, manifests, board runtime reports, logits comparison reports, prior negative controls, and scripts.

