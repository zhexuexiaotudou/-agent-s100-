#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from ai_nas_common import (
    DEFAULT_PERSONAL_ROOT,
    DEFAULT_REPORT_ROOT,
    DEFAULT_SQLITE_INDEX_PATH,
    build_sqlite_inventory,
    ensure_image_embeddings_for_photos,
    ensure_report_dir,
    iso_now,
    safe_write_json,
    safe_write_text,
    search_embedding_index,
    search_photo_semantic_index,
    search_sqlite_index,
    sqlite_index_status,
)


DEFAULT_QUERY = "2024 renovation payment contract invoice receipt chat screenshot"
DEFAULT_COLLECTION = "2024_renovation_payment_packet"


def merge_match(merged: dict, match: dict, source_label: str) -> None:
    key = match["relative_path"]
    existing = merged.setdefault(
        key,
        {
            "path": match.get("path"),
            "relative_path": key,
            "type": match.get("type"),
            "document_class": match.get("document_class"),
            "entities": match.get("entities") or {},
            "photo": match.get("photo") or {},
            "summary": match.get("summary", ""),
            "confidence": 0.0,
            "score": 0.0,
            "sources": [],
            "reasons": [],
            "evidence_fragments": [],
            "matched_intents": [],
            "missing_intents": [],
        },
    )
    existing["confidence"] = round(max(existing.get("confidence", 0.0), float(match.get("confidence") or 0.0)), 2)
    existing["score"] = round(max(existing.get("score", 0.0), float(match.get("score") or 0.0)), 3)
    if source_label not in existing["sources"]:
        existing["sources"].append(source_label)
    for reason in match.get("reasons") or []:
        if reason not in existing["reasons"]:
            existing["reasons"].append(reason)
    evidence = match.get("evidence")
    if evidence and evidence not in existing["evidence_fragments"]:
        existing["evidence_fragments"].append(evidence)
    for intent in match.get("matched_intents") or []:
        if intent not in existing["matched_intents"]:
            existing["matched_intents"].append(intent)
    for intent in match.get("missing_intents") or []:
        if intent not in existing["missing_intents"]:
            existing["missing_intents"].append(intent)
    if not existing.get("document_class") and match.get("document_class"):
        existing["document_class"] = match["document_class"]
    if not existing.get("entities") and match.get("entities"):
        existing["entities"] = match["entities"]
    if not existing.get("photo") and match.get("photo"):
        existing["photo"] = match["photo"]


def collect_payment_nodes(matches: list[dict]) -> list[dict]:
    nodes = []
    for match in matches:
        entities = match.get("entities") or {}
        dates = entities.get("dates") or []
        amounts = entities.get("amounts") or []
        terms = entities.get("payment_terms") or []
        if not dates and not amounts and not terms:
            continue
        nodes.append(
            {
                "relative_path": match["relative_path"],
                "document_class": match.get("document_class"),
                "dates": dates,
                "amounts": amounts,
                "payment_terms": terms,
                "confidence": match.get("confidence"),
            }
        )
    return nodes


def filter_case_matches(query: str, matches: list[dict]) -> tuple[list[dict], list[dict]]:
    filtered = []
    rejected = []
    q = query.lower()
    requires_visual_intent = any(term in q for term in ["screenshot", "invoice", "receipt", "chat", "截图", "发票", "票据", "聊天"])
    for match in matches:
        summary_text = " ".join(
            [
                match.get("summary", ""),
                " ".join(match.get("evidence_fragments", [])),
                " ".join(match.get("reasons", [])),
            ]
        ).lower()
        only_photo_semantic = set(match.get("sources", [])) == {"photo_semantic_local_visual"}
        if "unrelated" in summary_text or "not related" in summary_text or "irrelevant" in summary_text:
            rejected.append(
                {
                    "relative_path": match["relative_path"],
                    "reason": "explicit negative context near case terms",
                    "confidence": match.get("confidence"),
                }
            )
            continue
        if requires_visual_intent and only_photo_semantic and not match.get("matched_intents"):
            rejected.append(
                {
                    "relative_path": match["relative_path"],
                    "reason": "photo candidate did not match requested visual intent",
                    "confidence": match.get("confidence"),
                    "missing_intents": match.get("missing_intents", []),
                }
            )
            continue
        filtered.append(match)
    return filtered, rejected


