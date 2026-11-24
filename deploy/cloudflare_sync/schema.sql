-- InuYasha Hybrid Sync Hub — Cloudflare D1 Schema (SQLite)
-- Free-tier safe: 4 lightweight tables, Guilds stay 100% local (not synced).

CREATE TABLE IF NOT EXISTS accounts (
  account_id TEXT PRIMARY KEY,
  username TEXT NOT NULL,
  username_lower TEXT NOT NULL UNIQUE,
  password_salt TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  player_id TEXT NOT NULL UNIQUE,
  banned INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  device_id TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL,
  last_seen_at INTEGER NOT NULL,
  FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_account ON sessions(account_id);

CREATE TABLE IF NOT EXISTS player_saves (
  account_id TEXT PRIMARY KEY,
  player_id TEXT NOT NULL UNIQUE,
  sync_rev INTEGER NOT NULL DEFAULT 0,
  device_id TEXT NOT NULL DEFAULT '',
  save_hash TEXT NOT NULL DEFAULT '',
  save_gzip_b64 TEXT NOT NULL DEFAULT '',
  snapshot_json TEXT NOT NULL DEFAULT '{}',
  name TEXT NOT NULL DEFAULT '',
  lv INTEGER NOT NULL DEFAULT 1,
  fap INTEGER NOT NULL DEFAULT 0,
  arena_score INTEGER NOT NULL DEFAULT 1000,
  updated_at INTEGER NOT NULL,
  FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_player_saves_updated ON player_saves(updated_at);

CREATE TABLE IF NOT EXISTS social_inbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  to_player_id TEXT NOT NULL,
  from_player_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at INTEGER NOT NULL,
  consumed INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_social_inbox_to ON social_inbox(to_player_id, consumed, id);
