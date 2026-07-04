from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "migrations" / "create_digua_journal_tables.sql"


def load_schema_sql() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")