def build_copy_suggestions(matches: list[dict], collection_name: str) -> list[dict]:
    suggestions = []
    for match in matches:
        doc_class = match.get("document_class")
        labels = (match.get("photo") or {}).get("labels") or []
        if doc_class and doc_class != "unknown":
            bucket = doc_class
        elif "screenshot" in labels:
            bucket = "screenshots"
        elif labels:
            bucket = labels[0]
        else:
            bucket = match.get("type", "Other")
        suggestions.append(
            {
                "action": "copy_suggestion_only",
                "source_relative_path": match["relative_path"],
                "suggested_target_relative_path": f"Collections/{collection_name}/{bucket}/{Path(match['relative_path']).name}",
                "requires_human_confirmation": True,
                "delete_source": False,
                "move_source": False,
                "overwrite": False,
            }
        )
    return suggestions


def build_case_answer(matches: list[dict], payment_nodes: list[dict], gaps: list[str]) -> str:
    if not matches:
        return "No grounded evidence matched the case query. See gaps and index status before making claims."
    type_counts = Counter(match.get("type", "Unknown") for match in matches)
    class_counts = Counter(match.get("document_class") for match in matches if match.get("document_class"))
    parts = [
        f"Found {len(matches)} evidence files across {dict(sorted(type_counts.items()))}.",
    ]
    if class_counts:
        parts.append(f"Document classes: {dict(sorted(class_counts.items()))}.")
    if payment_nodes:
        node_bits = []
        for node in payment_nodes[:5]:
            details = []
            if node["dates"]:
                details.append("dates " + ", ".join(node["dates"][:3]))
            if node["amounts"]:
                details.append("amounts " + ", ".join(node["amounts"][:3]))
            if details:
                node_bits.append(f"{node['relative_path']} ({'; '.join(details)})")
        if node_bits:
            parts.append("Payment/date/amount nodes: " + " | ".join(node_bits) + ".")
    if gaps:
        parts.append("Important gaps: " + " ".join(gaps[:3]))
    return " ".join(parts)


def infer_gaps(query: str, matches: list[dict]) -> list[str]:
    q = query.lower()
    gaps = []
    if any(term in q for term in ["chat", "聊天"]):
        chat_verified = any(
            "chat" in match["relative_path"].lower()
            or "聊天" in match["relative_path"]
            or "chat" in " ".join((match.get("photo") or {}).get("labels") or [])
            for match in matches
        )
        if not chat_verified:
            gaps.append("No matched file is verified as a chat screenshot; screenshot evidence is reported only when path/labels/OCR indicate it.")
    if any(term in q for term in ["screenshot", "截图"]):
        screenshot_count = sum(1 for match in matches if "screenshot" in ((match.get("photo") or {}).get("labels") or []))
        if screenshot_count == 0:
            gaps.append("No screenshot-labelled image matched; OCR or image model coverage may be incomplete.")
    if not any((match.get("entities") or {}).get("amounts") for match in matches):
        gaps.append("No structured amount was extracted from matched evidence.")
    if not any((match.get("entities") or {}).get("dates") for match in matches):
        gaps.append("No structured date was extracted from matched evidence.")
    return gaps


