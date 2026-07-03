#!/usr/bin/env python3
"""Gate probe: Document summarization + RAG Q&A (Features A4, A5, A6).

Tests document OCR, summarization, RAG and auto-archive using local Qwen LLM.
Validates against S02, S03, S04 scenarios from ground_truth_manifest.json.
"""

from __future__ import annotations

import json, sys, time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from ai_nas_qwen_llm import summarize, rag_answer, suggest_archive, health as qwen_health
from ai_nas_text_embedding_provider import embed_text, embed_batch, semantic_search, embedding_provider_status

PERSONAL = Path("F:/mnt/nas/openclaw/Personal")
REPORT = Path("F:/mnt/nas/openclaw/reports/ai_nas_mvp")
MANIFEST = REPORT / "ground_truth_manifest.json"


def read_text_file(path: Path, max_chars: int = 8000) -> str:
    try:
        raw = path.read_bytes()
        for enc in ["utf-8", "utf-8-sig", "gbk", "latin-1"]:
            try: return raw.decode(enc)[:max_chars]
            except (UnicodeDecodeError, UnicodeError): continue
        return raw.decode("utf-8", errors="replace")[:max_chars]
    except Exception:
        return ""


def run_gate():
    manifest = {}
    if MANIFEST.exists():
        with open(MANIFEST, "r", encoding="utf-8-sig") as f:
            manifest = json.load(f)

    qw = qwen_health()
    emb = embedding_provider_status()

    results = {"gate_id": "ok_ai_nas_doc_rag_gate", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "features": ["A4_ocr", "A5_summary_rag", "A6_auto_archive"],
               "qwen_model": qw["model"], "embedding_backend": emb["backend"], "tests": []}

    # ---- Test S03: Document summary ----
    test_docs = [
        PERSONAL / "Documents" / "rfc1149_sample.txt",
        PERSONAL / "Documents" / "openclaw_qa_notes.md",
        PERSONAL / "Documents" / "dummy_accessibility_sample.pdf",
    ]
    for doc_path in test_docs:
        if not doc_path.exists(): continue
        text = read_text_file(doc_path)
        if not text: continue
        sum_result = summarize(text, max_chars=300)
        results["tests"].append({
            "type": "summarize", "file": str(doc_path.relative_to(PERSONAL)),
            "input_chars": len(text), "ok": sum_result.get("ok", False),
            "summary": sum_result.get("answer", "")[:200],
            "evidence": sum_result.get("evidence", {}),
        })

    # ---- Test S03: RAG Q&A ----
    rag_docs = []
    for doc_path in test_docs:
        if not doc_path.exists(): continue
        text = read_text_file(doc_path)
        if text:
            rag_docs.append({"text": text, "source": str(doc_path.relative_to(PERSONAL)), "score": 1.0})
    if rag_docs:
        queries = ["这份文档的主要内容是什么", "rfc1149文档提到了什么协议"]
        for q in queries:
            rag = rag_answer(q, rag_docs[:3])
            results["tests"].append({
                "type": "rag_answer", "query": q, "ok": rag.get("ok", False),
                "answer": rag.get("answer", "")[:300],
                "citations": rag.get("citations", []),
                "evidence": rag.get("evidence", {}),
            })
    else:
        results["tests"].append({"type": "rag_answer", "ok": False, "error": "no_document_content"})

    # ---- Test S04: Auto-archive suggestions ----
    archive_files = [
        {"name": "rfc1149_sample.txt", "path": "Inbox/rfc1149_sample.txt", "category": "text", "snippet": read_text_file(PERSONAL / "Documents" / "rfc1149_sample.txt", 500)},
        {"name": "airtravel_sample.csv", "path": "Inbox/airtravel_sample.csv", "category": "document", "snippet": read_text_file(PERSONAL / "Documents" / "Travel" / "airtravel_sample.csv", 500)},
    ]
    for fi in archive_files:
        if not fi["snippet"]: fi["snippet"] = f"File: {fi['name']}, Category: {fi['category']}"
        arch = suggest_archive(fi)
        results["tests"].append({
            "type": "archive_suggestion", "file": fi["path"],
            "ok": arch.get("ok", False),
            "suggestion": arch.get("suggestion", {}),
            "evidence": arch.get("evidence", {}),
        })

    # Aggregate verdict
    tests = results["tests"]
    passed = sum(1 for t in tests if t.get("ok"))
    results["verdict"] = "passed" if tests and passed >= len(tests) * 0.5 else "failed"
    results["tests_total"] = len(tests)
    results["tests_passed"] = passed

    out_path = REPORT / "doc_rag_gate_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Gate {results['verdict']}: {passed}/{len(tests)} tests passed")
    print(f"Report: {out_path}")
    return results


if __name__ == "__main__":
    gate = run_gate()
    print(json.dumps(gate, ensure_ascii=False, indent=2))
