# Career Scout — Full Implementation Plan

## What We're Building

Two tools sharing a single SQLite database, orchestrated entirely by n8n:

```
career-scout/
├── scrapers/        ← jobspy + Playwright + BS4, all free
├── core/            ← db, scoring, urgency, dedup, expiry, signals
├── forge/           ← AI-powered resume generation (Typst + Groq)
├── insights/        ← skill gap roadmap, weekly reports, response rates
├── notify/          ← Telegram message formatters
├── n8n/workflows/   ← all n8n workflow JSONs (auto-backed up)
├── app.py           ← Streamlit dashboard
├── config.yaml
└── shared/
    ├── jobs.db
    ├── backups/     ← daily SQLite snapshots
    ├── resumes/     ← generated PDFs
    └── cache/       ← page content hashes (scrape dedup)
```

**Total running cost: $0/month.**

---

## Integration Contract — SQLite Schema

```sql
companies (
  id               TEXT PRIMARY KEY,        -- sha256(name)
  name             TEXT,
  careers_url      TEXT,
  linkedin_slug    TEXT,
  priority         INTEGER DEFAULT 1,
  active           INTEGER DEFAULT 1,
  blacklisted      INTEGER DEFAULT 0,
  jobs_this_week   INTEGER DEFAULT 0,       -- hiring signal counter
  created_at       TEXT
)

roles (
  id               TEXT PRIMARY KEY,        -- sha256(title)
  title            TEXT,
  keywords         TEXT,                    -- JSON list
  tags             TEXT,                    -- JSON list
  active           INTEGER DEFAULT 1,
  created_at       TEXT
)

jobs (
  id               TEXT PRIMARY KEY,        -- sha256(title+company+url)
  title            TEXT,
  company          TEXT,
  location         TEXT,
  url              TEXT,
  source_urls      TEXT,                    -- JSON list: same job across portals
  description      TEXT,
  source           TEXT,                    -- linkedin|indeed|naukri|internshala|careers_page
  posted_date      TEXT,
  urgency          TEXT,                    -- hot|active|aging|stale
  score            REAL,                    -- 0.0–5.0, Groq LLM
  score_detail     TEXT,                    -- JSON: {fit_summary, matched_skills, missing_skills, ...}
  tags_matched     TEXT,                    -- JSON list
  status           TEXT DEFAULT 'new',      -- new|reviewed|applied|rejected|expired
  outcome          TEXT DEFAULT 'pending',  -- pending|interview|offer|rejected|ghosted
  outcome_date     TEXT,
  rejection_reason TEXT,
  follow_up_due    TEXT,                    -- applied_date + 7 days
  resume_path      TEXT,
  notes            TEXT,
  is_repost        INTEGER DEFAULT 0,
  original_job_id  TEXT,                   -- points to original if repost
  created_at       TEXT,
  updated_at       TEXT,
  scored_at        TEXT
)

page_cache (
  url              TEXT PRIMARY KEY,
  content_hash     TEXT,
  last_scraped     TEXT
)

insights (
  id                      INTEGER PRIMARY KEY AUTOINCREMENT,
  week_start              TEXT,
  missing_skills_json     TEXT,
  rejection_count         INTEGER,
  interview_count         INTEGER,
  offer_count             INTEGER,
  response_rate_by_source TEXT,            -- JSON: {linkedin: 0.4, naukri: 0.1}
  llm_summary             TEXT,
  created_at              TEXT
)

scraper_health (
  scraper              TEXT PRIMARY KEY,   -- jobspy|playwright_naukri|playwright_careers|...
  last_success         TEXT,
  consecutive_failures INTEGER DEFAULT 0,
  last_error           TEXT
)
```

---

## Inputs

### Google Sheets (initial setup)

**Tab: Companies**
| name | careers_url | linkedin_slug | priority | active |
|------|-------------|---------------|----------|--------|
| Google | https://careers.google.com/jobs | google | 1 | TRUE |
| Flipkart | https://www.flipkartcareers.com | flipkart | 1 | TRUE |

**Tab: Roles**
| role_title | keywords | tags | active |
|------------|----------|------|--------|
| Data Scientist | data scientist,ML,machine learning | ml,python,statistics | TRUE |
| AI Engineer | AI engineer,LLM,generative AI | llm,genai,langchain | TRUE |

