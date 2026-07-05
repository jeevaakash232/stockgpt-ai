"""
Watchlist Service
-----------------
Manages a per-process in-memory watchlist.
Symbols are stored in a set; live prices are fetched via yahoo_service.

For persistence across restarts, this uses a local SQLite file
(watchlist.db) via Python's built-in sqlite3 — no ORM required,
no extra dependencies.
"""

import sqlite3
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# DB file lives next to this service file (backend/app/services/)
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "watchlist.db")
_DB_PATH = os.path.abspath(_DB_PATH)


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the watchlist table if it doesn't exist."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                symbol TEXT PRIMARY KEY,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    logger.info("Watchlist DB ready at %s", _DB_PATH)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def get_symbols() -> list[str]:
    """Return all watchlist symbols."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT symbol FROM watchlist ORDER BY added_at ASC"
        ).fetchall()
    return [r["symbol"] for r in rows]


def add_symbol(symbol: str) -> bool:
    """
    Add a symbol to the watchlist.
    Returns True if added, False if already present.
    """
    symbol = symbol.upper().strip()
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO watchlist (symbol) VALUES (?)", (symbol,)
            )
            conn.commit()
        logger.info("Watchlist: added %s", symbol)
        return True
    except sqlite3.IntegrityError:
        return False  # already exists


def remove_symbol(symbol: str) -> bool:
    """
    Remove a symbol from the watchlist.
    Returns True if removed, False if it wasn't there.
    """
    symbol = symbol.upper().strip()
    with _get_conn() as conn:
        cursor = conn.execute(
            "DELETE FROM watchlist WHERE symbol = ?", (symbol,)
        )
        conn.commit()
    removed = cursor.rowcount > 0
    if removed:
        logger.info("Watchlist: removed %s", symbol)
    return removed


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
