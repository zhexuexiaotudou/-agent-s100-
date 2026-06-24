#!/usr/bin/env python3
"""AI-NAS Media Center — photo indexing, timeline, albums, duplicate detection."""
from __future__ import annotations
import hashlib, json, os, re, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path

IMAGE_EXTS = {".jpg",".jpeg",".png",".gif",".bmp",".webp",".tiff",".tif",".heic",".heif",".raw",".cr2",".nef",".arw"}
VIDEO_EXTS = {".mp4",".mov",".avi",".mkv",".wmv",".flv",".webm",".m4v",".3gp"}

def _now_iso(): return datetime.now(timezone.utc).isoformat()

def _init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS photos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            extension TEXT, size_bytes INTEGER, mtime REAL, ctime REAL,
            width INTEGER, height INTEGER, camera_model TEXT,
            taken_at TEXT, gps_lat REAL, gps_lon REAL,
            sha256 TEXT, phash TEXT, tags TEXT,
            indexed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS albums(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE, description TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS album_items(
            album_id INTEGER REFERENCES albums(id) ON DELETE CASCADE,
            photo_id INTEGER REFERENCES photos(id) ON DELETE CASCADE,
            added_at TEXT NOT NULL, PRIMARY KEY(album_id, photo_id)
        );
        CREATE INDEX IF NOT EXISTS idx_photos_taken ON photos(taken_at);
        CREATE INDEX IF NOT EXISTS idx_photos_sha ON photos(sha256);
    """)
    con.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version','1')")
    con.commit(); con.close()

class MediaCenter:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path; _init_db(db_path)
    def _connect(self):
        c = sqlite3.connect(str(self.db_path)); c.execute("PRAGMA foreign_keys=ON"); c.row_factory = sqlite3.Row; return c

    def index_photos(self, root: Path) -> dict:
        scanned, indexed, skipped = 0, 0, 0
        con = self._connect()
        try:
            for f in root.rglob("*"):
                if not f.is_file(): continue
                ext = f.suffix.lower()
                if ext not in IMAGE_EXTS and ext not in VIDEO_EXTS: continue
                scanned += 1
                existing = con.execute("SELECT id, sha256 FROM photos WHERE file_path=?",(str(f),)).fetchone()
                sha = self._hash(f)
                if existing and existing["sha256"] == sha:
                    skipped += 1; continue
                st = f.stat()
                taken = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
                if existing:
                    con.execute("UPDATE photos SET size_bytes=?,mtime=?,sha256=?,indexed_at=? WHERE id=?",(st.st_size,st.st_mtime,sha,_now_iso(),existing["id"]))
                else:
                    con.execute("INSERT INTO photos(file_path,name,extension,size_bytes,mtime,ctime,taken_at,sha256,indexed_at) VALUES(?,?,?,?,?,?,?,?,?)",(str(f),f.name,ext,st.st_size,st.st_mtime,st.st_ctime,taken,sha,_now_iso()))
                indexed += 1
            con.commit()
        finally: con.close()
        return {"scanned":scanned,"indexed":indexed,"skipped":skipped}

    def list_photos(self, limit=100, offset=0) -> list[dict]:
        con = self._connect()
        try:
            return [dict(r) for r in con.execute(
                "SELECT * FROM photos WHERE lower(extension) IN ({}) ORDER BY taken_at DESC LIMIT ? OFFSET ?".format(
                    ",".join("?" for _ in IMAGE_EXTS)
                ),
                tuple(sorted(IMAGE_EXTS)) + (limit, offset),
            ).fetchall()]
        finally: con.close()

    def list_movies(self, limit=100, offset=0) -> list[dict]:
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT * FROM photos WHERE lower(extension) IN ({}) ORDER BY taken_at DESC LIMIT ? OFFSET ?".format(
                    ",".join("?" for _ in VIDEO_EXTS)
                ),
                tuple(sorted(VIDEO_EXTS)) + (limit, offset),
            ).fetchall()
            return [self._movie_payload(dict(r)) for r in rows]
        finally: con.close()

    def timeline(self) -> list[dict]:
        con = self._connect()
        try:
            rows = con.execute("SELECT DATE(taken_at) as date, COUNT(*) as count FROM photos WHERE taken_at IS NOT NULL GROUP BY DATE(taken_at) ORDER BY date DESC").fetchall()
            return [dict(r) for r in rows]
        finally: con.close()

    def find_duplicates(self) -> list[dict]:
        con = self._connect()
        try:
            rows = con.execute("SELECT sha256, COUNT(*) as cnt, GROUP_CONCAT(file_path,'||') as paths FROM photos WHERE sha256 IS NOT NULL GROUP BY sha256 HAVING cnt > 1 ORDER BY cnt DESC").fetchall()
            return [dict(r) for r in rows]
        finally: con.close()

    def create_album(self, name: str, description: str="") -> dict:
        con = self._connect()
        try:
            con.execute("INSERT INTO albums(name,description,created_at) VALUES(?,?,?)",(name,description,_now_iso())); con.commit()
            return {"ok":True,"id":con.execute("SELECT last_insert_rowid()").fetchone()[0]}
        except sqlite3.IntegrityError: return {"ok":False,"error":"album_exists"}
        finally: con.close()

    def list_albums(self) -> list[dict]:
        con = self._connect()
        try: return [dict(r) for r in con.execute("SELECT * FROM albums ORDER BY name").fetchall()]
        finally: con.close()

    def add_to_album(self, album_name: str, photo_id: int) -> dict:
        con = self._connect()
        try:
            a = con.execute("SELECT id FROM albums WHERE name=?",(album_name,)).fetchone()
            if not a: return {"ok":False,"error":"album_not_found"}
            p = con.execute("SELECT id FROM photos WHERE id=?",(photo_id,)).fetchone()
            if not p: return {"ok":False,"error":"photo_not_found"}
            con.execute("INSERT OR IGNORE INTO album_items(album_id,photo_id,added_at) VALUES(?,?,?)",(a["id"],photo_id,_now_iso())); con.commit()
            return {"ok":True}
        finally: con.close()

    def get_album_photos(self, album_name: str) -> list[dict]:
        con = self._connect()
        try:
            return [dict(r) for r in con.execute("SELECT p.* FROM photos p JOIN album_items ai ON p.id=ai.photo_id JOIN albums a ON ai.album_id=a.id WHERE a.name=? ORDER BY p.taken_at DESC",(album_name,)).fetchall()]
        finally: con.close()

    def search(self, query: str) -> list[dict]:
        con = self._connect()
        try:
            q = f"%{query}%"
            return [dict(r) for r in con.execute("SELECT * FROM photos WHERE name LIKE ? OR extension LIKE ? OR tags LIKE ? ORDER BY taken_at DESC LIMIT 100",(q,q,q)).fetchall()]
        finally: con.close()

    def _hash(self, path: Path) -> str:
        try: return hashlib.sha256(path.read_bytes()).hexdigest()
        except: return ""

    def stats(self) -> dict:
        con = self._connect()
        try:
            pc = con.execute(
                "SELECT COUNT(*) FROM photos WHERE lower(extension) IN ({})".format(",".join("?" for _ in IMAGE_EXTS)),
                tuple(sorted(IMAGE_EXTS)),
            ).fetchone()[0]
            vc = con.execute(
                "SELECT COUNT(*) FROM photos WHERE lower(extension) IN ({})".format(",".join("?" for _ in VIDEO_EXTS)),
                tuple(sorted(VIDEO_EXTS)),
            ).fetchone()[0]
            ac = con.execute("SELECT COUNT(*) FROM albums").fetchone()[0]
            return {"photo_count":pc,"video_count":vc,"media_count":pc+vc,"album_count":ac}
        finally: con.close()

    def _movie_payload(self, row: dict) -> dict:
        path = Path(row["file_path"])
        parsed = parse_movie_filename(path.name)
        subtitle = find_sidecar(path, {".srt", ".ass", ".ssa", ".vtt"})
        poster = find_poster(path)
        row.update(
            {
                "media_type": "video",
                "title": parsed["title"],
                "year": parsed.get("year"),
                "season": parsed.get("season"),
                "episode": parsed.get("episode"),
                "episode_label": parsed.get("episode_label"),
                "subtitle_status": "available" if subtitle else "missing",
                "subtitle_path": str(subtitle) if subtitle else None,
                "poster_status": "available" if poster else "missing",
                "poster_path": str(poster) if poster else None,
                "metadata_source": "filename_and_sidecar_local",
                "transcoding": {
                    "enabled": False,
                    "policy": "external_player_or_direct_file_link_only",
                },
            }
        )
        return row


def clean_title(value: str) -> str:
    text = re.sub(r"[._]+", " ", value)
    text = re.sub(r"\s+", " ", text).strip(" -_[]()")
    return text.title() if text else "Untitled"


def parse_movie_filename(filename: str) -> dict:
    stem = Path(filename).stem
    year = None
    year_match = re.search(r"(19\d{2}|20\d{2})", stem)
    if year_match:
        year = int(year_match.group(1))
    season = None
    episode = None
    episode_label = None
    episode_match = re.search(r"(?i)\bS(\d{1,2})E(\d{1,3})\b|(?:^|[.\s_-])(\d{1,2})x(\d{1,3})(?:$|[.\s_-])|(?:^|[.\s_-])E(\d{1,3})(?:$|[.\s_-])", stem)
    if episode_match:
        if episode_match.group(1) and episode_match.group(2):
            season = int(episode_match.group(1))
            episode = int(episode_match.group(2))
        elif episode_match.group(3) and episode_match.group(4):
            season = int(episode_match.group(3))
            episode = int(episode_match.group(4))
        elif episode_match.group(5):
            episode = int(episode_match.group(5))
        if episode is not None:
            episode_label = f"S{season:02d}E{episode:02d}" if season is not None else f"E{episode:02d}"
    cut_at = len(stem)
    for match in [year_match, episode_match]:
        if match:
            cut_at = min(cut_at, match.start())
    return {
        "title": clean_title(stem[:cut_at] if cut_at else stem),
        "year": year,
        "season": season,
        "episode": episode,
        "episode_label": episode_label,
    }


def find_sidecar(video_path: Path, extensions: set[str]) -> Path | None:
    for ext in sorted(extensions):
        candidate = video_path.with_suffix(ext)
        if candidate.exists():
            return candidate
    stem = video_path.stem.lower()
    for item in video_path.parent.iterdir() if video_path.parent.exists() else []:
        if item.is_file() and item.suffix.lower() in extensions and item.stem.lower().startswith(stem):
            return item
    return None


def find_poster(video_path: Path) -> Path | None:
    image_exts = {".jpg", ".jpeg", ".png", ".webp"}
    candidates = []
    for suffix in image_exts:
        candidates.extend(
            [
                video_path.with_suffix(suffix),
                video_path.with_name(video_path.stem + ".poster" + suffix),
                video_path.with_name("poster" + suffix),
                video_path.with_name("folder" + suffix),
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