n8n reads both tabs on startup and every 24h → syncs to SQLite `companies` and `roles` tables.
Cross-match: every active company × every active role = search matrix.

### Telegram Bot (dynamic updates)
```
/add company <name> <careers_url> [linkedin_slug]
/add role <title> <keywords>
/blacklist <company>          → suppresses company forever
/note <id> <text>             → personal note on a job
```
All Telegram writes go to SQLite and sync back to Google Sheets.

---

## Scraping Stack (all free)

| Sites | Tool | Why |
|-------|------|-----|
| LinkedIn, Indeed, Glassdoor, ZipRecruiter | python-jobspy | Direct API wrapper, no browser, free |
| Naukri, Internshala | Playwright (headless Chromium) | JS-heavy, needs real browser |
| Company career pages (static) | requests + BS4 | Lightweight, fast |
| Company career pages (JS-heavy) | Playwright | Handles dynamic loading |

**Content hash caching:** before scraping, check `page_cache` table. If hash matches last scrape, skip. Dramatically reduces redundant scrapes.

**Cross-portal dedup:** sha256(title+company+url) catches exact duplicates. Fuzzy match on `normalize(title) + normalize(company)` (via rapidfuzz, threshold 90) catches same job on LinkedIn vs Indeed vs company page — merged into one record with multiple `source_urls`.

**Repost detection:** same normalized title+company seen again after 30+ days → `is_repost=1`, linked to original via `original_job_id`. Signals the company is struggling to fill the role.

**Urgency tiers:**
```
🔴 Hot    — posted < 24h
🟡 Active — posted 1–4 days
⚪ Aging  — posted 5–10 days
💀 Stale  — posted > 10 days → filtered from Telegram alerts, still in DB
```

---

## LLM Scoring (Groq, free tier)

**Model:** `llama3-70b-8192` via Groq API (free tier: ~14,400 req/day)
**Token budget:** ~720 tokens/job (600 input + 120 output)
**Only new/unscored jobs are sent to LLM — cached scores are reused**

### Scoring Prompt
```
You are evaluating a job posting for a fresher candidate graduating 2026.

CANDIDATE PROFILE:
- Target roles: {target_roles}
- Key skills: {skills_summary}
- Experience: {experience_summary}  (0–1 year internships)
- Locations: {locations}

JOB POSTING:
Title: {title}
Company: {company}
Location: {location}
Description: {description[:1500]}

Respond ONLY with valid JSON:
{
  "score": <float 0.0-5.0>,
  "fit_summary": "<one sentence>",
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill1"],
  "seniority_fit": true|false,
  "location_fit": true|false
}
```

**Graceful degradation:** if Groq is down → store `score=-1, status='unscored'` → retry on next run.
**Re-scoring flag:** when `master_profile.yaml` is updated → all `new/unscored` jobs get `scored_at=null` → re-scored on next scout run.

---

## n8n Workflows (9 total, all self-hosted)

### 1. `sync_sheets` — Google Sheets → SQLite
- Trigger: manual + every 24h
- Reads Companies + Roles tabs
- Upserts to `companies` and `roles` tables
- Detects removals → sets `active=0`

### 2. `scout` — Main pipeline (every 6h)
```
Build search matrix: active companies × active roles
↓
For each pair:
  jobspy_scraper.py  → LinkedIn, Indeed, Glassdoor
  playwright_scraper.py → Naukri, Internshala, JS career pages
  static_scraper.py → simple career pages
↓
Normalize → cross-portal fuzzy dedup → urgency tier → expiry check → repost check
↓
Score new jobs via Groq (skip stale, skip already scored)
↓
Write to jobs table
↓
Update scraper_health table
↓
Telegram: push jobs scored ≥ 3.5, urgency hot/active only
```

### 3. `followup` — Follow-up timer (every 6h)
```
Query jobs where status='applied' AND follow_up_due < now AND outcome='pending'
→ Telegram nudge per job:
  "Applied to Data Scientist @ Google 7 days ago — any update?
   Reply: /interview 42 | /rejected 42 | /ghosted 42"

Query jobs where status='applied' AND days_since_applied > 14 AND outcome='pending'
→ Auto-mark outcome='ghosted'
→ Telegram: "Marked {title} @ {company} as ghosted (14 days no response)"
```

