"""
Market Service
--------------
Orchestrator layer that assembles the full dashboard payload
by combining data from yahoo_service, nse_service, watchlist_service,
and the existing market_data / pcr_service.

All heavy lifting is delegated to individual services.
This layer only aggregates and caches the combined result.
"""

import logging
from app.services import cache_service, yahoo_service, watchlist_service
from app.services.market_data import get_market      # existing service — untouched
from app.services.pcr_service  import calculate_pcr, signal as pcr_signal

logger = logging.getLogger(__name__)

CACHE_TTL = 60


# ---------------------------------------------------------------------------
# Dashboard aggregate
# ---------------------------------------------------------------------------

def get_dashboard() -> dict:
    """
    Single endpoint payload for the full dashboard.
    TTL: 15s during market hours, 60s outside.
    """
    return cache_service.get_or_fetch(
        "dashboard",
        _build_dashboard,
        ttl=cache_service.market_ttl(),
    )


def _build_dashboard() -> dict:
    # Call the raw fetchers directly — the dashboard result itself is cached,
    # so we don't need inner caching here. This also avoids any lock nesting.
    from app.services.yahoo_service import _fetch_indices, _fetch_top_movers

    movers  = _fetch_top_movers()
    indices = _fetch_indices()

    # Market overview: combine Yahoo index price with existing PCR data
    pcr_data   = get_market()
    nifty_pcr  = next((s for s in pcr_data if s["symbol"] == "NIFTY"), {})
    total_call = sum(s["call_oi"] for s in pcr_data)
    total_put  = sum(s["put_oi"]  for s in pcr_data)

    nifty_idx = indices.get("NIFTY", {})
    market_overview = {
        "nifty_ltp":     nifty_idx.get("current_price"),
        "nifty_change":  nifty_idx.get("change"),
        "nifty_pct":     nifty_idx.get("change_pct"),
        "pcr":           nifty_pcr.get("pcr"),
        "signal":        nifty_pcr.get("signal"),
        "max_pain":      nifty_pcr.get("max_pain"),
        "total_call_oi": total_call,
        "total_put_oi":  total_put,
    }

    return {
        "marketOverview": market_overview,
        "topGainers":     movers.get("gainers",     [])[:25],
        "topLosers":      movers.get("losers",      [])[:25],
        "mostActive":     movers.get("most_active", [])[:25],
        "indices":        indices,
        "watchlist":      watchlist_service.get_watchlist_with_prices(),
    }


# ---------------------------------------------------------------------------
# Individual helpers (used by dedicated API endpoints)
# ---------------------------------------------------------------------------

def get_top_gainers() -> list[dict]:
    movers = yahoo_service.get_top_movers()
    return movers.get("gainers", [])


def get_top_losers() -> list[dict]:
    movers = yahoo_service.get_top_movers()
    return movers.get("losers", [])


def get_most_active() -> list[dict]:
    movers = yahoo_service.get_top_movers()
    return movers.get("most_active", [])


def get_indices() -> dict:
    return yahoo_service.get_indices()


def get_stock_detail(symbol: str) -> dict:
    """
    Full detail for a single stock.
    TTL: 15s during market hours, 60s outside.
    """
    key = f"stock_detail:{symbol.upper()}"
    return cache_service.get_or_fetch(
        key,
        lambda: _build_stock_detail(symbol),
        ttl=cache_service.market_ttl(),
    )


def _build_stock_detail(symbol: str) -> dict:
    from app.services.nse_service import _fetch_option_chain
    from app.services.yahoo_service import _fetch_quote

    symbol = symbol.upper()
    # Call raw fetchers directly to avoid nested lock acquisition
    quote  = _fetch_quote(symbol)
    chain  = _fetch_option_chain(symbol)

    price = quote.get("current_price") or 0
    high  = quote.get("high")  or price
    low   = quote.get("low")   or price

    # Simple support/resistance: pivot-point based
    prev_close = quote.get("prev_close") or price
    pivot   = round((high + low + prev_close) / 3, 2)
    support = round((2 * pivot) - high, 2)
    resist  = round((2 * pivot) - low,  2)

    return {
        "symbol":        symbol,
        "current_price": price,
        "open":          quote.get("open"),
        "high":          high,
        "low":           low,
        "prev_close":    prev_close,
        "volume":        quote.get("volume"),
        "market_cap":    quote.get("market_cap"),
        "week_52_high":  quote.get("week_52_high"),
        "week_52_low":   quote.get("week_52_low"),
        "change":        quote.get("change"),
        "change_pct":    quote.get("change_pct"),
        "pcr":           chain.get("pcr"),
        "signal":        chain.get("signal"),
        "call_oi":       chain.get("total_call_oi"),
        "put_oi":        chain.get("total_put_oi"),
        "max_pain":      chain.get("max_pain"),
        "support":       support,
        "resistance":    resist,
        "pivot":         pivot,
        "expiry_dates":  chain.get("expiry_dates", []),
    }
