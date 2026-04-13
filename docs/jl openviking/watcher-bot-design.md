# Regulatory Headline Watcher Bot

Design for a standalone bot that continuously watches regulatory sources,
determines relevance, and ingests into NaturalSentinel + OpenViking.

Lives **outside** NaturalSentinel as a separate process.

---

## Why External

NaturalSentinel is **pull-based** -- you trigger a scan, it fetches filings,
analyzes them. What we need is **push-based** -- a process that:

1. Continuously watches sources for new content
2. Makes a fast relevance decision (cheap/fast)
3. If relevant, ingests into NaturalSentinel (expensive/slow)

That's a separate lifecycle -- it runs 24/7, NaturalSentinel doesn't need to.

---

## Architecture

```
┌──────────────────────────────────────────┐
│            sentinel-watcher              │
│         (standalone Python bot)          │
│                                          │
│  ┌─────────┐  ┌──────────┐  ┌────────┐  │
│  │ Pollers │  │ Relevance│  │Dispatch│  │
│  │ (feeds) │→ │  Filter  │→ │  to NS │  │
│  └─────────┘  └──────────┘  └────────┘  │
│                                          │
│  Pollers:                                │
│  - RSS feeds (Federal Register, CISA)    │
│  - API polls (EDGAR, CFPB, Congress)     │
│  - Web scrape watches (FINRA, BIS)       │
│  - Twitter/X (agency accounts)           │
│  - Email/newsletter parsers              │
│                                          │
│  Relevance Filter:                       │
│  - Keyword matching (fast, free)         │
│  - Haiku classification (cheap LLM)      │
│  - Dedup against seen IDs                │
│                                          │
│  Dispatch:                               │
│  - POST to NS /filings/analyze           │
│  - POST to NS /openviking/add            │
│  - Webhook/Slack notification            │
└──────────────────────────────────────────┘
```

---

## How It Works

### Step 1 -- Poll sources on schedule

| Source | Method | Cadence |
|--------|--------|---------|
| Federal Register | RSS Atom feed | Every 30 min |
| SEC EDGAR | RSS feed | Every 30 min |
| CISA KEV | JSON feed | Every 6 hours |
| OFAC SDN | Bulk hash check | Daily |
| FINRA | HTML scrape | Every 4 hours |
| Fed speeches | JSON listing | Hourly |
| Agency Twitter/X | API or RSS bridge | Real-time |

### Step 2 -- Fast relevance filter (two-stage)

**Stage A -- Keyword gate** (free, instant):
Check title + summary against a keyword list (e.g., "proposed rule",
"enforcement", "capital requirement", "margin", "disclosure").
If no keyword match, skip.

**Stage B -- Haiku classification** (cheap, ~$0.001/call):
Send the title + first 500 chars to Claude Haiku:

```
Is this regulatory document relevant to financial services,
capital markets, consumer lending, or cybersecurity compliance?
Reply YES or NO with a one-sentence reason.
```

Costs basically nothing and catches what keywords miss.

### Step 3 -- Dispatch to NaturalSentinel

If relevant:
- `POST /api/v1/openviking/add` -- push source URL into OpenViking for
  full ingestion + L0/L1/L2 processing
- `POST /api/v1/filings/analyze` -- trigger full impact analysis
- Send Slack/Discord/email notification with headline + severity

---

## Tech Stack

Keep it minimal:

```
sentinel-watcher/
├── watcher/
│   ├── pollers/           # One module per source type
│   │   ├── rss.py         # Generic RSS/Atom poller
│   │   ├── json_feed.py   # JSON API poller
│   │   └── scraper.py     # HTML scrape poller
│   ├── filters/
│   │   ├── keywords.py    # Fast keyword gate
│   │   └── llm_classify.py # Haiku relevance check
│   ├── dispatch/
│   │   ├── naturalsentinel.py  # POST to NS API
│   │   ├── slack.py            # Slack webhook
│   │   └── openviking.py       # Direct OV ingest
│   ├── config.py          # Source definitions, schedules, keywords
│   ├── state.py           # SQLite for seen_ids + last_poll timestamps
│   └── main.py            # Scheduler loop
├── pyproject.toml
├── Dockerfile
└── compose.yml            # or add to NS compose as a service
```

**Dependencies**: `httpx`, `feedparser`, `anthropic` (for Haiku),
`apscheduler` or just `asyncio` + `sleep`. That's it.

---

## Alternative: Claude Code Hook (lighter weight)

Instead of a standalone service, a Claude Code session-start hook could:

1. Check RSS feeds on session start
2. Summarize what's new since last check
3. Ask if any should be ingested

Good for personal use. For real 24/7 monitoring, use the standalone bot.
