#!/usr/bin/env sh
set -eu

if [ -n "${DIGUA_JOURNAL_DB_PATH:-}" ]; then
  python3 - "$DIGUA_JOURNAL_DB_PATH" "${DIGUA_JOURNAL_REPORT_ROOT:-}" <<'PY'
import json
import sys
from pathlib import Path

from src.digua_journal.collectors import collect_sample_nas_index_diff_events, collect_sample_system_events
from src.digua_journal.journal_db import JournalDB

db_path = Path(sys.argv[1])
report_root = Path(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else db_path.parent
report_root.mkdir(parents=True, exist_ok=True)

db = JournalDB(db_path)
migration = db.migrate()
events = [*collect_sample_nas_index_diff_events(32), *collect_sample_system_events()]
event_ids = db.insert_events(events)
events_jsonl = report_root / "digua_journal_collectors_once_events.jsonl"
with events_jsonl.open("w", encoding="utf-8", newline="\n") as handle:
    for event in events:
        handle.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")

print(json.dumps({
    "ok": True,
    "mode": "live_db",
    "db_path": str(db_path),
    "migration": migration,
    "event_count": len(event_ids),
    "events_jsonl": str(events_jsonl),
    "stats": db.stats(),
}, ensure_ascii=False, sort_keys=True))
PY
  exit 0
fi

python3 scripts/probes/digua_journal_production_deployment.py --collectors-only
