from __future__ import annotations

import argparse
from pathlib import Path

from ai_space_gate_common import check, write_gate
from stage10_common import add_stage10_args, all_manifest_records, gate_payload, has_raw_path


NAME = "stage10_open_visual_corpus_license_gate"
THIRD_PARTY = {"open_images", "wikimedia"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate demo corpus license and attribution metadata.")
    add_stage10_args(parser)
    args = parser.parse_args()
    records = all_manifest_records(args.corpus_root)
    third_party = [r for r in records if r.get("source") in THIRD_PARTY]
    failures = []
    for record in records:
        prefix = record.get("asset_id")
        if not record.get("license_verified"):
            failures.append(f"{prefix}:license_not_verified")
        if not record.get("license"):
            failures.append(f"{prefix}:license_missing")
        if record.get("source") in THIRD_PARTY:
            for key in ("source_url", "source_id", "author", "attribution"):
                if not record.get(key):
                    failures.append(f"{prefix}:{key}_missing")
            if record.get("release_package_includes_file"):
                failures.append(f"{prefix}:third_party_file_marked_for_release")
        if record.get("raw_path_returned") is not False:
            failures.append(f"{prefix}:raw_path_flag_not_false")
    checks = [
        check("manifest records exist", bool(records), len(records)),
        check("license docs exist", all((args.corpus_root / "licenses" / name).exists() for name in ["ATTRIBUTION.md", "LICENSES.md", "THIRD_PARTY_NOTICES.md"]), "license docs"),
        check("downloaded ignored", (args.corpus_root / "downloaded" / ".gitignore").exists(), "downloaded/.gitignore"),
        check("third-party files manifest-only", not failures, failures[:20]),
        check("no raw paths in manifests", not has_raw_path(records), "redacted"),
    ]
    payload = gate_payload("ok_stage10_open_visual_corpus_license_gate", "blocked_stage10_open_visual_corpus_license_gate", checks, {"record_count": len(records), "third_party_count": len(third_party), "failures": failures})
    json_path, md_path = write_gate(args.report_root, NAME, payload)
    print(md_path)
    print(json_path)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

