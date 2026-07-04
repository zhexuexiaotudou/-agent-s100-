from __future__ import annotations

from collections import defaultdict
from typing import Any

from .event_model import hash_folder
from .journal_db import JournalDB


PROJECT_RULES = [
    ("project_ai_nas", ("ai_nas", "harness", "token", "qwen", "journal")),
    ("project_openclaw_ops", ("openclaw", "copy", "default service", "health")),
    ("project_reports", ("report", "rag", "docs", "gate")),
]

PROJECT_LABELS = {
    "project_ai_nas": "AI-NAS productization",
    "project_openclaw_ops": "OpenClaw operations",
    "project_reports": "Evidence and report writing",
    "project_uncategorized": "Uncategorized local work",
}


class ProjectClassifier:
    def classify_event(self, event: dict[str, Any]) -> str:
        text = " ".join(
            str(event.get(key, ""))
            for key in ("project_id", "source", "event_type", "title", "summary", "folder_hash")
        ).lower()
        for project_id, keywords in PROJECT_RULES:
            if any(keyword in text for keyword in keywords):
                return project_id
        return str(event.get("project_id") or "project_uncategorized")

    def build_project_map(self, events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        grouped: dict[str, set[str]] = defaultdict(set)
        for event in events:
            project_id = self.classify_event(event)
            grouped[project_id].add(str(event.get("folder_hash") or hash_folder(project_id)))
        return {
            project_id: {
                "project_id": project_id,
                "label": PROJECT_LABELS.get(project_id, project_id.replace("_", " ").title()),
                "folder_hashes": sorted(folder_hashes),
                "qwen_suggestion_used": False,
                "qwen_execution_authority": False,
            }
            for project_id, folder_hashes in grouped.items()
        }

    def persist_project_map(self, db: JournalDB, events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        project_map = self.build_project_map(events)
        for project in project_map.values():
            db.upsert_project(project["project_id"], project["label"], project["folder_hashes"])
        return project_map

    def apply_manual_override(self, db: JournalDB, project_id: str, label: str, folder_hint: str) -> None:
        db.upsert_project(project_id, label, [hash_folder(folder_hint)], manual_override=True)
