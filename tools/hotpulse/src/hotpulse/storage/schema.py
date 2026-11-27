"""SQLite schema。MVP 使用单库、WAL、按主题的追加快照。"""

SCHEMA_VERSION = 1

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    status TEXT NOT NULL,
    item_count INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    source TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_platform_id ON runs(platform, id DESC);
CREATE INDEX IF NOT EXISTS idx_runs_finished ON runs(finished_at DESC);

CREATE TABLE IF NOT EXISTS topics (
    platform TEXT NOT NULL,
    external_id TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    author TEXT,
    summary TEXT,
    category TEXT,
    published_at TEXT,
    fingerprint TEXT NOT NULL,
    PRIMARY KEY (platform, external_id)
);
CREATE INDEX IF NOT EXISTS idx_topics_last_seen ON topics(last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_topics_fingerprint ON topics(fingerprint);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    external_id TEXT NOT NULL,
    run_id INTEGER,
    observed_at TEXT NOT NULL,
    rank INTEGER NOT NULL,
    hot_value REAL,
    score REAL NOT NULL DEFAULT 0,
    trend TEXT NOT NULL DEFAULT 'new',
    category TEXT NOT NULL DEFAULT 'other',
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_topic ON snapshots(platform, external_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_observed ON snapshots(observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_platform_observed ON snapshots(platform, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_score ON snapshots(score DESC);

CREATE TABLE IF NOT EXISTS clusters (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    score REAL NOT NULL,
    item_count INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cluster_members (
    cluster_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    score REAL NOT NULL,
    PRIMARY KEY (cluster_id, platform, external_id),
    FOREIGN KEY (cluster_id) REFERENCES clusters(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_cluster_members_topic ON cluster_members(platform, external_id);
"""
