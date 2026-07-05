"""
Watchlist Service
-----------------
Manages watchlist symbols.
Persistence supports both SQLite (locally) and PostgreSQL (in production).
"""

import os
import logging
from app.utils.db import get_db_cursor, q

logger = logging.getLogger(__name__)

# SQLite fallback path
_WATCHLIST_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "watchlist.db")
)


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create the watchlist table if it doesn't exist."""
    schema = """
        CREATE TABLE IF NOT EXISTS watchlist (
            symbol TEXT PRIMARY KEY,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    try:
        with get_db_cursor(sqlite_path=_WATCHLIST_DB_PATH) as (c, conn):
            c.execute(schema)
            conn.commit()
        logger.info("Watchlist Database setup completed successfully.")
    except Exception as exc:
        logger.error("watchlist init_db failed: %s", exc)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def get_symbols() -> list[str]:
    """Return all watchlist symbols."""
    try:
        with get_db_cursor(sqlite_path=_WATCHLIST_DB_PATH) as (c, conn):
            c.execute("SELECT symbol FROM watchlist ORDER BY added_at ASC")
            rows = c.fetchall()
        return [r["symbol"] for r in rows]
    except Exception as exc:
        logger.error("get_symbols failed: %s", exc)
        return []


def add_symbol(symbol: str) -> bool:
    """
    Add a symbol to the watchlist.
    Returns True if added, False if already present or failed.
    """
    symbol = symbol.upper().strip()
    try:
        with get_db_cursor(sqlite_path=_WATCHLIST_DB_PATH) as (c, conn):
            query = q("INSERT INTO watchlist (symbol) VALUES (?)")
            c.execute(query, (symbol,))
            conn.commit()
        logger.info("Watchlist: added %s", symbol)
        return True
    except Exception as exc:
        # Catch integrity violations (duplicate symbols) and fail gracefully
        logger.debug("add_symbol duplicate or failed: %s", exc)
        return False


def remove_symbol(symbol: str) -> bool:
    """
    Remove a symbol from the watchlist.
    Returns True if removed, False if it wasn't there.
    """
    symbol = symbol.upper().strip()
    try:
        with get_db_cursor(sqlite_path=_WATCHLIST_DB_PATH) as (c, conn):
            query = q("DELETE FROM watchlist WHERE symbol = ?")
            c.execute(query, (symbol,))
            conn.commit()
            removed = c.rowcount > 0
        if removed:
            logger.info("Watchlist: removed %s", symbol)
        return removed
    except Exception as exc:
        logger.error("remove_symbol failed: %s", exc)
        return False


def get_watchlist_with_prices() -> list[dict]:
    """
    Return all watchlist symbols with their latest cached price data.
    Uses yahoo_service for live quotes.
    """
    from app.services import yahoo_service   # local import to avoid circular
    symbols = get_symbols()
    result  = []
    for sym in symbols:
        try:
            quote = yahoo_service.get_quote(sym)
            result.append({
                "symbol":     sym,
                "price":      quote.get("current_price"),
                "change":     quote.get("change"),
                "change_pct": quote.get("change_pct"),
                "volume":     quote.get("volume"),
            })
        except Exception as exc:
            logger.warning("Quote fetch failed for watchlist symbol %s: %s", sym, exc)
            result.append({
                "symbol":     sym,
                "price":      None,
                "change":     None,
                "change_pct": None,
                "volume":     None,
                "error":      str(exc),
            })
    return result


# Initialise DB on module import
init_db()
