"""
Market Data Service
-------------------
Provides live LTP for ALL NSE F&O equity symbols (~210 stocks) + indices.
Live prices fetched from Angel One in batches of 50 tokens per call.
OI/PCR data is available on demand via /api/option-chain/{symbol}.

To add more symbols: they are auto-loaded from CASH_TOKENS in angel_service.py.
"""

from app.services.pcr_service import calculate_pcr, signal
from app.services import cache_service

CACHE_TTL = 60  # fallback default

# ---------------------------------------------------------------------------
# Default OI values for PCR table (used when live OI is not yet fetched).
# Live OI is fetched on-demand via /api/option-chain/{symbol}.
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


def get_all_symbols() -> list[str]:
    """Return all tracked NSE F&O symbols sorted alphabetically."""
    from app.services.angel_service import CASH_TOKENS
    # Exclude index tokens from the equity list
    indices = {"NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX"}
    equities = sorted(s for s in CASH_TOKENS if s not in indices)
    # Indices first, then equities
    return ["NIFTY", "BANKNIFTY", "FINNIFTY"] + equities


def get_sample_data() -> list[dict]:
    """Return fallback stock records (used by pcr API when live data unavailable)."""
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
    Return ALL NSE F&O stocks with live LTP from Angel One.
    Cache TTL: 15s during market hours, 60s outside.
    """
    return cache_service.get_or_fetch(
        "market_data",
        _build_market,
        ttl=cache_service.market_ttl(),
    )


def _build_market() -> list[dict]:
    # Fetch all live LTPs in batches
    live_ltps = _get_all_ltps_batch()

    result = []
    for sym in get_all_symbols():
        ltp = live_ltps.get(sym, 0.0)
        oi  = DEFAULT_OI.get(sym, _DEFAULT_OI_FALLBACK)

        pcr_value = calculate_pcr(oi["call_oi"], oi["put_oi"])
        result.append({
            "symbol":   sym,
            "call_oi":  oi["call_oi"],
            "put_oi":   oi["put_oi"],
            "ltp":      ltp,
            "max_pain": oi["max_pain"],
            "pcr":      pcr_value,
            "signal":   signal(pcr_value),
        })
    return result


def _get_all_ltps_batch() -> dict:
    """
    Fetch live LTP for ALL tracked symbols using Angel One batch API.
    Angel One allows 50 tokens per call — we make multiple calls as needed.
    Returns dict: symbol -> ltp
    """
    from app.services.angel_service import CASH_TOKENS, _get_session
    import time

    # Build token -> symbol reverse map
    token_to_sym = {v: k for k, v in CASH_TOKENS.items()}
    all_tokens   = list(CASH_TOKENS.values())
    ltps         = {}
    BATCH        = 50  # Angel One free tier limit

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
                time.sleep(0.1)   # small pause between batches

    except Exception:
        pass

    # Fallback: use Yahoo Finance movers cache for at least the popular symbols
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
