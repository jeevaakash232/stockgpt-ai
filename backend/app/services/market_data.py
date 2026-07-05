"""
Market Data Service
-------------------
Provides live LTP for ALL NSE F&O equity symbols (~210 stocks) + indices.
Live prices fetched from Angel One in batches of 50 tokens per call.

Change tracking:
  - Previous snapshot is saved each refresh cycle (in-memory)
  - Δ PCR, Call OI Change %, Put OI Change %, Price Change % are computed
    from the difference between the current and previous snapshot
"""

from app.services.pcr_service import calculate_pcr, signal
from app.services import cache_service

CACHE_TTL = 60  # fallback default

# ---------------------------------------------------------------------------
# Default OI values (fallback estimates when live OI not fetched)
# ---------------------------------------------------------------------------
DEFAULT_OI = {
    "NIFTY":      {"call_oi": 5_500_000, "put_oi": 6_200_000, "max_pain": 24000},
    "BANKNIFTY":  {"call_oi": 3_100_000, "put_oi": 3_400_000, "max_pain": 57000},
    "FINNIFTY":   {"call_oi":   800_000, "put_oi":   750_000, "max_pain": 24000},
    "RELIANCE":   {"call_oi": 1_200_000, "put_oi":   720_000, "max_pain":  1300},
    "TCS":        {"call_oi":   380_000, "put_oi":   290_000, "max_pain":  2000},
    "INFY":       {"call_oi":   420_000, "put_oi":   390_000, "max_pain":  1000},
    "HDFCBANK":   {"call_oi":   550_000, "put_oi":   480_000, "max_pain":  1900},
    "ICICIBANK":  {"call_oi":   490_000, "put_oi":   430_000, "max_pain":  1400},
    "SBIN":       {"call_oi":   800_000, "put_oi":   600_000, "max_pain":  1000},
    "BAJFINANCE": {"call_oi":   310_000, "put_oi":   270_000, "max_pain":  7000},
    "HINDUNILVR": {"call_oi":   180_000, "put_oi":   150_000, "max_pain":  2300},
    "ITC":        {"call_oi":   420_000, "put_oi":   380_000, "max_pain":   460},
    "AXISBANK":   {"call_oi":   370_000, "put_oi":   310_000, "max_pain":  1300},
    "KOTAKBANK":  {"call_oi":   290_000, "put_oi":   250_000, "max_pain":  2100},
    "LT":         {"call_oi":   230_000, "put_oi":   200_000, "max_pain":  3600},
    "TITAN":      {"call_oi":   160_000, "put_oi":   130_000, "max_pain":  3400},
    "WIPRO":      {"call_oi":   200_000, "put_oi":   170_000, "max_pain":   530},
    "MARUTI":     {"call_oi":   140_000, "put_oi":   120_000, "max_pain": 12500},
    "ADANIENT":   {"call_oi":   260_000, "put_oi":   220_000, "max_pain":  2500},
    "SUNPHARMA":  {"call_oi":   170_000, "put_oi":   140_000, "max_pain":  1850},
}

_DEFAULT_OI_FALLBACK = {"call_oi": 100_000, "put_oi": 100_000, "max_pain": 0}

# Cache key for the previous snapshot
_PREV_SNAPSHOT_KEY = "market_prev_snapshot"


def get_all_symbols() -> list[str]:
    """Return all tracked NSE F&O symbols."""
    from app.services.angel_service import CASH_TOKENS
    indices  = {"NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX"}
    equities = sorted(s for s in CASH_TOKENS if s not in indices)
    return ["NIFTY", "BANKNIFTY", "FINNIFTY"] + equities


def get_sample_data() -> list[dict]:
    """Fallback records for pcr API."""
    from app.services.angel_service import CASH_TOKENS
    result = []
    for sym in get_all_symbols():
        if sym not in CASH_TOKENS:
            continue
        oi = DEFAULT_OI.get(sym, _DEFAULT_OI_FALLBACK)
        result.append({
            "symbol":   sym,
            "call_oi":  oi["call_oi"],
            "put_oi":   oi["put_oi"],
            "ltp":      0.0,
            "max_pain": oi["max_pain"],
        })
    return result


def get_market() -> list[dict]:
    """
    Return ALL NSE F&O stocks with live LTP, PCR and change metrics.
    Cache TTL: 15s market hours, 60s outside.
    """
    return cache_service.get_or_fetch(
        "market_data",
        _build_market,
        ttl=cache_service.market_ttl(),
    )


