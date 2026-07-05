"""
History Service
---------------
Stores day-by-day stock snapshots and intraday ticks in SQLite.

Tables:
  daily_snapshot  — one row per symbol per calendar date (end-of-day)
  intraday_ticks  — one row per symbol per refresh during market hours

Automatic saves:
  - During market hours: saved every refresh (via save_intraday_tick)
  - At 3:30 PM IST:      daily snapshot saved (via save_daily_snapshot)
  - Old ticks pruned:    after TICK_RETENTION_DAYS days

DB location: backend/stockgpt.db
"""

import sqlite3
import os
import logging
import threading
from datetime import datetime, date, timedelta

import pytz

logger    = logging.getLogger(__name__)
IST       = pytz.timezone("Asia/Kolkata")
_DB_LOCK  = threading.Lock()

TICK_RETENTION_DAYS = 7     # keep intraday ticks for 7 days
_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "stockgpt.db")
)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")  # better concurrent write performance
    return c


def init_db() -> None:
    """Create tables if they don't exist."""
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS daily_snapshot (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date  DATE    NOT NULL,
                symbol      TEXT    NOT NULL,
                ltp         REAL,
                open        REAL,
                high        REAL,
                low         REAL,
                prev_close  REAL,
                call_oi     INTEGER,
                put_oi      INTEGER,
                pcr         REAL,
                signal      TEXT,
                max_pain    REAL,
                price_chg_pct  REAL,
                UNIQUE(trade_date, symbol)
            );

            CREATE TABLE IF NOT EXISTS intraday_ticks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tick_time   DATETIME NOT NULL,
                trade_date  DATE     NOT NULL,
                symbol      TEXT     NOT NULL,
                ltp         REAL,
                call_oi     INTEGER,
                put_oi      INTEGER,
                pcr         REAL,
                signal      TEXT,
                pcr_change  REAL,
                price_chg_pct REAL
            );

            CREATE INDEX IF NOT EXISTS idx_daily_symbol_date
                ON daily_snapshot(symbol, trade_date);

            CREATE INDEX IF NOT EXISTS idx_tick_symbol_date
                ON intraday_ticks(symbol, trade_date);
        """)
        c.commit()
    logger.info("History DB ready at %s", _DB_PATH)


# ---------------------------------------------------------------------------
# Save functions (called automatically from market_data.py)
# ---------------------------------------------------------------------------

def save_intraday_tick(market_rows: list[dict]) -> None:
    """
    Save one intraday tick for all symbols.
    Called after every successful market data refresh during market hours.
    """
    if not market_rows:
        return

    now        = datetime.now(IST)
    tick_time  = now.strftime("%Y-%m-%d %H:%M:%S")
    trade_date = now.strftime("%Y-%m-%d")

    rows = [
        (
            tick_time,
            trade_date,
            s["symbol"],
            s.get("ltp"),
            s.get("call_oi"),
            s.get("put_oi"),
            s.get("pcr"),
            s.get("signal"),
            s.get("pcr_change"),
            s.get("price_chg_pct"),
        )
        for s in market_rows
        if s.get("ltp", 0) > 0   # skip rows with no live price
    ]

    try:
        with _DB_LOCK:
            with _conn() as c:
                c.executemany("""
                    INSERT INTO intraday_ticks
                        (tick_time, trade_date, symbol, ltp, call_oi, put_oi,
                         pcr, signal, pcr_change, price_chg_pct)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, rows)
                c.commit()
        logger.debug("Saved %d intraday ticks for %s", len(rows), trade_date)
    except Exception as exc:
        logger.error("save_intraday_tick failed: %s", exc)


