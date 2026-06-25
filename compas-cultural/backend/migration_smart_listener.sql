-- Smart Listener: tables for content change detection, scraping state, and config storage

-- Config key-value store (for Meta token persistence)
CREATE TABLE IF NOT EXISTS config_kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    expires_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Scraping state per lugar (for smart scheduling & change detection)
CREATE TABLE IF NOT EXISTS scraping_state (
    lugar_id UUID PRIMARY KEY REFERENCES lugares(id) ON DELETE CASCADE,
    content_hash TEXT,
    last_scraped_at TIMESTAMPTZ DEFAULT NOW(),
    events_found INTEGER DEFAULT 0,
    consecutive_empty INTEGER DEFAULT 0,
    rss_feed_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for priority-based queries
CREATE INDEX IF NOT EXISTS idx_scraping_state_priority 
ON scraping_state (consecutive_empty, events_found);

CREATE INDEX IF NOT EXISTS idx_scraping_state_last_scraped 
ON scraping_state (last_scraped_at);