def _build_market() -> list[dict]:
    # Load previous snapshot from cache (survives refreshes, resets on restart)
    prev_snapshot = cache_service.get(_PREV_SNAPSHOT_KEY) or {}

    live_ltps = _get_all_ltps_batch()
    result    = []

    for sym in get_all_symbols():
        ltp = live_ltps.get(sym, 0.0)
        oi  = DEFAULT_OI.get(sym, _DEFAULT_OI_FALLBACK)

        call_oi  = oi["call_oi"]
        put_oi   = oi["put_oi"]
        max_pain = oi["max_pain"]
        pcr      = calculate_pcr(call_oi, put_oi)

        # Retrieve previous values from snapshot
        prev = prev_snapshot.get(sym)

        prev_pcr     = prev["pcr"]     if prev else None
        prev_call_oi = prev["call_oi"] if prev else None
        prev_put_oi  = prev["put_oi"]  if prev else None
        prev_ltp     = prev["ltp"]     if prev else None

        # Δ PCR
        pcr_change = None
        if prev_pcr is not None:
            pcr_change = round(pcr - prev_pcr, 2)

        # Call OI Change %
        call_oi_chg_pct = None
        if prev_call_oi and prev_call_oi != 0:
            call_oi_chg_pct = round(((call_oi - prev_call_oi) / prev_call_oi) * 100)

        # Put OI Change %
        put_oi_chg_pct = None
        if prev_put_oi and prev_put_oi != 0:
            put_oi_chg_pct = round(((put_oi - prev_put_oi) / prev_put_oi) * 100)

        # Price Change %
        price_chg_pct = None
        if prev_ltp and prev_ltp > 0 and ltp > 0:
            price_chg_pct = round(((ltp - prev_ltp) / prev_ltp) * 100, 1)

        result.append({
            "symbol":          sym,
            "ltp":             ltp,
            "call_oi":         call_oi,
            "put_oi":          put_oi,
            "max_pain":        max_pain,
            "pcr":             pcr,
            "signal":          signal(pcr),
            "prev_pcr":        prev_pcr,
            "prev_call_oi":    prev_call_oi,
            "prev_put_oi":     prev_put_oi,
            "prev_ltp":        prev_ltp,
            "pcr_change":      pcr_change,
            "call_oi_chg_pct": call_oi_chg_pct,
            "put_oi_chg_pct":  put_oi_chg_pct,
            "price_chg_pct":   price_chg_pct,
        })

    # Save current as next prev_snapshot with a long TTL (6 hours)
    # so it persists through multiple refresh cycles
    new_snapshot = {
        row["symbol"]: {
            "pcr":     row["pcr"],
            "call_oi": row["call_oi"],
            "put_oi":  row["put_oi"],
            "ltp":     row["ltp"],
        }
        for row in result
        if row["ltp"] > 0
    }
    cache_service.set(_PREV_SNAPSHOT_KEY, new_snapshot, ttl=21600)

    # ── Persist to SQLite in background ─────────────────────
    import threading
    from datetime import datetime as _dt

    def _persist():
        try:
            from app.services.history_service import (
                save_intraday_tick, save_daily_snapshot, prune_old_ticks
            )
            import pytz as _tz
            ist     = _tz.timezone("Asia/Kolkata")
            now_ist = _dt.now(ist)
            day     = now_ist.weekday()
            mins    = now_ist.hour * 60 + now_ist.minute

            if day < 5 and 545 <= mins <= 945:      # 9:05 – 3:45 IST
                save_intraday_tick(result)

            if day < 5 and 925 <= mins <= 935:      # 3:25 – 3:35 IST (market close)
                save_daily_snapshot(result)

            if mins == 240:                          # 4:00 AM — prune old ticks
                prune_old_ticks()
        except Exception as _e:
            pass  # never crash the main thread

    threading.Thread(target=_persist, daemon=True, name="db-persist").start()

    return result


def _get_all_ltps_batch() -> dict:
    """
    Fetch live LTP for ALL tracked symbols in Angel One batch calls.
    Returns dict: symbol -> ltp
    """
    from app.services.angel_service import CASH_TOKENS, _get_session
    import time

    token_to_sym = {v: k for k, v in CASH_TOKENS.items()}
    all_tokens   = list(CASH_TOKENS.values())
    ltps         = {}
    BATCH        = 50

    try:
        smart = _get_session()
        for i in range(0, len(all_tokens), BATCH):
            batch = all_tokens[i : i + BATCH]
            try:
                resp = smart.getMarketData("LTP", {"NSE": batch})
                if resp and resp.get("status"):
                    for item in (resp.get("data", {}).get("fetched") or []):
                        token = str(item.get("symbolToken", ""))
                        ltp   = float(item.get("ltp", 0) or 0)
                        sym   = token_to_sym.get(token)
                        if sym and ltp > 0:
                            ltps[sym] = ltp
            except Exception:
                pass
            if i + BATCH < len(all_tokens):
                time.sleep(0.1)
    except Exception:
        pass

    # Fallback: Yahoo Finance movers cache
    if len(ltps) < 10:
        try:
            movers = cache_service.get("top_movers")
            if movers:
                all_q = (movers.get("gainers", []) +
                         movers.get("losers",  []) +
                         movers.get("most_active", []))
                for q in all_q:
                    if q.get("symbol") and q.get("price") and q["symbol"] not in ltps:
                        ltps[q["symbol"]] = q["price"]
        except Exception:
            pass

    return ltps