def save_daily_snapshot(market_rows: list[dict]) -> None:
    """
    Save end-of-day snapshot for all symbols.
    Called once at market close (3:30 PM IST).
    Uses INSERT OR REPLACE so re-running at close is safe.
    """
    if not market_rows:
        return

    trade_date = datetime.now(IST).strftime("%Y-%m-%d")

    rows = [
        (
            trade_date,
            s["symbol"],
            s.get("ltp"),
            s.get("open"),
            s.get("high"),
            s.get("low"),
            s.get("prev_ltp"),   # previous close
            s.get("call_oi"),
            s.get("put_oi"),
            s.get("pcr"),
            s.get("signal"),
            s.get("max_pain"),
            s.get("price_chg_pct"),
        )
        for s in market_rows
        if s.get("ltp", 0) > 0
    ]

    try:
        with _DB_LOCK:
            with _conn() as c:
                c.executemany("""
                    INSERT OR REPLACE INTO daily_snapshot
                        (trade_date, symbol, ltp, open, high, low, prev_close,
                         call_oi, put_oi, pcr, signal, max_pain, price_chg_pct)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, rows)
                c.commit()
        logger.info("Saved daily snapshot for %s (%d symbols)", trade_date, len(rows))
    except Exception as exc:
        logger.error("save_daily_snapshot failed: %s", exc)


def prune_old_ticks() -> None:
    """Delete intraday ticks older than TICK_RETENTION_DAYS."""
    cutoff = (date.today() - timedelta(days=TICK_RETENTION_DAYS)).isoformat()
    try:
        with _DB_LOCK:
            with _conn() as c:
                result = c.execute(
                    "DELETE FROM intraday_ticks WHERE trade_date < ?", (cutoff,)
                )
                c.commit()
        logger.info("Pruned %d old ticks (before %s)", result.rowcount, cutoff)
    except Exception as exc:
        logger.error("prune_old_ticks failed: %s", exc)


# ---------------------------------------------------------------------------
# Query functions (used by history API and export)
# ---------------------------------------------------------------------------

def get_daily_history(symbol: str, days: int = 30) -> list[dict]:
    """
    Return the last `days` daily snapshots for a symbol.
    Ordered oldest → newest.
    """
    symbol = symbol.upper()
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    try:
        with _conn() as c:
            rows = c.execute("""
                SELECT trade_date, symbol, ltp, call_oi, put_oi, pcr,
                       signal, max_pain, price_chg_pct, prev_close
                FROM   daily_snapshot
                WHERE  symbol = ? AND trade_date >= ?
                ORDER  BY trade_date ASC
            """, (symbol, cutoff)).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("get_daily_history failed [%s]: %s", symbol, exc)
        return []


def get_intraday_ticks(symbol: str, trade_date: str = None) -> list[dict]:
    """
    Return intraday ticks for a symbol on a given date (defaults to today).
    """
    symbol     = symbol.upper()
    trade_date = trade_date or datetime.now(IST).strftime("%Y-%m-%d")
    try:
        with _conn() as c:
            rows = c.execute("""
                SELECT tick_time, ltp, pcr, call_oi, put_oi,
                       signal, pcr_change, price_chg_pct
                FROM   intraday_ticks
                WHERE  symbol = ? AND trade_date = ?
                ORDER  BY tick_time ASC
            """, (symbol, trade_date)).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("get_intraday_ticks failed [%s]: %s", symbol, exc)
        return []


def get_all_symbols_history(trade_date: str = None) -> list[dict]:
    """
    Return daily snapshot for ALL symbols on a given date.
    Defaults to today; falls back to most recent available date.
    """
    trade_date = trade_date or datetime.now(IST).strftime("%Y-%m-%d")
    try:
        with _conn() as c:
            # Try exact date first
            rows = c.execute("""
                SELECT * FROM daily_snapshot
                WHERE trade_date = ?
                ORDER BY symbol ASC
            """, (trade_date,)).fetchall()

            if not rows:
                # Fall back to most recent available date
                latest = c.execute(
                    "SELECT MAX(trade_date) as dt FROM daily_snapshot"
                ).fetchone()
                if latest and latest["dt"]:
                    rows = c.execute("""
                        SELECT * FROM daily_snapshot
                        WHERE trade_date = ?
                        ORDER BY symbol ASC
                    """, (latest["dt"],)).fetchall()

        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("get_all_symbols_history failed: %s", exc)
        return []


def get_available_dates() -> list[str]:
    """Return all dates for which we have daily snapshots, newest first."""
    try:
        with _conn() as c:
            rows = c.execute("""
                SELECT DISTINCT trade_date
                FROM   daily_snapshot
                ORDER  BY trade_date DESC
                LIMIT  90
            """).fetchall()
        return [r["trade_date"] for r in rows]
    except Exception as exc:
        logger.error("get_available_dates failed: %s", exc)
        return []


def get_db_stats() -> dict:
    """Return database statistics for the admin endpoint."""
    try:
        with _conn() as c:
            daily_count = c.execute(
                "SELECT COUNT(*) as n FROM daily_snapshot"
            ).fetchone()["n"]
            tick_count = c.execute(
                "SELECT COUNT(*) as n FROM intraday_ticks"
            ).fetchone()["n"]
            dates = c.execute(
                "SELECT COUNT(DISTINCT trade_date) as n FROM daily_snapshot"
            ).fetchone()["n"]
            symbols = c.execute(
                "SELECT COUNT(DISTINCT symbol) as n FROM daily_snapshot"
            ).fetchone()["n"]
        db_size_kb = os.path.getsize(_DB_PATH) // 1024 if os.path.exists(_DB_PATH) else 0
        return {
            "daily_rows":    daily_count,
            "intraday_ticks": tick_count,
            "trading_days":  dates,
            "symbols":       symbols,
            "db_size_kb":    db_size_kb,
            "db_path":       _DB_PATH,
        }
    except Exception as exc:
        return {"error": str(exc)}


# Init on import
init_db()
