#!/usr/bin/env bash
set -euo pipefail

dataset_root="${1:-${OPENCLAW_DATASET_DIR:-/root/.openclaw/workspace/robot_datasets}}"
report_dir="${2:-${OPENCLAW_REPORT_DIR:-/root/.openclaw/workspace/reports/robot-datasets}}"

case "$dataset_root" in
  /tmp/*|/mnt/nas/openclaw/robot_datasets|/mnt/nas/openclaw/robot_datasets/*|/root/.openclaw/workspace/robot_datasets|/root/.openclaw/workspace/robot_datasets/*) ;;
  *)
    echo "Refusing dataset root outside approved robot dataset directories: $dataset_root" >&2
    exit 2
    ;;
esac

case "$report_dir" in
  /tmp/*|/mnt/nas/openclaw/reports|/mnt/nas/openclaw/reports/*|/root/.openclaw/workspace/reports|/root/.openclaw/workspace/reports/*) ;;
  *)
    echo "Refusing report directory outside approved report directories: $report_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$report_dir"
stamp="$(date +%Y%m%d-%H%M%S)"
report="$report_dir/dataset_card_inventory_$stamp.md"
json="$report_dir/dataset_card_inventory_$stamp.json"

python3 - "$dataset_root" "$report" "$json" <<'PY'
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

dataset_root = Path(sys.argv[1])
report = Path(sys.argv[2])
json_path = Path(sys.argv[3])


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


cards = []
if dataset_root.exists():
    for card in sorted(dataset_root.glob("*/DATASET_CARD.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = card.stat()
        dataset_dir = card.parent
        bag_files = sorted(dataset_dir.glob("*.bag*")) + sorted(dataset_dir.glob("*.db3"))
        metadata_files = sorted(dataset_dir.glob("metadata.y*ml")) + sorted(dataset_dir.glob("*.json"))
        cards.append(
            {
                "dataset": dataset_dir.name,
                "card_path": str(card),
                "card_size_bytes": stat.st_size,
                "card_mtime": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
                "card_sha256": digest(card),
                "bag_file_count": len(bag_files),
                "metadata_file_count": len(metadata_files),
            }
        )

payload = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "mode": "read-only dataset card inventory; no capture or dataset creation",
    "dataset_root": str(dataset_root),
    "report": str(report),
    "dataset_card_count": len(cards),
    "latest_dataset_card": cards[0]["card_path"] if cards else None,
    "cards": cards,
}

json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

with report.open("w", encoding="utf-8") as out:
    out.write("# Dataset Card Inventory\n\n")
    out.write(f"- generated_at: {payload['generated_at']}\n")
    out.write("- mode: read-only dataset card inventory; no capture or dataset creation\n")
    out.write(f"- dataset_root: {dataset_root}\n")
    out.write(f"- dataset_card_count: {len(cards)}\n")
    out.write(f"- latest_dataset_card: {payload['latest_dataset_card'] or 'missing'}\n")
    out.write("- verdict: " + ("ok" if cards else "missing_dataset_cards") + "\n\n")
    out.write("| Dataset | Card | Size bytes | Bag files | Metadata files | SHA256 |\n")
    out.write("| --- | --- | ---: | ---: | ---: | --- |\n")
    if cards:
        for card in cards:
            out.write(
                f"| {card['dataset']} | {card['card_path']} | {card['card_size_bytes']} | "
                f"{card['bag_file_count']} | {card['metadata_file_count']} | {card['card_sha256']} |\n"
            )
    else:
        out.write("| missing | missing | 0 | 0 | 0 | missing |\n")

print(report)
PY
