-- Career Scout — Supabase PostgreSQL schema
-- Run this in Supabase SQL Editor (supabase.com → SQL Editor → New Query)

CREATE TABLE IF NOT EXISTS jobs (
  id               TEXT PRIMARY KEY,
  short_id         TEXT UNIQUE,
  title            TEXT NOT NULL,
  company          TEXT NOT NULL,
  location         TEXT,
  url              TEXT,
  source_urls      TEXT,
  description      TEXT,
  source           TEXT,
  posted_date      TEXT,
  urgency          TEXT DEFAULT 'active',
  score            FLOAT8 DEFAULT -1,
  score_detail     JSONB DEFAULT '{}',
  tags_matched     JSONB DEFAULT '[]',
  status           TEXT DEFAULT 'new',
  outcome          TEXT DEFAULT 'pending',
  outcome_date     TEXT,
  rejection_reason TEXT,
  follow_up_due    TEXT,
  resume_path      TEXT,
  notes            TEXT,
  is_repost        INTEGER DEFAULT 0,
  original_job_id  TEXT,
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,
  scored_at        TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_status    ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_score     ON jobs(score);
CREATE INDEX IF NOT EXISTS idx_jobs_company   ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_urgency   ON jobs(urgency);
CREATE INDEX IF NOT EXISTS idx_jobs_outcome   ON jobs(outcome);
CREATE INDEX IF NOT EXISTS idx_jobs_short_id  ON jobs(short_id);

CREATE TABLE IF NOT EXISTS companies (
  id          SERIAL PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,
  url         TEXT,
  blacklisted INTEGER DEFAULT 0,
  active      INTEGER DEFAULT 1,
  created_at  TEXT DEFAULT to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS roles (
  id         SERIAL PRIMARY KEY,
  title      TEXT NOT NULL UNIQUE,
  active     INTEGER DEFAULT 1,
  created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS scraper_health (
  scraper       TEXT PRIMARY KEY,
  last_success  TEXT,
  last_failure  TEXT,
  failure_count INTEGER DEFAULT 0,
  last_error    TEXT
);

CREATE TABLE IF NOT EXISTS insights (
  id         SERIAL PRIMARY KEY,
  type       TEXT,
  payload    JSONB DEFAULT '{}',
  created_at TEXT DEFAULT to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS url_cache (
  url          TEXT PRIMARY KEY,
  content_hash TEXT,
  updated_at   TEXT
);

-- Disable RLS for all tables (single-user personal app)
ALTER TABLE jobs           DISABLE ROW LEVEL SECURITY;
ALTER TABLE companies      DISABLE ROW LEVEL SECURITY;
ALTER TABLE roles          DISABLE ROW LEVEL SECURITY;
ALTER TABLE scraper_health DISABLE ROW LEVEL SECURITY;
ALTER TABLE insights       DISABLE ROW LEVEL SECURITY;
ALTER TABLE url_cache      DISABLE ROW LEVEL SECURITY;
