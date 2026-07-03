#!/usr/bin/env python3
"""Unified gate probe for Qwen2.5-7B AI-NAS features.

Runs ALL feature tests against the 7B model (port 18080).
Tests: A2 (search), A5 (summarize/RAG), A6 (archive), A7 (movie), A9 (classify), A12 (report).
"""

from __future__ import annotations

import json, sys, time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from ai_nas_qwen_llm import (
    health as qwen_health, summarize, rag_answer, suggest_archive,
    extract_movie_metadata, classify, generate_report, rewrite_query
)

PERSONAL = Path("F:/mnt/nas/openclaw/Personal")
REPORT = Path("F:/mnt/nas/openclaw/reports/ai_nas_mvp")


def read_text(path: Path, max_chars: int = 4000) -> str:
    try:
        raw = path.read_bytes()
        for enc in ["utf-8", "utf-8-sig", "gbk", "latin-1"]:
            try: return raw.decode(enc)[:max_chars]
            except: continue
        return raw.decode("utf-8", errors="replace")[:max_chars]
    except: return ""


def run_all():
    qw = qwen_health()
    results = {"gate_id": "ok_ai_nas_7b_unified_gate", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": qw["model"], "tests": [], "verdict": "pending"}

    # ---- A2: Query rewrite ----
    queries = ["查找所有装修合同", "上周的发票在哪里", "显示海滩照片", "找一部动作电影"]
    for q in queries:
        rw = rewrite_query(q)
        results["tests"].append({"feature": "A2_query_rewrite", "query": q, "ok": rw.get("ok", False), "intent": rw.get("intent", {}), "evidence": rw.get("evidence", {})})

    # ---- A5: Summarize ----
    doc_paths = [PERSONAL / "Documents" / "openclaw_qa_notes.md", PERSONAL / "Documents" / "rfc1149_sample.txt"]
    for dp in doc_paths:
        if not dp.exists(): continue
        text = read_text(dp)
        if not text: continue
        sm = summarize(text, max_chars=200)
        results["tests"].append({"feature": "A5_summarize", "file": dp.name, "ok": sm.get("ok", False), "summary": sm.get("answer", "")[:200], "evidence": sm.get("evidence", {})})

    # ---- A5: RAG ----
    chunks = []
    for dp in doc_paths:
        if dp.exists():
            t = read_text(dp)
            if t: chunks.append({"text": t, "source": dp.name, "score": 1.0})
    if chunks:
        rag = rag_answer("这些文档的主要内容是什么", chunks[:2])
        results["tests"].append({"feature": "A5_rag", "query": "文档摘要", "ok": rag.get("ok", False), "answer": rag.get("answer", "")[:300], "citations": rag.get("citations", []), "evidence": rag.get("evidence", {})})

    # ---- A6: Archive ----
    af = [{"name": "rfc1149_sample.txt", "path": "Inbox/rfc1149_sample.txt", "category": "text", "snippet": read_text(PERSONAL / "Documents" / "rfc1149_sample.txt", 500)}]
    for fi in af:
        if fi["snippet"]:
            arch = suggest_archive(fi)
            results["tests"].append({"feature": "A6_archive", "file": fi["name"], "ok": arch.get("ok", False), "suggestion": arch.get("suggestion", {}), "evidence": arch.get("evidence", {})})

    # ---- A7: Movie metadata ----
    movies = ["The.Dark.Knight.2008.1080p.BluRay.x264-YIFY.mp4", "Breaking.Bad.S01E01.720p.WEBRip.x264-Group.mkv", "big_buck_bunny_sample.mp4"]
    for m in movies:
        mm = extract_movie_metadata(m)
        results["tests"].append({"feature": "A7_movie_meta", "filename": m, "ok": mm.get("ok", False), "metadata": mm.get("metadata", {}), "evidence": mm.get("evidence", {})})

    # ---- A9: Photo classify ----
    photo_items = [{"name": "beach.jpg", "desc": "A child playing on a sandy beach with blue ocean"}, {"name": "invoice.png", "desc": "A scanned invoice document with company letterhead"}, {"name": "soccer.jpg", "desc": "A green soccer field with goal posts under sunny sky"}]
    cats = ["beach", "sports", "document", "meal", "portrait", "other"]
    for pd in photo_items:
        cl = classify(f"File: {pd['name']}\nDescription: {pd['desc']}", cats)
        results["tests"].append({"feature": "A9_photo_classify", "file": pd["name"], "ok": cl.get("ok", False), "category": cl.get("category", ""), "evidence": cl.get("evidence", {})})

    # ---- A12: AI Report ----
    sections = [{"heading": "存储概览", "data_summary": "总计194个文件，文档类占比最高。存储使用率约35%。"}, {"heading": "本周活动", "data_summary": "新增12个文件，修改5个文件。"}, {"heading": "AI分析", "data_summary": "自动分类准确率约85%。重复图片检测发现2组相似图片。"}]
    rep = generate_report("AI-NAS 周报 2026-W26", sections)
    results["tests"].append({"feature": "A12_ai_report", "ok": rep.get("ok", False), "report": rep.get("answer", "")[:300], "evidence": rep.get("evidence", {})})

    tests = results["tests"]
    passed = sum(1 for t in tests if t.get("ok"))
    results["verdict"] = "passed" if passed >= len(tests) * 0.5 else "failed"
    results["tests_total"] = len(tests)
    results["tests_passed"] = passed

    out = REPORT / "7b_unified_gate_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"7B Unified Gate: {results['verdict']} ({passed}/{len(tests)} passed)")
    print(f"Report: {out}")
    return results


if __name__ == "__main__":
    gate = run_all()
    print(json.dumps(gate, ensure_ascii=False, indent=2))
