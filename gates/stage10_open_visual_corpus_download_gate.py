from __future__ import annotations

import argparse

from PIL import Image

from ai_space_gate_common import check, write_gate
from stage10_common import add_stage10_args, all_manifest_records, gate_payload


NAME = "stage10_open_visual_corpus_download_gate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate demo corpus downloaded/generated assets referenced by manifest.")
    add_stage10_args(parser)
    parser.add_argument("--min-records", type=int, default=20)
    args = parser.parse_args()
    records = all_manifest_records(args.corpus_root)
    failures = []
    existing = 0
    for record in records:
        local_rel = str(record.get("local_rel") or "")
        path = args.corpus_root / local_rel
        manifest_only = record.get("release_package_includes_manifest_only") is True
        if path.exists():
            existing += 1
            if record.get("modality") == "image":
                try:
                    Image.open(path).verify()
                except Exception as exc:
                    failures.append(f"{record.get('asset_id')}:image_unreadable:{type(exc).__name__}")
        elif not manifest_only:
            failures.append(f"{record.get('asset_id')}:local_file_missing:{local_rel}")
        if not record.get("sha256"):
            failures.append(f"{record.get('asset_id')}:sha256_missing")
    modalities = {name: sum(1 for r in records if r.get("modality") == name) for name in ["image", "document", "video", "audio"]}
    checks = [
        check("manifest total meets minimum", len(records) >= args.min_records, len(records)),
        check("some local generated files exist", existing > 0, existing),
        check("documents generated", modalities["document"] >= 10, modalities),
        check("no unreadable or missing non-manifest-only files", not failures, failures[:20]),
    ]
    payload = gate_payload("ok_stage10_open_visual_corpus_download_gate", "blocked_stage10_open_visual_corpus_download_gate", checks, {"modalities": modalities, "existing_file_count": existing, "failures": failures})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

