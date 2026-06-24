#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3, sys, re
from pathlib import Path
from ai_nas_common import ensure_report_dir, iso_now, safe_write_json
from ai_nas_copilot import CopilotStore

TOOL_ID = "ai_nas_copilot_product_gate"; OK = "ok_ai_nas_copilot_product_gate"

def chk(msg, cond, fails): fails.append(msg) if not cond else None; print(f"  {'PASS' if cond else 'FAIL'}: {msg}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, default=Path("tmp/nas_copilot_gate_local"))
    args = parser.parse_args()
    rd = ensure_report_dir(args.report_root, "copilot_gate")
    docs_dir = rd / "Docs"; docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir/"sub").mkdir(exist_ok=True)
    db = rd / "copilot.db"
    store = CopilotStore(db)
    fails = []
    print("Goal 7 AI-NAS Copilot Gate Probe (direct)")

    # Create test docs
    (docs_dir/"doc1.txt").write_text("This is a contract about office renovation from 2025. Payment terms are net 30 days. Total cost is $50,000 for the renovation work.")
    (docs_dir/"doc2.txt").write_text("Invoice for payment of office supplies. Company: ABC Corp. Amount: $1,200. Date: 2025-03-15. Payment due by April 15.")
    (docs_dir/"sub/doc3.md").write_text("# Project Report\n\nThis quarter we completed the website redesign and launched the new marketing campaign. The renovation project is also complete.")

    # 1. Index
    print("\n--- Document Indexing ---")
    r = store.index_documents(docs_dir)
    chk(f"Indexed {r['indexed']} documents", r["indexed"] >= 3, fails)

    # 2. List
    docs = store.list_docs()
    chk(f"List {len(docs)} docs", len(docs) >= 3, fails)
    chk("Folder filtering", len(store.list_docs("sub")) == 1, fails)

    # 3. Search
    print("\n--- Search ---")
    results = store.search("renovation contract")
    chk("Search finds renovation", len(results) >= 2, fails)
    results2 = store.search("office supplies invoice")
    chk("Search finds invoice", len(results2) >= 1, fails)

    # 4. Folder-level search
    results3 = store.search("website marketing", "sub")
    chk("Folder search finds report", len(results3) >= 1, fails)

    # 5. Q&A with citations
    print("\n--- Q&A ---")
    a = store.answer_question("how much does the renovation cost")
    chk("Q&A returns answer", len(a["answer"]) > 20, fails)
    chk("Q&A has sources", len(a["sources"]) >= 1, fails)
    chk("Sources contain file paths", all("path" in s for s in a["sources"]), fails)

    # 6. Multi-file Q&A
    a2 = store.answer_question("payment invoice renovation")
    chk("Multi-file Q&A with citations", len(a2["sources"]) >= 2, fails)

    # 7. Stats
    stats = store.stats()
    chk(f"Stats: {stats['doc_count']} docs, {stats['keyword_count']} keywords", stats["doc_count"] >= 3, fails)

    # DB integrity
    con = sqlite3.connect(str(db))
    chk("Copilot DB integrity", con.execute("PRAGMA integrity_check").fetchone()[0]=="ok", fails); con.close()

    passed = len(fails) == 0; verdict = OK if passed else "failed_ai_nas_copilot_product_gate"
    total = 12
    print(f"\n{'='*60}\n  Verdict: {verdict}\n  Passed: {total-len(fails)}/{total}")
    if fails: print(f"  Failures: {len(fails)}"); [print(f"    - {f}") for f in fails]
    print(f"{'='*60}")
    payload = {"generated_at":iso_now(),"tool_id":TOOL_ID,"verdict":verdict,"passed_count":total-len(fails),"failures":fails}
    safe_write_json(rd/"copilot_product_gate.json", payload)
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