### 4. `weekly_insights` — Sunday 9am
```
Aggregate week's rejections + missing_skills
→ Groq: generate insight report
→ Telegram push

Check: any missing_skill appearing 3+ times total →
  trigger gaps.py → skill gap roadmap message
  (fires once per skill, not every week)

Update response_rate_by_source in insights table
```

### 5. `telegram_bot` — Webhook, always-on
```
/jobs              → top 5 new today, sorted by score
/job <id>          → full JD + fit summary + matched/missing skills
/apply <id>        → status=applied, follow_up_due=now+7d, outcome=pending
/interview <id>    → outcome=interview
/offer <id>        → outcome=offer
/rejected <id> [reason] → outcome=rejected, rejection_reason=text
/ghosted <id>      → outcome=ghosted
/add company ...   → insert to DB + append to Google Sheet
/add role ...      → insert to DB + append to Google Sheet
/blacklist <name>  → companies.blacklisted=1
/note <id> <text>  → append to jobs.notes
/resume <id>       → Execute Command: python forge/forge.py --job-id <id>
/stats             → this week: found/applied/interview/offer/ghosted
/scout             → trigger immediate scout run
/digest            → show today's digest on demand
```

### 6. `gmail_monitor` — every 30min
```
n8n Gmail node (OAuth) — search subject/body for:
  company names from applied jobs + keywords: "unfortunately", "move forward",
  "pleased to", "interview", "offer", "regret", "not selected"

On match:
  Extract company → look up applied job in DB
  Telegram: "📧 Email detected from Google — rejection? /rejected 42 | /ignore"
  User confirms → DB updated

Draft detection: "interview" / "pleased" → suggest /interview <id>
```

### 7. `morning_digest` — 8am daily
```
Query: new jobs added since yesterday, scored ≥ 3.5, urgency hot/active
→ Telegram:
  "☀️ Good morning — 4 new matches since yesterday
   🔴 Data Scientist @ Flipkart (4.8★) — 3h ago
   🟡 AI Engineer @ Microsoft (4.4★) — 18h ago
   Reply /jobs for full list"
```

### 8. `db_backup` — 2am daily
```
Execute Command: python -c "import shutil,datetime; shutil.copy('shared/jobs.db',
  f'shared/backups/jobs_{datetime.date.today()}.db')"
Keep last 30 days, delete older
```

### 9. `workflow_backup` — on n8n workflow save
```
n8n Export Workflow node → save JSON to n8n/workflows/{workflow_name}.json
Keeps workflows in git repo — recoverable if n8n DB breaks
```

---

## Resume Forge

**Stack:** Python + Groq (llama3-70b) + Typst
**Install:** `winget install Typst.Typst` (single binary, free)
**Cost:** $0

### File Structure
```
forge/
├── master_profile.yaml    ← all content, every bullet tagged
├── profiles/
│   ├── data_scientist.yaml
│   ├── bi_developer.yaml
│   └── default.yaml
├── templates/
│   └── resume.typ         ← single Typst template, all profiles share it
├── matcher.py             ← tags_matched → auto-select profile
├── optimizer.py           ← Groq ATS optimization pass
└── forge.py               ← CLI entrypoint
```

### ATS Optimization Flow
```
1. Load job from DB (title, company, description, tags_matched, score_detail)
2. Load master_profile.yaml
3. Groq call (llama3-70b):
   Input:  JD + full candidate profile
   Output: {
     "ats_keywords": [...],          ← exact keywords from JD
     "summary": "2-line tailored summary",
     "skills_order": [...],          ← reordered by JD relevance
     "selected_bullets": {...},      ← indices per experience/project
     "rewritten_bullets": {...},     ← light rewrites to surface JD keywords
     "ats_score_estimate": 84
   }
   Rules enforced in prompt:
     - Use exact JD keywords verbatim (ATS matches literally)
     - Only select bullets that exist in master_profile.yaml (no hallucination)
     - Rewrites only surface keywords already implied in the bullet
     - Single-page constraint: drop lowest-relevance items if overflow
     - Never claim a skill the candidate doesn't have

4. Render: fill resume.typ with AI-selected content
5. Compile: typst compile resume.typ → PDF
6. Save to shared/resumes/{company}_{role}_{date}.pdf
7. Write resume_path back to DB
```

