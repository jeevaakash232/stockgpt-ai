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
    # Load previous day's snapshot from SQLite (or cache)
    from app.services.history_service import get_previous_day_snapshot
    from app.utils.db import get_db_cursor, q
    from datetime import date

    prev_day_snapshot = cache_service.get_or_fetch(
        "prev_day_snapshot",
        get_previous_day_snapshot,
        ttl=3600  # cache for 1 hour to avoid excessive DB reads
    ) or {}

    # Find the latest date in daily_snapshot as "today" (simulated date alignment)
    today_str = None
    try:
        with get_db_cursor() as (c, conn):
            c.execute("SELECT MAX(trade_date) as dt FROM daily_snapshot")
            row = c.fetchone()
            if row and row["dt"]:
                if hasattr(row["dt"], "strftime"):
                    today_str = row["dt"].strftime("%Y-%m-%d")
                else:
                    today_str = str(row["dt"])
    except Exception as exc:
        logger.exception("Failed to query MAX(trade_date) from daily_snapshot:")

    if not today_str:
        today_str = date.today().strftime("%Y-%m-%d")

    today_snapshot = {}
    try:
        with get_db_cursor() as (c, conn):
            c.execute(q("""
                SELECT symbol, call_oi, put_oi, pcr, max_pain
                FROM daily_snapshot WHERE trade_date = ?
            """), (today_str,))
            today_snapshot = {
                r["symbol"]: r for r in c.fetchall()
            }
    except Exception as exc:
        logger.exception("Failed to load today_snapshot from daily_snapshot:")

    # Load previous snapshot from cache (survives refreshes, resets on restart) for tick fallback
    prev_snapshot = cache_service.get(_PREV_SNAPSHOT_KEY) or {}

    live_ltps = _get_all_ltps_batch()
    result    = []

    for sym in get_all_symbols():
        ltp = live_ltps.get(sym, 0.0)
        
        # Check if today's snapshot is pre-populated in database
        db_snap = today_snapshot.get(sym)
        if db_snap and db_snap.get("call_oi") is not None and db_snap.get("put_oi") is not None:
            call_oi  = db_snap["call_oi"]
            put_oi   = db_snap["put_oi"]
            max_pain = db_snap["max_pain"] or 0.0
            pcr      = db_snap["pcr"] or calculate_pcr(call_oi, put_oi)
        else:
            oi  = DEFAULT_OI.get(sym, _DEFAULT_OI_FALLBACK)
            call_oi  = oi["call_oi"]
            put_oi   = oi["put_oi"]
            max_pain = oi["max_pain"]
            pcr      = calculate_pcr(call_oi, put_oi)

        # Retrieve previous values from snapshots
        prev = prev_snapshot.get(sym)

        # In-memory tick-to-tick values
        prev_pcr     = prev["pcr"]     if prev else None
        prev_call_oi = prev["call_oi"] if prev else None
        prev_put_oi  = prev["put_oi"]  if prev else None
        prev_ltp     = prev["ltp"]     if prev else None

        # Previous day's EOD values (fallback to tick if DB has no historical data yet)
        prev_day_pcr = None
        if sym in prev_day_snapshot:
            prev_day_pcr = prev_day_snapshot[sym].get("pcr")
        elif prev_pcr is not None:
            prev_day_pcr = prev_pcr

        yesterday_close = None
        if sym in prev_day_snapshot:
            yesterday_close = prev_day_snapshot[sym].get("ltp")
        elif prev_ltp is not None:
            yesterday_close = prev_ltp

        # Δ PCR (Current Day PCR - Previous Day PCR)
        pcr_change = None
        if prev_day_pcr is not None:
            pcr_change = round(pcr - prev_day_pcr, 2)

        # Call OI Change % (using last tick, or fallback to EOD)
        call_oi_chg_pct = None
        ref_call_oi = prev_call_oi if prev_call_oi else (prev_day_snapshot.get(sym, {}).get("call_oi") if sym in prev_day_snapshot else None)
        if ref_call_oi and ref_call_oi != 0:
            call_oi_chg_pct = round(((call_oi - ref_call_oi) / ref_call_oi) * 100)

        # Put OI Change % (using last tick, or fallback to EOD)
        put_oi_chg_pct = None
        ref_put_oi = prev_put_oi if prev_put_oi else (prev_day_snapshot.get(sym, {}).get("put_oi") if sym in prev_day_snapshot else None)
        if ref_put_oi and ref_put_oi != 0:
            put_oi_chg_pct = round(((put_oi - ref_put_oi) / ref_put_oi) * 100)

        # Price Change % since yesterday's close (or fallback to last tick)
        price_chg_pct = None
        if yesterday_close and yesterday_close > 0 and ltp > 0:
            price_chg_pct = round(((ltp - yesterday_close) / yesterday_close) * 100, 1)

        # % change in PCR (Current day PCR - Previous day PCR) / Previous day PCR * 100
        pcr_change_pct = None
        if prev_day_pcr and prev_day_pcr > 0:
            pcr_change_pct = round(((pcr - prev_day_pcr) / prev_day_pcr) * 100, 2)

        # Get expiry date dynamically from instrument master cache
        from app.services.angel_service import get_nearest_expiry
        expiry = get_nearest_expiry(sym)

        result.append({
            "symbol":          sym,
            "ltp":             ltp,
            "call_oi":         call_oi,
            "put_oi":          put_oi,
            "max_pain":        max_pain,
            "pcr":             pcr,
            "signal":          signal(pcr),
            "prev_day_pcr":    prev_day_pcr,
            "prev_pcr":        prev_pcr,
            "prev_call_oi":    prev_call_oi,
            "prev_put_oi":     prev_put_oi,
            "prev_ltp":        prev_ltp,
            "pcr_change":      pcr_change,
            "pcr_change_pct":  pcr_change_pct,
            "expiry":          expiry,
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
            from app.utils.db import get_db_cursor, q
            import pytz as _tz
            ist     = _tz.timezone("Asia/Kolkata")
            now_ist = _dt.now(ist)
            day     = now_ist.weekday()
            mins    = now_ist.hour * 60 + now_ist.minute

            if day < 5 and 545 <= mins <= 945:      # 9:05 – 3:45 IST
                save_intraday_tick(result)

            if day < 5 and 925 <= mins <= 935:      # 3:25 – 3:35 IST (market close)
                save_daily_snapshot(result)
            
            # Catch-up: if after 3:35 PM on a trading day and snapshot is missing, save it
            if day < 5 and mins > 935:
                today_str = now_ist.strftime("%Y-%m-%d")
                has_today = False
                try:
                    with get_db_cursor() as (c, conn):
                        c.execute(q("SELECT 1 FROM daily_snapshot WHERE trade_date = ? LIMIT 1"), (today_str,))
                        has_today = bool(c.fetchone())
                except Exception:
                    pass
                if not has_today:
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
