"""
NSE Public Data Service
-----------------------
Fetches publicly available NSE data without any paid API.
Sources used:
  - nsepython (open-source wrapper around NSE's public JSON endpoints)
  - Fallback to yfinance if nsepython unavailable

All results are cached via cache_service.
"""

import logging
from typing import Optional
from app.services import cache_service
from app.services.pcr_service import calculate_pcr, signal as pcr_signal

logger = logging.getLogger(__name__)

CACHE_TTL = 60  # seconds

# ---------------------------------------------------------------------------
# Try importing nsepython; gracefully degrade if not installed
# ---------------------------------------------------------------------------
try:
    from nsepython import (
        nse_optionchain_scrapper,
        nse_eq,
    )
    _NSE_AVAILABLE = True
    logger.info("nsepython loaded — NSE option chain data enabled.")
except ImportError:
    _NSE_AVAILABLE = False
    logger.warning(
        "nsepython not installed. NSE option chain data will be unavailable. "
        "Install with: pip install nsepython"
    )


# ---------------------------------------------------------------------------
# Option Chain
# ---------------------------------------------------------------------------

def get_option_chain(symbol: str) -> dict:
    """
    Fetch option chain for an NSE F&O symbol.
    Tries Angel One live data first, falls back to nsepython/sample.
    Cached 60 s.
    """
    key = f"option_chain:{symbol.upper()}"
    return cache_service.get_or_fetch(
        key,
        lambda: _fetch_option_chain(symbol),
        ttl=CACHE_TTL,
    )


def _fetch_option_chain(symbol: str) -> dict:
    # Try Angel One live data first (real OI from instrument master)
    try:
        from app.services.angel_service import _fetch_option_chain_live
        result = _fetch_option_chain_live(symbol)
        if result.get("source") == "angel_one_live":
            # Normalise key names to match existing contract
            result.setdefault("expiry_dates", [result.get("expiry")] if result.get("expiry") else [])
            return result
    except Exception as exc:
        logger.warning("Angel option chain failed, trying nsepython: %s", exc)

    # Fallback: nsepython scraper
    if _NSE_AVAILABLE:
        try:
            chain   = nse_optionchain_scrapper(symbol.upper())
            records = chain.get("records", {})
            data    = records.get("data", []) if isinstance(records, dict) else []

            if not data:
                logger.warning("nsepython empty for [%s] — using sample data", symbol)
                return _fallback_option_chain(symbol)

            exp_dates     = records.get("expiryDates", [])
            atm_price     = records.get("underlyingValue", 0)
            total_call_oi = 0
            total_put_oi  = 0
            strikes       = []

            for rec in data:
                strike = rec.get("strikePrice", 0)
                ce     = rec.get("CE", {})
                pe     = rec.get("PE", {})
                c_oi   = ce.get("openInterest", 0) or 0
                p_oi   = pe.get("openInterest", 0) or 0
                total_call_oi += c_oi
                total_put_oi  += p_oi
                strikes.append({
                    "strike":   strike,
                    "call_oi":  c_oi,
                    "put_oi":   p_oi,
                    "call_ltp": ce.get("lastPrice", 0),
                    "put_ltp":  pe.get("lastPrice", 0),
                })

            pcr      = calculate_pcr(total_call_oi, total_put_oi)
            max_pain = _calculate_max_pain(strikes)

            return {
                "symbol":        symbol.upper(),
                "underlying":    atm_price,
                "expiry_dates":  exp_dates[:5],
                "total_call_oi": total_call_oi,
                "total_put_oi":  total_put_oi,
                "pcr":           pcr,
                "signal":        pcr_signal(pcr),
                "max_pain":      max_pain,
                "strikes":       strikes[:40],
                "source":        "nsepython",
            }
        except Exception as exc:
            logger.error("NSE option chain fetch failed [%s]: %s", symbol, exc)

    return _fallback_option_chain(symbol)


def _calculate_max_pain(strikes: list[dict]) -> float:
    """
    Max Pain = strike price at which total option buyer loss is maximum
    (i.e., option writer gains the most).
    """
    if not strikes:
        return 0.0

    strike_prices = [s["strike"] for s in strikes]
    pain_at_strike = {}

    for test_strike in strike_prices:
        total_pain = 0.0
        for s in strikes:
            k = s["strike"]
            # Call buyers lose if test_strike < k
            if test_strike < k:
                total_pain += s["call_oi"] * (k - test_strike)
            # Put buyers lose if test_strike > k
            if test_strike > k:
                total_pain += s["put_oi"] * (test_strike - k)
        pain_at_strike[test_strike] = total_pain

    return min(pain_at_strike, key=pain_at_strike.get)


def _fallback_option_chain(symbol: str) -> dict:
    """Return a minimal structure using existing sample market data."""
    from app.services.market_data import get_market
    market_list = get_market()
    # Build lookup by symbol
    market = {s["symbol"].upper(): s for s in market_list}
    stock  = market.get(symbol.upper(), {})
    call_oi = stock.get("call_oi", 0)
    put_oi  = stock.get("put_oi",  0)
    pcr_val = stock.get("pcr",     calculate_pcr(call_oi, put_oi))
    return {
        "symbol":         symbol.upper(),
        "underlying":     stock.get("ltp", 0),
        "expiry_dates":   [],
        "total_call_oi":  call_oi,
        "total_put_oi":   put_oi,
        "pcr":            pcr_val,
        "signal":         stock.get("signal", pcr_signal(pcr_val)),
        "max_pain":       stock.get("max_pain", 0),
        "strikes":        [],
        "note":           "Live option chain unavailable. Install nsepython for full data.",
    }