def summarize(matches: list[dict]) -> dict:
    return {
        "match_count": len(matches),
        "type_counts": dict(sorted(Counter(match.get("type", "Unknown") for match in matches).items())),
        "document_class_counts": dict(
            sorted(Counter(match.get("document_class") for match in matches if match.get("document_class")).items())
        ),
        "photo_label_counts": dict(
            sorted(
                Counter(
                    label
                    for match in matches
                    for label in ((match.get("photo") or {}).get("labels") or [])
                ).items()
            )
        ),
        "source_counts": dict(sorted(Counter(source for match in matches for source in match.get("sources", [])).items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an auditable mixed-source AI-NAS case packet.")
    parser.add_argument("query", nargs="?", default=DEFAULT_QUERY)
    parser.add_argument("--personal-root", type=Path, default=DEFAULT_PERSONAL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sqlite-index-path", type=Path, default=DEFAULT_SQLITE_INDEX_PATH)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION)
    parser.add_argument("--no-refresh-index", action="store_true")
    args = parser.parse_args()

    if not args.no_refresh_index:
        build_sqlite_inventory(args.personal_root, args.sqlite_index_path)
    elif not args.sqlite_index_path.exists():
        build_sqlite_inventory(args.personal_root, args.sqlite_index_path)

    image_upsert = ensure_image_embeddings_for_photos(args.sqlite_index_path)
    merged: dict[str, dict] = {}
    for match in search_sqlite_index(args.sqlite_index_path, args.query, args.limit):
        merge_match(merged, match, "sqlite_text_fts_metadata")
    for match in search_embedding_index(args.sqlite_index_path, args.query, args.limit):
        merge_match(merged, match, "local_hash_embedding")
    photo_query = f"{args.query} invoice screenshot receipt"
    for match in search_photo_semantic_index(args.sqlite_index_path, photo_query, args.limit):
        merge_match(merged, match, "photo_semantic_local_visual")

    candidates = sorted(merged.values(), key=lambda item: (item["confidence"], item["score"], item["relative_path"]), reverse=True)
    matches, rejected_matches = filter_case_matches(args.query, candidates)
    matches = matches[: args.limit]
    payment_nodes = collect_payment_nodes(matches)
    gaps = infer_gaps(args.query, matches)
    suggestions = build_copy_suggestions(matches, args.collection_name)
    payload = {
        "generated_at": iso_now(),
        "query": args.query,
        "personal_root": str(args.personal_root),
        "sqlite_index_path": str(args.sqlite_index_path),
        "index_status": sqlite_index_status(args.sqlite_index_path),
        "image_embedding_upsert": image_upsert,
        "answer": build_case_answer(matches, payment_nodes, gaps),
        "summary": summarize(matches),
        "matches": matches,
        "rejected_matches": rejected_matches,
        "payment_nodes": payment_nodes,
        "gaps": gaps,
        "copyable_organizing_suggestions": suggestions,
        "audit": {
            "tool_id": "ai_nas_case_packet",
            "source_files_modified": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "writes": "Markdown/JSON mixed evidence packet only; may refresh SQLite index and image embedding rows",
            "requires_human_confirmation_for_suggestions": True,
            "grounding_policy": "all claims come from indexed metadata/text/photo evidence; gaps are explicit",
        },
    }

    run_dir = ensure_report_dir(args.report_root, "case_packet")
    json_path = run_dir / "case_packet.json"
    md_path = run_dir / "case_packet.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS Case Packet",
        "",
        f"- query: `{args.query}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- match_count: `{payload['summary']['match_count']}`",
        f"- index_status: `{payload['index_status'].get('status')}`",
        "- policy: report/index only; no delete, no move, no overwrite",
        "",
        "## Answer",
        "",
        payload["answer"],
        "",
        "## Summary",
        "",
        f"- type_counts: `{payload['summary']['type_counts']}`",
        f"- document_class_counts: `{payload['summary']['document_class_counts']}`",
        f"- photo_label_counts: `{payload['summary']['photo_label_counts']}`",
        f"- source_counts: `{payload['summary']['source_counts']}`",
        "",
        "## Evidence Files",
        "",
    ]
    if not matches:
        lines.append("- No indexed evidence matched this case query.")
    for match in matches:
        lines.append(
            f"- `{match['relative_path']}` | confidence `{match['confidence']}` | "
            f"type `{match.get('type')}` | sources `{', '.join(match.get('sources', []))}`"
        )
        if match.get("document_class"):
            lines.append(f"  - document_class: `{match['document_class']}`")
        labels = (match.get("photo") or {}).get("labels") or []
        if labels:
            lines.append(f"  - photo_labels: `{', '.join(labels)}`")
        if match.get("matched_intents"):
            lines.append(f"  - matched_intents: `{', '.join(match['matched_intents'])}`")
        if match.get("missing_intents"):
            lines.append(f"  - missing_intents: `{', '.join(match['missing_intents'])}`")
        for evidence in match.get("evidence_fragments", [])[:3]:
            lines.append(f"  - evidence: {evidence}")
        lines.append(f"  - reasons: {', '.join(match.get('reasons', [])[:10])}")

    lines.extend(["", "## Payment Nodes", ""])
    if not payment_nodes:
        lines.append("- No structured payment/date/amount nodes were extracted from matched files.")
    for node in payment_nodes:
        lines.append(f"- `{node['relative_path']}`")
        if node["dates"]:
            lines.append(f"  - dates: `{', '.join(node['dates'])}`")
        if node["amounts"]:
            lines.append(f"  - amounts: `{', '.join(node['amounts'])}`")
        for term in node["payment_terms"]:
            lines.append(f"  - payment_term: {term}")

    lines.extend(["", "## Gaps", ""])
    if not gaps:
        lines.append("- No explicit evidence gap detected for this bounded query.")
    for gap in gaps:
        lines.append(f"- {gap}")

    lines.extend(["", "## Rejected Candidates", ""])
    if not rejected_matches:
        lines.append("- No rejected candidates.")
    for item in rejected_matches:
        lines.append(f"- `{item['relative_path']}` | confidence `{item.get('confidence')}` | reason: {item['reason']}")
        if item.get("missing_intents"):
            lines.append(f"  - missing_intents: `{', '.join(item['missing_intents'])}`")

    lines.extend(["", "## Copyable Organizing Suggestions", ""])
    if not suggestions:
        lines.append("- No suggestions because no evidence files matched.")
    for suggestion in suggestions:
        lines.append(
            f"- copy `{suggestion['source_relative_path']}` -> "
            f"`{suggestion['suggested_target_relative_path']}`"
        )
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
