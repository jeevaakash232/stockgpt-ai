"""
Yahoo Finance Service
---------------------
Wraps yfinance to fetch live price data, OHLCV, and indices.
All calls are cached via cache_service — never called directly from routes.

NSE suffix mapping: symbol + ".NS" for equities, ".BO" for BSE if needed.
Indices use their own Yahoo tickers (^NSEI, ^NSEBANK, ^BSESN, ^INDIAVIX).
"""

import logging
from typing import Optional
import yfinance as yf

from app.services import cache_service
from app.services.pcr_service import calculate_pcr, signal as pcr_signal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ticker maps
# ---------------------------------------------------------------------------

INDICES = {
    "NIFTY":     "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX":    "^BSESN",
    "INDIAVIX":  "^INDIAVIX",
}

# Common NSE F&O equity symbols — used for top movers (Yahoo Finance batch download)
# We limit to 50 most liquid for Yahoo download speed
EQUITY_SYMBOLS = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "SBIN", "BAJFINANCE", "HINDUNILVR", "ITC", "AXISBANK",
    "KOTAKBANK", "LT", "TITAN", "WIPRO", "MARUTI",
    "ADANIENT", "POWERGRID", "NTPC", "SUNPHARMA", "ONGC",
    "BHARTIARTL", "HCLTECH", "TATASTEEL", "COALINDIA", "BPCL",
    "GRASIM", "DIVISLAB", "DRREDDY", "CIPLA", "EICHERMOT",
    "HEROMOTOCO", "BAJAJ-AUTO", "TATAPOWER", "HINDALCO", "JSWSTEEL",
    "ULTRACEMCO", "TECHM", "TRENT", "NESTLEIND", "BRITANNIA",
    "APOLLOHOSP", "DABUR", "MARICO", "PIDILITIND", "HAVELLS",
    "INDUSINDBK", "DLF", "GODREJCP", "TATACONSUM", "CHOLAFIN",
]

CACHE_TTL = 60  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nse_ticker(symbol: str) -> str:
    """Convert a plain NSE symbol to its Yahoo Finance ticker."""
    symbol = symbol.upper().strip()
    if symbol in INDICES:
        return INDICES[symbol]
    return f"{symbol}.NS"


def _safe_float(val) -> Optional[float]:
    try:
        f = float(val)
        return round(f, 2) if f == f else None  # NaN check
    except (TypeError, ValueError):
        return None


def _extract_quote(ticker_obj: yf.Ticker) -> dict:
    """Pull a standardised quote dict from a yf.Ticker object."""
    fast = None
    try:
        fast = ticker_obj.fast_info
    except Exception:
        pass

    info = {}
    # Only access the extremely slow .info property if fast_info is unavailable
    if not fast or getattr(fast, "last_price", None) is None:
        try:
            info = ticker_obj.info or {}
        except Exception:
            pass

    def _get(*keys):
        for k in keys:
            # Map fast_info attributes
            fast_attr = k
            if k == "currentPrice": fast_attr = "last_price"
            elif k == "regularMarketPrice": fast_attr = "last_price"
            elif k == "regularMarketPreviousClose": fast_attr = "previous_close"
            elif k == "previousClose": fast_attr = "previous_close"
            elif k == "dayHigh": fast_attr = "day_high"
            elif k == "dayLow": fast_attr = "day_low"
            elif k == "day_high": fast_attr = "day_high"
            elif k == "day_low": fast_attr = "day_low"

            v = getattr(fast, fast_attr, None) if fast else None
            if v is None and info:
                v = info.get(k)
            if v is not None:
                return _safe_float(v)
        return None

    current = _get("currentPrice", "regularMarketPrice", "last_price")
    prev    = _get("previousClose", "regularMarketPreviousClose", "previous_close")
    change  = None
    pct     = None
    if current is not None and prev is not None and prev != 0:
        change = round(current - prev, 2)
        pct    = round((change / prev) * 100, 2)

    volume = _safe_float(getattr(fast, "last_volume", None)) if fast else None
    if volume is None and info:
        volume = _safe_float(info.get("volume") or info.get("regularMarketVolume"))

    market_cap = _safe_float(getattr(fast, "market_cap", None)) if fast else None
    if market_cap is None and info:
        market_cap = _safe_float(info.get("marketCap"))

    return {
        "current_price": current,
        "open":          _get("open", "regularMarketOpen"),
        "high":          _get("dayHigh", "regularMarketDayHigh", "day_high"),
        "low":           _get("dayLow",  "regularMarketDayLow", "day_low"),
        "prev_close":    prev,
        "volume":        volume,
        "market_cap":    market_cap,
        "week_52_high":  _get("fiftyTwoWeekHigh", "year_high"),
        "week_52_low":   _get("fiftyTwoWeekLow", "year_low"),
        "change":        change,
        "change_pct":    pct,
    }


# ---------------------------------------------------------------------------
# Public functions (all cached)
# ---------------------------------------------------------------------------

def get_quote(symbol: str) -> dict:
    """Fetch live quote for a single symbol. Result cached 60 s."""
    cache_key = f"quote:{symbol.upper()}"
    return cache_service.get_or_fetch(
        cache_key,
        lambda: _fetch_quote(symbol),
        ttl=CACHE_TTL,
    )


def _fetch_quote(symbol: str) -> dict:
    ticker = yf.Ticker(_nse_ticker(symbol))
    data   = _extract_quote(ticker)
    data["symbol"] = symbol.upper()
    return data