### Telegram Response
```
✅ Resume generated — Data Scientist @ Google

ATS Score estimate: 84%
✅ Matched: Python, feature engineering, A/B testing, SQL, scikit-learn
❌ Missing from profile: MLOps, Kubeflow

PDF: shared/resumes/google_ds_2026-05-14.pdf
```

Missing keywords are saved to the job record and feed weekly insights.

---

## Insights & Intelligence

### Skill Gap Roadmap
Triggered when any skill appears as `missing` in 3+ rejections (fires once per skill):
```
🎯 Skill Gap Alert: PyTorch flagged in 4 rejections

Fastest free path:
  → fast.ai Practical Deep Learning (free, 7 weeks)
  → Build a small image classifier project on GitHub
  → Estimated resume score impact: +0.6 on ML Engineer roles
```

### Weekly Report (every Sunday)
```
📊 Week of May 11–17

Jobs found:     23  |  Scored ≥ 3.5: 11
Applied:         4  |  Interviews: 1  |  Offers: 0  |  Ghosted: 2

Common missing skills this week:
  PyTorch (3×), Azure ML (2×), dbt (1×)

Best source:    LinkedIn (3 responses from 4 applied, 75%)
Worst source:   Naukri (0 responses from 8 applied, 0%)

💡 Suggestion: Focus LinkedIn applications this week.
   Consider a small PyTorch project before applying to ML Engineer roles.
```

### Company Hiring Signal
`jobs_this_week` counter on `companies` table — increments on each new job found. If a company posts 5+ jobs in one week → Telegram alert:
```
📈 Hiring signal: Swiggy posted 6 Data roles this week — they're actively hiring.
```

---

## Streamlit Dashboard (`app.py`)

### Tab: Pipeline
- Table: all jobs filterable by status, urgency, score, source, role, company
- Click row → full JD + fit summary + matched/missing skills
- Inline status change (new → reviewed → applied → rejected)
- Color-coded urgency badges

### Tab: Scout
- "Run Scout Now" button → triggers n8n scout webhook
- Last run summary: X companies checked, Y new jobs, Z scored ≥ 3.5
- Scraper health status table (green/red per scraper)
- Next scheduled run countdown

### Tab: Insights
- Application funnel chart: found → applied → interview → offer
- Missing skills frequency bar chart (last 30 days)
- Score distribution histogram
- Response rate by source
- Weekly trend: jobs found over time

### Tab: Companies & Roles
- View/toggle active companies and roles without touching Google Sheets
- Add new company/role inline (syncs back to Sheet)
- Blacklist toggle per company
- Hiring signal column (jobs posted this week)

### Tab: Resumes
- Table: all generated resumes (job title, company, date, ATS score estimate, profile used)
- Open PDF button
- Regenerate button → re-runs forge.py for latest profile version

---

## Technology Stack

```
# Scraping (all free)
python-jobspy          # LinkedIn, Indeed, Glassdoor, ZipRecruiter
playwright             # Naukri, Internshala, JS-heavy career pages
beautifulsoup4         # static HTML parsing
requests               # HTTP client
rapidfuzz              # fuzzy string matching (cross-portal dedup)

# LLM (free tier)
groq                   # llama3-70b: scoring + resume ATS + insights

# Storage
sqlite3                # stdlib, no install needed

# Dashboard
streamlit

# Resume
# typst via: winget install Typst.Typst
pyyaml                 # master_profile + config parsing

# Utilities
python-dotenv          # env vars
```

**External setup (all free):**
- n8n: `npm install -g n8n` → `n8n start` → localhost:5678
- Typst: `winget install Typst.Typst`
- Playwright Chromium: `playwright install chromium`
- Groq API key: console.groq.com → free tier
- Telegram bot: @BotFather → /newbot (2 min)
- Gmail OAuth: configured inside n8n (built-in Google node)
- Google Sheets OAuth: configured inside n8n (built-in Google Sheets node)

**Env vars (never in config.yaml):**
```
GROQ_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

---

## config.yaml

```yaml
target_roles:
  - "Data Scientist"
  - "AI Engineer"
  - "BI Developer"
  - "Data Analyst"
  - "Machine Learning Engineer"

locations:
  - "Hyderabad"
  - "Remote"
  - "Bangalore"

experience_years: [0, 3]
min_score: 3.5
hours_old: 72

