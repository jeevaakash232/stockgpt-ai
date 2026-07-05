# StockGPT AI — Full Implementation Document

**Version:** 2.0  
**Date:** July 2026  
**Live URL:** https://stockgpt-ai1.netlify.app  
**Backend:** https://stockgpt-ai.onrender.com  
**Repository:** https://github.com/jeevaakash232/stockgpt-ai

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Technology Stack](#2-technology-stack)
3. [Project Structure](#3-project-structure)
4. [Backend Architecture](#4-backend-architecture)
5. [API Reference](#5-api-reference)
6. [Frontend Architecture](#6-frontend-architecture)
7. [Data Sources](#7-data-sources)
8. [Database Design](#8-database-design)
9. [Caching Strategy](#9-caching-strategy)
10. [Refresh & Smart Polling](#10-refresh--smart-polling)
11. [Deployment](#11-deployment)
12. [Environment Variables](#12-environment-variables)
13. [Feature Summary by Phase](#13-feature-summary-by-phase)
14. [Known Limitations](#14-known-limitations)
15. [Roadmap](#15-roadmap)

---

## 1. Project Overview

StockGPT AI is a live Indian stock market dashboard that combines:

- **Real-time NSE F&O data** — 209 stocks, all F&O-eligible equities
- **Angel One SmartAPI** — live LTP, option chain OI, Max Pain
- **Yahoo Finance** — indices (NIFTY, BANKNIFTY, SENSEX, VIX), top movers
- **Groq AI (llama-4-scout)** — natural language stock analysis
- **SQLite database** — daily snapshots + intraday ticks, historical downloads
- **Professional dark dashboard** — tab-based layout, sortable tables, TradingView charts

---

## 2. Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, CSS3, Bootstrap 5.3, Vanilla JavaScript |
| Backend | Python 3.11, FastAPI 0.135 |
| AI | Groq API (llama-4-scout-17b-16e-instruct) |
| Market Data (primary) | Angel One SmartAPI |
| Market Data (secondary) | Yahoo Finance (yfinance) |
| Database | SQLite (built-in Python sqlite3) |
| Excel Export | openpyxl 3.1 |
| Cache | In-memory TTL cache (custom, threading.RLock) |
| Deployment | Render (backend) + Netlify (frontend) |

---

## 3. Project Structure

```
StockGPT/
├── .gitignore
├── README.md
├── IMPLEMENTATION.md         ← this file
├── DEPLOY.md                 ← deployment guide
│
├── backend/
│   ├── Procfile              ← Render start command
│   ├── runtime.txt           ← Python 3.11.9
│   ├── render.yaml           ← Render config
│   ├── requirements_stockgpt.txt
│   ├── run.py                ← local dev entry point
│   ├── watchlist.db          ← SQLite watchlist (gitignored)
│   ├── stockgpt.db           ← SQLite history (gitignored)
│   ├── data/
│   │   ├── instrument_master.json    ← Angel One token map (daily refresh)
│   │   └── instrument_master_date.txt
│   ├── app/
│   │   ├── main.py           ← FastAPI app, CORS, router registration
│   │   ├── api/
│   │   │   ├── chat.py       ← POST /api/chat
│   │   │   ├── dashboard.py  ← GET /api/dashboard, /top-gainers, /top-losers, /most-active, /indices
│   │   │   ├── export.py     ← GET /api/export/excel, /api/export/csv
│   │   │   ├── history.py    ← GET /api/history/*
│   │   │   ├── market.py     ← GET /api/market
│   │   │   ├── option_chain.py ← GET /api/option-chain/{symbol}
│   │   │   ├── pcr.py        ← GET /api/pcr
│   │   │   ├── stock.py      ← GET /api/stock/{symbol}, /api/search
│   │   │   └── watchlist.py  ← GET/POST/DELETE /api/watchlist
│   │   ├── services/
│   │   │   ├── ai_service.py         ← Groq API wrapper
│   │   │   ├── angel_service.py      ← Angel One SmartAPI (live quotes, option chain)
│   │   │   ├── cache_service.py      ← In-memory TTL cache + market_ttl()
│   │   │   ├── history_service.py    ← SQLite historical data
│   │   │   ├── market_data.py        ← 209-stock data, LTP batch fetch, delta tracking
│   │   │   ├── market_service.py     ← Dashboard aggregator
│   │   │   ├── nse_service.py        ← NSE option chain (Angel → nsepython → fallback)
│   │   │   ├── pcr_service.py        ← PCR calculation + signal logic
│   │   │   ├── watchlist_service.py  ← SQLite watchlist CRUD
│   │   │   └── yahoo_service.py      ← Yahoo Finance (indices, movers, quotes)
│   │   ├── utils/
│   │   │   └── calculator.py
│   │   └── models/
│   │       └── stock.py
│
└── frontend/
    ├── netlify.toml          ← Netlify config
    ├── index.html            ← Single-page application
    ├── assests/
    │   └── logo.png
    ├── css/
    │   └── style.css         ← Full dark theme stylesheet
    └── js/
        ├── api.js            ← Base URL + apiFetch() + auto-detect env
        ├── app.js            ← Tab system, scroll-spy, mobile sidebar, keep-alive
        ├── chat.js           ← AI chat UI (markdown, typing indicator)
        ├── dashboard.js      ← Dashboard data + smart refresh (15s/60s)
        ├── export.js         ← Excel/CSV download
        ├── history.js        ← Historical data tab
        ├── market.js         ← PCR/Markets table + analyzeStock()
        ├── search.js         ← Navbar autocomplete search
        └── stock_detail.js   ← Stock detail modal + TradingView chart + option chain
```

---

## 4. Backend Architecture

### Request Flow

```
Browser → Netlify CDN
         → frontend/js/api.js (apiFetch)
         → Render backend (FastAPI)
              → Cache check (cache_service)
                   HIT → return cached data
                   MISS → fetch from Angel One / Yahoo Finance / Groq
                        → save to cache
                        → (background) save to SQLite
              → return JSON
```

### Service Layer

| Service | Responsibility |
|---------|---------------|
| `angel_service.py` | Angel One session management, live LTP batch (50 tokens/call), option chain from instrument master |
| `yahoo_service.py` | Indices, top movers (gainers/losers/most active) for 50 liquid stocks |
| `market_data.py` | Orchestrates 209-stock LTP fetch, computes PCR deltas, triggers DB saves |
| `nse_service.py` | Option chain with 3-tier fallback: Angel One → nsepython → sample data |
| `market_service.py` | Assembles full dashboard payload |
| `ai_service.py` | Groq API with dynamic context (market data + stock detail + indices) |
| `cache_service.py` | Thread-safe RLock cache, `market_ttl()` (15s/60s), background refresh |
| `history_service.py` | SQLite reads/writes, daily snapshot, intraday ticks, pruning |
| `watchlist_service.py` | SQLite watchlist CRUD |
| `pcr_service.py` | PCR = Put OI / Call OI; signal thresholds |

---

## 5. API Reference

### Core Endpoints

| Method | Path | Description | Cache TTL |
|--------|------|-------------|-----------|
| GET | `/` | Health check | — |
| GET | `/api/market` | 209 stocks: LTP, PCR, signal, delta metrics | 15s/60s |
| GET | `/api/pcr` | PCR table (reshaped from /market) | 15s/60s |
| GET | `/api/indices` | NIFTY, BANKNIFTY, SENSEX, India VIX | 15s/60s |

### Dashboard

| Method | Path | Description | Cache TTL |
|--------|------|-------------|-----------|
| GET | `/api/dashboard` | Full payload: overview + movers + indices + watchlist | 15s/60s |
| GET | `/api/top-gainers?limit=25` | Top gaining stocks (1–50) | 15s/60s |
| GET | `/api/top-losers?limit=25` | Top losing stocks | 15s/60s |
| GET | `/api/most-active?limit=25` | Most active by volume | 15s/60s |

### Stock Detail

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stock/{symbol}` | OHLCV + PCR + OI + support/resistance/pivot |
| GET | `/api/search?q={query}` | Symbol autocomplete (up to 10 results) |
| GET | `/api/option-chain/{symbol}` | Per-strike Call/Put OI, PCR, Max Pain |

### Watchlist

| Method | Path | Body | Description |
|--------|------|------|-------------|
| GET | `/api/watchlist` | — | Get all symbols with live prices |
| POST | `/api/watchlist` | `{"symbol":"RELIANCE"}` | Add symbol |
| DELETE | `/api/watchlist/{symbol}` | — | Remove symbol |

### AI Chat

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/api/chat` | `{"question":"...","symbol":"NIFTY"}` | Ask StockGPT AI |

### Export

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/export/excel` | Download 7-sheet Excel (all stocks + history) |
| GET | `/api/export/csv` | Download CSV of all 209 stocks |

### History

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/history/stats` | DB row counts, size, trading days |
| GET | `/api/history/dates` | All available trading dates (newest first) |
| GET | `/api/history/{symbol}?days=30` | Daily snapshots for a symbol |
| GET | `/api/history/{symbol}/intraday?date=YYYY-MM-DD` | Intraday ticks |
| GET | `/api/history/snapshot/{date}` | All symbols for a specific date |
| GET | `/api/history/download/{date}` | Download Excel for a historical date |

### Response Schema — `/api/market`

```json
[
  {
    "symbol":          "NIFTY",
    "ltp":             24270.85,
    "call_oi":         5500000,
    "put_oi":          6200000,
    "max_pain":        24000,
    "pcr":             1.13,
    "signal":          "Bullish",
    "prev_pcr":        1.11,
    "prev_call_oi":    5450000,
    "prev_put_oi":     6180000,
    "prev_ltp":        24175.7,
    "pcr_change":      0.02,
    "call_oi_chg_pct": 1,
    "put_oi_chg_pct":  0,
    "price_chg_pct":   0.4
  }
]
```

---

## 6. Frontend Architecture

### Tab System

The UI is a single-page application with 5 tabs:

| Tab | ID | Content |
|-----|----|---------|
| Dashboard | `tab-dashboard` | Summary cards, index cards, Gainers/Losers/Most Active |
| Markets | `tab-markets` | 209-stock filterable + sortable table |
| Watchlist | `tab-watchlist` | Saved stocks with live prices + add input |
| PCR Table | `tab-pcr` | Enhanced option chain: 11 columns, sortable, tooltips |
| History | `tab-history` | Date selector, snapshots, per-symbol 30d history, Excel download |
| AI Chat | `tab-chat` | ChatGPT-style AI with markdown rendering |

### PCR Table Columns (11)

`Symbol | LTP ₹ | PCR | Δ PCR | Call OI | Put OI | Call OI Δ% | Put OI Δ% | Price Δ% | Signal | Max Pain | Detail`

### Smart Refresh

```javascript
// Market hours (Mon–Fri 9:15–15:30 IST)
REFRESH_MARKET_HOURS = 15_000   // 15 seconds

// After hours / weekends
REFRESH_AFTER_HOURS  = 60_000   // 60 seconds
```

Navbar badge shows: `● LIVE 15s` (green) or `○ After Hours 60s` (grey)

### JS Module Responsibilities

| File | Responsibility |
|------|---------------|
| `api.js` | `apiFetch()`, auto-detect localhost vs Render URL, 2-min timeout |
| `dashboard.js` | Dashboard data, smart refresh, mover tables, wake-up detection |
| `market.js` | PCR/Markets table, `analyzeStock()` |
| `chat.js` | Chat UI, markdown via marked.js, typing indicator |
| `search.js` | Navbar autocomplete dropdown |
| `stock_detail.js` | Bootstrap modal, TradingView chart, option chain table |
| `export.js` | Excel + CSV download with loading state |
| `history.js` | History tab: date selector, snapshots, symbol history, download |
| `app.js` | Tab switching, sidebar scroll-spy, hamburger, keep-alive ping |

---

## 7. Data Sources

| Data | Source | Frequency | Notes |
|------|--------|-----------|-------|
| NIFTY / BANKNIFTY / SENSEX / VIX | Yahoo Finance | 15s/60s | ~15 min delayed on free tier |
| 209 stock LTPs | Angel One SmartAPI | 15s/60s | Real-time during market hours |
| Top Gainers / Losers / Most Active | Yahoo Finance | 15s/60s | 50 most liquid NSE stocks |
| Option Chain (per-strike OI) | Angel One SmartAPI | On demand | ATM ±20 strikes, max 40 tokens |
| PCR / Max Pain | Calculated | Real-time | From live OI data |
| Support / Resistance / Pivot | Calculated | Real-time | Pivot point method |
| AI Analysis | Groq (llama-4-scout) | On demand | ~1–2 second response |
| Historical snapshots | SQLite | Auto at 15:30 IST | Cumulates day by day |
| Intraday ticks | SQLite | Every 15s refresh | Pruned after 7 days |

### Angel One Token Map

- 210 symbols mapped in `CASH_TOKENS` dict in `angel_service.py`
- Instrument master (156k records) downloaded from Angel One public JSON daily
- Saved to `backend/data/instrument_master.json` (refreshed once per day)
- In-memory index built at startup for O(1) strike token lookups

---

## 8. Database Design

### `watchlist.db`

```sql
CREATE TABLE watchlist (
    symbol    TEXT PRIMARY KEY,
    added_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `stockgpt.db`

```sql
CREATE TABLE daily_snapshot (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date     DATE    NOT NULL,
    symbol         TEXT    NOT NULL,
    ltp            REAL,
    open           REAL,
    high           REAL,
    low            REAL,
    prev_close     REAL,
    call_oi        INTEGER,
    put_oi         INTEGER,
    pcr            REAL,
    signal         TEXT,
    max_pain       REAL,
    price_chg_pct  REAL,
    UNIQUE(trade_date, symbol)
);

CREATE TABLE intraday_ticks (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    tick_time      DATETIME NOT NULL,
    trade_date     DATE     NOT NULL,
    symbol         TEXT     NOT NULL,
    ltp            REAL,
    call_oi        INTEGER,
    put_oi         INTEGER,
    pcr            REAL,
    signal         TEXT,
    pcr_change     REAL,
    price_chg_pct  REAL
);
```

**Auto-save schedule:**
- Intraday ticks: saved every 15s refresh during **9:05–15:45 IST**
- Daily snapshot: saved once at **15:25–15:35 IST** (market close)
- Old ticks pruned: daily at **04:00 IST** (7-day retention)
- All saves run in background threads — never block API responses

---

## 9. Caching Strategy

All external API calls are cached via `cache_service.py`.

```
cache_service.get_or_fetch(key, fetch_fn, ttl)
```

- Uses `threading.RLock` (reentrant) — no deadlocks on nested cache calls
- `market_ttl()` returns 15 during market hours, 60 outside
- Previous market snapshot stored with 6-hour TTL for delta computation
- Instrument master cached 24 hours (also saved to disk)

| Cache Key | TTL | What |
|-----------|-----|------|
| `market_data` | 15s/60s | All 209 stocks |
| `dashboard` | 15s/60s | Full dashboard payload |
| `indices` | 15s/60s | 4 index prices |
| `top_movers` | 15s/60s | Gainers/losers/active |
| `stock_detail:{sym}` | 15s/60s | Per-stock detail |
| `angel_oc:{sym}` | 15s/60s | Option chain |
| `market_prev_snapshot` | 6h | Previous values for delta |
| `angel_instrument_master` | 24h | 156k token records |
| `quote:{sym}` | 15s/60s | Single stock quote |

---

## 10. Refresh & Smart Polling

### Backend
Every cache key uses `cache_service.market_ttl()` which returns:
- `15` seconds — Mon–Fri, 9:15–15:30 IST
- `60` seconds — all other times

### Frontend
```
scheduleNextRefresh()
  → loadDashboard()          ← fetches /api/dashboard
  → refreshPCRIfVisible()    ← fetches /api/market if PCR tab open
  → scheduleNextRefresh()    ← re-schedules with current market_ttl
```

### Keep-alive (Render free tier)
Pings `https://stockgpt-ai.onrender.com/` every 10 minutes from the frontend to prevent the free-tier backend from sleeping.

### Wake-up detection
If the backend is sleeping (Render cold start), the frontend shows:
```
"Waking up the server… (8s elapsed)"
```
And retries every 8 seconds for up to 3 minutes.

---

## 11. Deployment

### Local Development

```bash
# Terminal 1 — Backend
cd D:\StockGPT\backend
python run.py
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)

# Terminal 2 — Frontend
cd D:\StockGPT\frontend
python -m http.server 3000
# → http://localhost:3000
```

### Production (Render + Netlify)

| Service | Platform | URL |
|---------|----------|-----|
| Backend API | Render (free) | https://stockgpt-ai.onrender.com |
| Frontend | Netlify (free) | https://stockgpt-ai1.netlify.app |
| Code | GitHub | https://github.com/jeevaakash232/stockgpt-ai |

**Render config (`backend/render.yaml`):**
```yaml
services:
  - type: web
    name: stockgpt-api
    runtime: python
    rootDir: .
    buildCommand: pip install -r requirements_stockgpt.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Netlify config (`frontend/netlify.toml`):**
```toml
[build]
  publish = "."
```

**Auto-deploy:** Every `git push` to `main` triggers both Render and Netlify to redeploy automatically.

---

## 12. Environment Variables

Set in Render dashboard under **Environment** tab:

| Variable | Description | Example |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key | `gsk_...` |
| `MODEL_NAME` | Groq model ID | `meta-llama/llama-4-scout-17b-16e-instruct` |
| `ANGEL_API_KEY` | Angel One API key | `z0ikbKgb` |
| `ANGEL_CLIENT_ID` | Angel One client ID | `AAAF142252` |
| `ANGEL_PASSWORD` | Angel One trading password | `****` |
| `ANGEL_TOTP_SECRET` | TOTP secret for 2FA | `6YGMBDZ5...` |
| `FRONTEND_URL` | Netlify URL for CORS | `https://stockgpt-ai1.netlify.app` |

---

## 13. Feature Summary by Phase

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | FastAPI backend skeleton | ✅ Done |
| 2 | HTML/CSS/JS frontend | ✅ Done |
| 3 | PCR calculation service | ✅ Done |
| 4 | Market data service (sample) | ✅ Done |
| 5 | Dashboard, PCR table | ✅ Done |
| 6 | Groq AI chat integration | ✅ Done |
| 7 | SQLite watchlist | ✅ Done |
| 8 | Yahoo Finance (indices, movers) | ✅ Done |
| 9 | Angel One SmartAPI (live LTP + option chain) | ✅ Done |
| 10 | Smart cache + market_ttl (15s/60s) | ✅ Done |
| 11 | Tab-based UI (Dashboard/Markets/Watchlist/PCR/Chat) | ✅ Done |
| 12 | Enhanced PCR table (Δ PCR, OI change%, sortable) | ✅ Done |
| 13 | Historical database (daily snapshots + intraday ticks) | ✅ Done |
| 14 | History tab + per-date Excel download | ✅ Done |
| 15 | Render + Netlify deployment | ✅ Done |
| 16 | Wake-up detection + keep-alive | ✅ Done |

---

## 14. Known Limitations

| Limitation | Reason | Impact |
|-----------|--------|--------|
| Index prices ~15 min delayed | Yahoo Finance free tier | Low — absolute levels visible, not tick-by-tick |
| OI data is default/sample | NSE blocks scraping; Angel One option chain API limited on free plan | Medium — PCR signals based on estimates |
| Render free tier sleeps after 15 min | Free plan restriction | First visit after idle takes 30–60s |
| Historical DB resets on Render restart | SQLite stored on ephemeral disk | Medium — data lost on every deploy |
| TOTP session renews every 23h | Angel One JWT lifespan | Low — auto-renews silently |
| No user authentication | Not yet implemented | Anyone can access the deployed site |

> **Note on historical DB on Render:** Render's free tier has ephemeral storage — the SQLite DB is lost on every redeploy. To persist history on the server, upgrade to Render paid tier (persistent disk) or migrate to Supabase/PostgreSQL (Phase 16 roadmap).

---

## 15. Roadmap

| Phase | Feature |
|-------|---------|
| 16 | PostgreSQL / Supabase for persistent historical storage |
| 17 | OI vs Strike price bar chart (Chart.js) |
| 18 | User authentication (JWT login/register) |
| 19 | Personal watchlists per user |
| 20 | Price alerts (email / browser notification) |
| 21 | Real-time WebSocket price feed |
| 22 | Backtesting — historical PCR vs price movement |
| 23 | Mobile app (PWA or React Native) |

---

## Dependencies

```
fastapi==0.135.1
uvicorn==0.41.0
python-multipart==0.0.22
pydantic==2.12.5
python-dotenv==1.2.2
groq==1.1.1
yfinance==1.5.1
nsepython==2.97
logzero==1.7.0
pyotp==2.9.0
websocket-client==1.8.0
smartapi-python==1.3.9
openpyxl==3.1.5
requests==2.32.5
pytz==2024.1
```

---

*Generated by Kiro AI — StockGPT AI implementation document*