def get_indices() -> dict:
    """Fetch all four indices in one call. TTL: 15s market hours, 60s outside."""
    return cache_service.get_or_fetch(
        "indices",
        _fetch_indices,
        ttl=cache_service.market_ttl(),
    )


def _fetch_indices() -> dict:
    result = {}
    for name, ticker_sym in INDICES.items():
        q_data = None
        try:
            ticker = yf.Ticker(ticker_sym)
            q_data = _extract_quote(ticker)
        except Exception as exc:
            logger.warning("Yahoo Index fetch failed [%s]: %s", name, exc)

        # Fallback to Angel One if Yahoo is rate-limited or fails
        if not q_data or q_data.get("current_price") is None:
            try:
                from app.services.angel_service import _get_session
                smart = _get_session()
                resp = None
                if name == "NIFTY":
                    resp = smart.ltpData("NSE", "NIFTY", "26000")
                elif name == "BANKNIFTY":
                    resp = smart.ltpData("NSE", "BANKNIFTY", "26009")
                elif name == "SENSEX":
                    resp = smart.ltpData("BSE", "BSX", "1")

                if resp and resp.get("status") and resp.get("data"):
                    d = resp["data"]
                    ltp = float(d.get("ltp", 0))
                    close = float(d.get("close", 0))
                    chg = round(ltp - close, 2) if close else 0.0
                    pct = round((chg / close) * 100, 2) if close else 0.0
                    q_data = {
                        "current_price": ltp,
                        "change": chg,
                        "change_pct": pct,
                        "high": float(d.get("high", 0)),
                        "low": float(d.get("low", 0)),
                    }
            except Exception as angel_exc:
                logger.warning("Angel Index fallback failed [%s]: %s", name, angel_exc)

        if q_data and q_data.get("current_price") is not None:
            result[name] = {
                "symbol":        name,
                "current_price": q_data["current_price"],
                "change":        q_data["change"],
                "change_pct":    q_data["change_pct"],
                "high":          q_data["high"],
                "low":           q_data["low"],
            }
        else:
            result[name] = {"symbol": name, "error": "Unavailable — rate limited"}
    return result


def get_top_movers() -> dict:
    """
    Fetch quotes for all tracked equities and compute top gainers,
    top losers, and most active. TTL: 15s market hours, 60s outside.
    """
    return cache_service.get_or_fetch(
        "top_movers",
        _fetch_top_movers,
        ttl=cache_service.market_ttl(),
    )


def _fetch_top_movers() -> dict:
    tickers_str = " ".join(f"{s}.NS" for s in EQUITY_SYMBOLS)
    try:
        data = yf.download(
            tickers_str,
            period="2d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as exc:
        logger.error("yf.download failed: %s", exc)
        return {"gainers": [], "losers": [], "most_active": []}

    quotes = []
    for sym in EQUITY_SYMBOLS:
        try:
            ticker_key = f"{sym}.NS"
            if ticker_key not in data.columns.get_level_values(0):
                continue
            df  = data[ticker_key].dropna()
            if len(df) < 2:
                continue
            prev  = float(df["Close"].iloc[-2])
            curr  = float(df["Close"].iloc[-1])
            vol   = float(df["Volume"].iloc[-1])
            hi    = float(df["High"].iloc[-1])
            lo    = float(df["Low"].iloc[-1])
            chg   = round(curr - prev, 2)
            pct   = round((chg / prev) * 100, 2) if prev else 0
            quotes.append({
                "symbol":     sym,
                "price":      round(curr, 2),
                "change":     chg,
                "change_pct": pct,
                "volume":     int(vol),
                "high":       round(hi, 2),
                "low":        round(lo, 2),
            })
        except Exception as exc:
            logger.debug("Skip %s: %s", sym, exc)

    gainers     = sorted(quotes, key=lambda x: x["change_pct"], reverse=True)
    losers      = sorted(quotes, key=lambda x: x["change_pct"])
    most_active = sorted(quotes, key=lambda x: x["volume"], reverse=True)

    return {
        "gainers":     gainers,
        "losers":      losers,
        "most_active": most_active,
    }


def search_symbols(query: str) -> list[dict]:
    """
    Search NSE symbols from the instrument master + tracked equity list.
    Returns up to 10 suggestions with basic info.
    Tries instrument index first for full NSE coverage.
    """
    q = query.upper().strip()
    if len(q) < 1:
        return []

    results = []
    seen    = set()

    # Search Angel One instrument index for equity symbols
    try:
        from app.services.angel_service import _get_instrument_index
        index = _get_instrument_index()
        # Collect unique symbols from NSE cash segment that match
        for (sym, exp, opt) in index.keys():
            if q in sym and sym not in seen:
                seen.add(sym)
                results.append({"symbol": sym, "label": f"{sym} (NSE)"})
            if len(results) >= 10:
                break
    except Exception:
        pass

    # Always also include tracked equity symbols as fallback
    for s in EQUITY_SYMBOLS:
        if q in s and s not in seen:
            seen.add(s)
            results.append({"symbol": s, "label": f"{s} (NSE)"})

    return results[:10]


def warm_cache() -> None:
    """Pre-warm all heavy cache keys at startup (non-blocking)."""
    import threading
    def _warm():
        try:
            get_indices()
            get_top_movers()
            logger.info("Cache warm-up complete.")
        except Exception as exc:
            logger.warning("Cache warm-up failed: %s", exc)
    threading.Thread(target=_warm, daemon=True, name="cache-warmup").start()
