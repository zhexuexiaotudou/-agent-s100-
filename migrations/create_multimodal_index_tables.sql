CREATE TABLE IF NOT EXISTS multimodal_items(
  item_id TEXT PRIMARY KEY,
  basename TEXT NOT NULL,
  extension TEXT NOT NULL,
  media_type TEXT NOT NULL,
  relative_path_hash TEXT NOT NULL,
  raw_path_exported INTEGER NOT NULL DEFAULT 0,
  raw_content_stored INTEGER NOT NULL DEFAULT 0
);
