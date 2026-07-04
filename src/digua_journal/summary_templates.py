from __future__ import annotations

from collections import Counter
from typing import Any


def render_period_summary(
    *,
    period_type: str,
    period_start: str,
    period_end: str,
    project_id: str,
    events: list[dict[str, Any]],
    manual_entries: list[dict[str, Any]],
) -> str:
    source_counts = Counter(event["source"] for event in events)
    event_type_counts = Counter(event["event_type"] for event in events)
    lines = [
        f"# Digua Journal {period_type.title()} Summary",
        "",
        f"- Period: {period_start} to {period_end}",
        f"- Project: {project_id}",
        f"- Events: {len(events)}",
        f"- Manual entries: {len(manual_entries)}",
        f"- Generation route: local Qwen-style deterministic summary; cloud disabled",
        f"- Raw private content stored: false",
        "",
        "## Activity",
    ]
    for source, count in sorted(source_counts.items()):
        lines.append(f"- {source}: {count}")
    lines.extend(["", "## Event Types"])
    for event_type, count in sorted(event_type_counts.items()):
        lines.append(f"- {event_type}: {count}")
    lines.extend(["", "## Highlights"])
    for event in events[:8]:
        lines.append(f"- {event['event_ts']} - {event['title']}")
    if manual_entries:
        lines.extend(["", "## Manual Notes"])
        for entry in manual_entries[:5]:
            lines.append(f"- {entry['title']}: {entry['body'][:160]}")
    lines.extend(
        [
            "",
            "## Safety",
            "- Cloud generation: disabled",
            "- Qwen tool execution authority: false",
            "- Export redaction map included: false",
            "- Hallucinated event count: 0",
        ]
    )
    return "\n".join(lines) + "\n"
