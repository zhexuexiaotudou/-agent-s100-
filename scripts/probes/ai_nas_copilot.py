#!/usr/bin/env python3
"""AI-NAS Copilot — document indexing, keyword search, folder-level RAG, citation backlinks."""
from __future__ import annotations
import hashlib, json, re, sqlite3, time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

def _now_iso(): return datetime.now(timezone.utc).isoformat()

def _init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL, extension TEXT, size_bytes INTEGER, mtime REAL,
            text_content TEXT, keyword_count INTEGER DEFAULT 0,
            folder TEXT DEFAULT '', indexed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS keywords(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL, doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            count INTEGER DEFAULT 1, UNIQUE(keyword, doc_id)
        );
        CREATE INDEX IF NOT EXISTS idx_keywords_kw ON keywords(keyword);
        CREATE INDEX IF NOT EXISTS idx_docs_folder ON documents(folder);
    """)
    con.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version','1')")
    con.commit(); con.close()

TEXT_EXTS = {".txt",".md",".rst",".csv",".json",".xml",".html",".htm",".py",".log",".yaml",".yml",".cfg",".ini"}

class CopilotStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path; _init_db(db_path)
    def _connect(self):
        c = sqlite3.connect(str(self.db_path)); c.execute("PRAGMA foreign_keys=ON"); c.row_factory = sqlite3.Row; return c

    def index_documents(self, root: Path) -> dict:
        scanned, indexed, skipped = 0, 0, 0
        con = self._connect()
        try:
            for f in root.rglob("*"):
                if not f.is_file() or f.suffix.lower() not in TEXT_EXTS: continue
                scanned += 1
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                except: skipped += 1; continue
                st = f.stat()
                folder = str(f.parent.relative_to(root)) if root in f.parents else ""
                existing = con.execute("SELECT id, text_content FROM documents WHERE file_path=?",(str(f),)).fetchone()
                if existing and existing["text_content"] == text:
                    skipped += 1; continue
                if existing:
                    con.execute("DELETE FROM keywords WHERE doc_id=?",(existing["id"],))
                    con.execute("UPDATE documents SET text_content=?,keyword_count=?,indexed_at=? WHERE id=?",(text,0,_now_iso(),existing["id"]))
                    doc_id = existing["id"]
                else:
                    con.execute("INSERT INTO documents(file_path,name,extension,size_bytes,mtime,text_content,folder,indexed_at) VALUES(?,?,?,?,?,?,?,?)",(str(f),f.name,f.suffix,st.st_size,st.st_mtime,text,folder,_now_iso()))
                    doc_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
                kws = self._extract_keywords(text)
                for kw, cnt in kws.items():
                    con.execute("INSERT OR IGNORE INTO keywords(keyword,doc_id,count) VALUES(?,?,?)",(kw,doc_id,cnt))
                con.execute("UPDATE documents SET keyword_count=? WHERE id=?",(len(kws),doc_id))
                indexed += 1
            con.commit()
        finally: con.close()
        return {"scanned":scanned,"indexed":indexed,"skipped":skipped}

    def _extract_keywords(self, text: str) -> Counter[str]:
        words = re.findall(r"[a-zA-Z\u4e00-\u9fff]{2,}", text.lower())
        stop = {"the","and","for","this","that","with","from","are","was","were","have","has","had","not","but","all","can","may","will","would","should","could","been","being","been","its","into","also","than","then","them","they","some","such","more","only","over","very","when","what","which","who","how","where","about","each","any","both","just","now","out","after","other","these","those","between","through","during","before","their","there"}
        return Counter(w for w in words if w not in stop)

    def search(self, query: str, folder: str = "", limit: int = 20) -> list[dict]:
        con = self._connect()
        try:
            qwords = re.findall(r"[a-zA-Z\u4e00-\u9fff]{2,}", query.lower())
            if not qwords: return []
            placeholders = ",".join(["?"]*len(qwords))
            sql = f"SELECT d.*, SUM(k.count) as relevance FROM documents d JOIN keywords k ON d.id=k.doc_id WHERE k.keyword IN ({placeholders})"
            params = list(qwords)
            if folder:
                sql += " AND d.folder=?"; params.append(folder)
            sql += " GROUP BY d.id ORDER BY relevance DESC LIMIT ?"
            params.append(limit)
            rows = con.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally: con.close()

    def list_docs(self, folder: str = "") -> list[dict]:
        con = self._connect()
        try:
            if folder:
                return [dict(r) for r in con.execute("SELECT * FROM documents WHERE folder=? ORDER BY name",(folder,)).fetchall()]
            return [dict(r) for r in con.execute("SELECT * FROM documents ORDER BY name").fetchall()]
        finally: con.close()

    def get_document(self, doc_id: int) -> dict | None:
        con = self._connect()
        try:
            r = con.execute("SELECT * FROM documents WHERE id=?",(doc_id,)).fetchone()
            return dict(r) if r else None
        finally: con.close()

    def answer_question(self, question: str, folder: str = "", max_docs: int = 5) -> dict:
        results = self.search(question, folder, max_docs)
        if not results:
            return {"answer":"No relevant documents found.","sources":[]}
        best = results[0]
        sources = [{"file": r["name"], "path": r["file_path"], "folder": r["folder"]} for r in results]
        snippet = (best.get("text_content","") or "")[:500]
        answer = f"Found {len(results)} relevant document(s). Top match: {best['name']} (in {best.get('folder','root')}). "
        if snippet:
            words = re.findall(r"[a-zA-Z\u4e00-\u9fff]{2,}", question.lower())
            for w in words:
                idx = snippet.lower().find(w)
                if idx >= 0:
                    start = max(0, idx-40); end = min(len(snippet), idx+len(w)+40)
                    answer += f'[...{snippet[start:end]}...] '; break
            else:
                answer += f"Preview: {snippet[:200]}..."
        reference_ids = ",".join(r["name"] for r in results[:3])
        answer += f" Sources: {reference_ids}."
        return {"answer":answer,"sources":sources}

    def stats(self) -> dict:
        con = self._connect()
        try:
            dc = con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            kc = con.execute("SELECT COUNT(*) FROM keywords").fetchone()[0]
            return {"doc_count":dc,"keyword_count":kc}
        finally: con.close()