schedule:
  scout_interval_hours: 6
  digest_time: "08:00"

llm:
  provider: groq
  model: llama3-70b-8192

scraping:
  request_delay_seconds: 2
  max_retries: 3
  health_alert_threshold: 3     # consecutive failures → Telegram alert

urgency:
  hot_hours: 24
  active_hours: 96
  aging_hours: 240               # beyond aging = stale

skill_gap:
  trigger_count: 3               # rejections before roadmap fires

follow_up:
  nudge_days: 7
  ghost_days: 14

scoring:
  min_score_alert: 3.5

repost:
  window_days: 30

paths:
  db: "shared/jobs.db"
  backups: "shared/backups/"
  resumes: "shared/resumes/"
  cache: "shared/cache/"
  workflows: "n8n/workflows/"

sheets:
  spreadsheet_id: ""            # fill after creating Google Sheet
  companies_tab: "Companies"
  roles_tab: "Roles"
```

---

## Phase Plan

### Phase 0 — Infrastructure Setup
**Goal:** every tool installed, connected, and verified before writing any feature code.

Tasks:
1. Install n8n: `npm install -g n8n` → `n8n start` → verify at localhost:5678
2. Create Google Sheet with Companies + Roles tabs, add 5 sample rows each
3. Connect n8n Google Sheets OAuth → test read
4. Create Telegram bot via @BotFather → set env vars → test n8n Telegram node
5. Create Groq account → get API key → set env var → test one API call
6. Connect Gmail OAuth in n8n → test search node
7. Install Python deps: `pip install python-jobspy playwright beautifulsoup4 requests rapidfuzz groq streamlit pyyaml python-dotenv`
8. Install Playwright Chromium: `playwright install chromium`
9. Install Typst: `winget install Typst.Typst`
10. Create all directories + config.yaml + SQLite schema (all tables)

**Success criteria:**
- `python -c "import jobspy, playwright, groq, streamlit"` — no errors
- `typst --version` — prints version
- n8n at localhost:5678 with Google Sheets + Telegram + Gmail nodes connected
- `python -c "import sqlite3; sqlite3.connect('shared/jobs.db')"` — creates DB

---

### Phase 1 — Scout Pipeline
**Goal:** jobs flowing into DB from real portals, scored, deduplicated, Telegram alerts firing.

Tasks:
1. `core/db.py` — schema init, upsert jobs, read by status/score, update scraper_health
2. `scrapers/jobspy_scraper.py` — wrap python-jobspy, normalize output, company+role filter
3. `scrapers/playwright_scraper.py` — Naukri search + Internshala + JS career pages, content hash cache
4. `scrapers/static_scraper.py` — requests+BS4 for simple career pages, content hash cache
5. `scrapers/dedup.py` — sha256 exact dedup + rapidfuzz cross-portal merge + repost detection
6. `core/urgency.py` — posted_date → hot/active/aging/stale tier
7. `core/scorer.py` — Groq prompt builder + JSON response parser + graceful degradation
8. `core/llm.py` — Groq client with retry + error handling
9. n8n `sync_sheets` workflow — Google Sheets → SQLite companies + roles
10. n8n `scout` workflow — full pipeline every 6h, calls Python scripts via Execute Command
11. n8n `morning_digest` workflow — 8am daily Telegram digest
12. n8n `db_backup` workflow — 2am daily SQLite backup
13. n8n `workflow_backup` — export workflow JSONs to n8n/workflows/
14. Scraper health monitoring in scout workflow → Telegram alert on 3 consecutive failures

**Success criteria:**
- `scout` workflow runs without error
- Telegram receives new job alerts with score, urgency, matched/missing skills
- Running scout twice in a row adds 0 duplicates
- Same job found on LinkedIn + Indeed → merged to 1 record with 2 source_urls
- Repost of a job from 31 days ago → is_repost=1
- If Groq is down → jobs stored with score=-1, no crash
- Morning digest arrives at 8am
- Scraper failure → Telegram alert within one run

---

### Phase 2 — Follow-up, Insights & Gmail
**Goal:** full lifecycle tracking from application → outcome + weekly intelligence.

Tasks:
1. n8n `followup` workflow — 7-day nudge + 14-day auto-ghosting
2. n8n `telegram_bot` workflow — all commands: /apply, /interview, /offer, /rejected, /ghosted, /note, /blacklist, /add company, /add role, /stats, /scout, /resume
3. `insights/weekly.py` — aggregate rejections + missing skills → Groq report builder
4. `insights/gaps.py` — skill gap roadmap trigger (3+ rejections) + free resource links
5. `insights/signals.py` — company hiring signal counter, response rate by source
6. n8n `weekly_insights` workflow — Sunday 9am, calls weekly.py + gaps.py
7. n8n `gmail_monitor` workflow — 30min poll, match against applied companies, Telegram prompt
8. Re-scoring logic in `core/scorer.py` — detect master_profile.yaml change → flag for re-score

**Success criteria:**
- `/apply 42` sets status=applied, follow_up_due=now+7d
- 7 days later → Telegram nudge for that job
- 14 days with no update → auto-ghosted
- Sunday → weekly report pushed to Telegram with skill gaps + source performance
- Skill appearing missing 3+ times → roadmap message fires once
- Rejection email from Google in Gmail → Telegram prompt within 30min

---

### Phase 3 — Resume Forge
**Goal:** one Telegram command generates a tailored, ATS-optimized single-page PDF.

Tasks:
1. `forge/master_profile.yaml` — full profile (personal, education, skills, experience, projects, certifications), every bullet tagged
2. `forge/profiles/data_scientist.yaml` — summary, skills_order, experience_tags, projects, bullets_max
3. `forge/profiles/bi_developer.yaml` — same structure, BI-focused
4. `forge/profiles/default.yaml` — balanced fallback
5. `forge/templates/resume.typ` — single Typst template, clean single-page layout, all profiles share it
6. `forge/matcher.py` — job tags_matched → auto-select best profile
7. `forge/optimizer.py` — Groq ATS optimization: keyword extraction, bullet selection/rewriting, skills reordering
8. `forge/forge.py` — CLI: reads job from DB → matcher → optimizer → render → typst compile → save PDF → write resume_path to DB
9. `/resume <id>` in telegram_bot workflow → n8n Execute Command → forge.py → Telegram reply with ATS score + PDF path

**Success criteria:**
- `python forge/forge.py --job-id <id>` produces a PDF in shared/resumes/
- PDF is exactly 1 page
- DS job → picks data_scientist profile; BI job → picks bi_developer profile
- Telegram shows ATS score estimate + matched/missing keywords
- Missing keywords written to job record in DB

---

### Phase 4 — Streamlit Dashboard
**Goal:** full desktop view of the pipeline, insights, and resumes.

Tasks:
1. `app.py` Pipeline tab — job table, status filters, urgency badges, inline status change, full JD modal
2. `app.py` Scout tab — Run Now button (hits n8n webhook), scraper health table, last/next run info
3. `app.py` Insights tab — funnel chart, missing skills bar chart, score histogram, response rate by source, weekly trend
4. `app.py` Companies & Roles tab — add/toggle/blacklist companies + roles, hiring signal column, Sheet sync status
5. `app.py` Resumes tab — generated resume table, open PDF, regenerate button

**Success criteria:**
- `streamlit run app.py` opens without errors
- Can change job status from UI → reflected in DB immediately
- "Run Scout Now" triggers n8n scout workflow and shows confirmation
- Resumes tab shows all PDFs with open button functional

---

### Phase 5 — Later (after system is stable)
- **Cover letter generation** — one more Groq call using same JD + profile context, Typst template, `/coverletter <id>` Telegram command
- **Interview prep mode** — `/interview <id>` triggers Groq to generate 7–10 likely questions based on JD + submitted resume, pushed to Telegram as prep sheet

---

## Build Order

```
Week 1:  Phase 0 (infrastructure) + Phase 1 (scout pipeline live)
Week 2:  Phase 2 (follow-up, insights, Gmail)
Week 3:  Phase 3 (resume forge)
Week 4:  Phase 4 (Streamlit dashboard)
Phase 5: After system has 2–3 weeks of real data
```

---

## Scope Guard — What We Will NOT Build

- No auto-apply (apply button is always manual)
- No login-based scraping (no LinkedIn/Naukri authenticated sessions)
- No cloud deployment (runs local only)
- No REST API between components (SQLite is the only interface)
- No email sending (Telegram only for notifications)
- No proxy rotation (randomized user-agent + delays is sufficient for target scale)
