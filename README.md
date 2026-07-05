# 📈 StockGPT AI — Live Indian Stock Market Dashboard

AI-powered stock market dashboard with live NSE data, option chain analysis, PCR calculations, and Groq-powered AI chat.

---

## What's Live vs Estimated

| Feature | Source | Status |
|---------|--------|--------|
| NIFTY / BANKNIFTY / SENSEX / VIX prices | Yahoo Finance | ✅ Live |
| 20-stock LTP (RELIANCE, TCS, etc.) | Angel One SmartAPI | ✅ Live |
| Top Gainers / Losers / Most Active | Yahoo Finance | ✅ Live |
| Option Chain (PCR, OI per strike, Max Pain) | Angel One SmartAPI | ✅ Live |
| Support / Resistance / Pivot | Calculated (pivot-point) | ✅ Calculated |
| AI Analysis | Groq (llama-4-scout) | ✅ Live |
| Watchlist | SQLite (persistent) | ✅ Saved |
| Sample OI in PCR table | Hardcoded fallback | ⚠️ Estimated |

---

## Project Structure

```
StockGPT/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── chat.py           POST /api/chat
│   │   │   ├── dashboard.py      GET  /api/dashboard + movers + indices
│   │   │   ├── market.py         GET  /api/market
│   │   │   ├── option_chain.py   GET  /api/option-chain/{symbol}
│   │   │   ├── pcr.py            GET  /api/pcr
│   │   │   ├── stock.py          GET  /api/stock/{symbol}  GET /api/search
│   │   │   └── watchlist.py      GET/POST/DELETE /api/watchlist
│   │   ├── services/
│   │   │   ├── ai_service.py     Groq API wrapper
│   │   │   ├── angel_service.py  Angel One SmartAPI (live quotes + option chain)
│   │   │   ├── cache_service.py  In-memory TTL cache (60s)
│   │   │   ├── market_data.py    20-stock list with live LTP batch fetch
│   │   │   ├── market_service.py Dashboard aggregator
│   │   │   ├── nse_service.py    NSE option chain (Angel One → nsepython → fallback)
│   │   │   ├── pcr_service.py    PCR calculation logic
│   │   │   ├── watchlist_service.py SQLite watchlist CRUD
│   │   │   └── yahoo_service.py  Yahoo Finance (indices, movers, quotes)
│   │   └── main.py
│   ├── data/
│   │   └── instrument_master.json  Angel One NFO tokens (refreshed daily)
│   ├── models/stock.py
│   ├── watchlist.db                SQLite watchlist
│   ├── .env                        API keys
│   ├── requirements_stockgpt.txt   Clean dependency list
│   └── run.py
└── frontend/
    ├── index.html
    ├── css/style.css
    └── js/
        ├── api.js           Base URL + fetch wrapper
        ├── app.js           Sidebar scroll-spy + mobile hamburger
        ├── chat.js          AI chat UI
        ├── dashboard.js     Market overview + movers + watchlist (60s refresh)
        ├── market.js        PCR table + analyzeStock()
        ├── search.js        Navbar autocomplete
        └── stock_detail.js  Stock modal + TradingView chart + option chain table
```

---

## Setup

### 1. Install dependencies

```bash
cd backend
pip install -r requirements_stockgpt.txt
```

### 2. Configure `.env`

```env
GROQ_API_KEY=gsk_your_groq_key_here
MODEL_NAME=meta-llama/llama-4-scout-17b-16e-instruct

ANGEL_API_KEY=your_angel_api_key
ANGEL_CLIENT_ID=your_client_id
ANGEL_PASSWORD=your_trading_password
ANGEL_TOTP_SECRET=your_totp_secret
```

- **Groq key**: [console.groq.com/keys](https://console.groq.com/keys)
- **Angel One**: [smartapi.angelone.in](https://smartapi.angelone.in) → Create App → Enable TOTP on mobile app

### 3. Start backend

```bash
cd backend
python run.py
```

Backend: `http://localhost:8000` | Swagger docs: `http://localhost:8000/docs`

### 4. Start frontend

```bash
cd frontend
python -m http.server 3000
```

Open: `http://localhost:3000`

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/api/market` | 20 stocks with live LTP + PCR |
| GET | `/api/pcr` | PCR table (same data, reshaped) |
| GET | `/api/indices` | NIFTY, BANKNIFTY, SENSEX, India VIX |
| GET | `/api/dashboard` | Full dashboard payload |
| GET | `/api/top-gainers` | Top 10 gainers by % change |
| GET | `/api/top-losers` | Top 10 losers by % change |
| GET | `/api/most-active` | Top 10 by volume |
| GET | `/api/stock/{symbol}` | Full quote + PCR + OI + support/resistance |
| GET | `/api/option-chain/{symbol}` | Live per-strike OI from Angel One |
| GET | `/api/search?q=` | Symbol autocomplete |
| GET | `/api/watchlist` | Get watchlist with live prices |
| POST | `/api/watchlist` | Add symbol `{"symbol":"RELIANCE"}` |
| DELETE | `/api/watchlist/{symbol}` | Remove symbol |
| POST | `/api/chat` | Ask StockGPT AI `{"question":"...","symbol":"NIFTY"}` |

---

## Performance (cached)

| Endpoint | First call | Cached |
|----------|-----------|--------|
| `/api/market` (20 stocks) | ~1.5s | <0.1s |
| `/api/dashboard` | ~5s | <0.1s |
| `/api/option-chain/NIFTY` | ~2-3s | <0.1s |
| `/api/chat` | ~1.5s | — |

Cache TTL: 60 seconds. Instrument master: refreshed daily (saved to disk).

---

## Phase Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| 1-6 | Dashboard, AI Chat, PCR, Market API | ✅ Done |
| 7 | SQLite watchlist + live data | ✅ Done |
| 8 | Angel One live OI + option chain | ✅ Done |
| 9 | OI vs Strike bar chart (Chart.js) | 🔜 Next |
| 10 | User authentication (JWT) | 🔜 Planned |
| 11 | Real-time WebSocket price feed | 🔜 Planned |
| 12 | Alerts & notifications | 🔜 Planned |
