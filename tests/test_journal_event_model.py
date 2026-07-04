from __future__ import annotations

import pytest

from src.digua_journal.event_model import make_event


def test_journal_event_redacts_private_path_and_blocks_raw_content() -> None:
    event = make_event(
        source="nas_index_diff",
        event_type="file_added",
        project_id="project_ai_nas",
        folder_hint="/mnt/nas/openclaw/Personal/secret-folder",
        title="Added /mnt/nas/openclaw/Personal/private.docx",
        summary="Safe summary",
        metadata={"raw_path": "/mnt/nas/openclaw/Personal/private.docx"},
    )
    payload = event.to_dict()
    assert "/mnt/nas/openclaw/Personal" not in str(payload)
    assert payload["raw_content_stored"] is False
    assert payload["metadata"]["raw_path_omitted"] is True


def test_journal_event_rejects_unknown_source() -> None:
    with pytest.raises(ValueError):
        make_event(
            source="unknown",
            event_type="file_added",
            project_id="project_ai_nas",
            folder_hint="folder",
            title="bad source",
            summary="bad source",
        )
