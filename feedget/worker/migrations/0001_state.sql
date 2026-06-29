-- feedget per-device state: read-state, subscriptions, pairing.
-- Read-state is relational (one row per token+item) so concurrent devices
-- upsert their own marks instead of clobbering a shared blob. The Worker also
-- creates these lazily (CREATE TABLE IF NOT EXISTS) on first request, so this
-- migration is mainly for `wrangler d1 migrations apply` and documentation.

CREATE TABLE IF NOT EXISTS read_state (
  token   TEXT    NOT NULL,
  item_id TEXT    NOT NULL,   -- the raw item link, same key /?feeds= dedupes on
  ts      INTEGER NOT NULL,   -- epoch ms, mark time; drives LRU cap + sync cursor
  PRIMARY KEY (token, item_id)
);
CREATE INDEX IF NOT EXISTS idx_read_token_ts ON read_state (token, ts);

CREATE TABLE IF NOT EXISTS subs_state (
  token TEXT    PRIMARY KEY,
  feeds TEXT    NOT NULL,      -- JSON array of feed URLs
  ts    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pair_state (
  code       TEXT    PRIMARY KEY,
  token      TEXT    NOT NULL,
  expires_at INTEGER NOT NULL  -- epoch ms; claimed once then deleted, lazy-swept on create
);
