"""
History Service
---------------
Stores day-by-day stock snapshots and intraday ticks in SQLite or PostgreSQL.
"""

import os
import logging
import threading
from datetime import datetime, date, timedelta
import pytz

from app.utils.db import get_db_cursor, q, is_postgres

logger    = logging.getLogger(__name__)
IST       = pytz.timezone("Asia/Kolkata")
_DB_LOCK  = threading.Lock()

TICK_RETENTION_DAYS = 7     # keep intraday ticks for 7 days


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables if they don't exist."""
    if is_postgres():
        schema = """
            CREATE TABLE IF NOT EXISTS daily_snapshot (
                id             SERIAL PRIMARY KEY,
                trade_date     DATE    NOT NULL,
                symbol         TEXT    NOT NULL,
                ltp            DOUBLE PRECISION,
                open           DOUBLE PRECISION,
                high           DOUBLE PRECISION,
                low            DOUBLE PRECISION,
                prev_close     DOUBLE PRECISION,
                call_oi        BIGINT,
                put_oi         BIGINT,
                pcr            DOUBLE PRECISION,
                signal         TEXT,
                max_pain       DOUBLE PRECISION,
                price_chg_pct  DOUBLE PRECISION,
                UNIQUE(trade_date, symbol)
            );

            CREATE TABLE IF NOT EXISTS intraday_ticks (
                id             SERIAL PRIMARY KEY,
                tick_time      TIMESTAMP NOT NULL,
                trade_date     DATE     NOT NULL,
                symbol         TEXT     NOT NULL,
                ltp            DOUBLE PRECISION,
                call_oi        BIGINT,
                put_oi         BIGINT,
                pcr            DOUBLE PRECISION,
                signal         TEXT,
                pcr_change     DOUBLE PRECISION,
                price_chg_pct  DOUBLE PRECISION
            );

            CREATE INDEX IF NOT EXISTS idx_daily_symbol_date
                ON daily_snapshot(symbol, trade_date);

            CREATE INDEX IF NOT EXISTS idx_tick_symbol_date
                ON intraday_ticks(symbol, trade_date);
        """
    else:
        schema = """
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
        """

    try:
        with get_db_cursor() as (c, conn):
            # For multi-statement schema in PostgreSQL we execute directly
            if is_postgres():
                c.execute(schema)
            else:
                # sqlite3 allows executescript on connection or cursor, but cursor.executescript is not standard.
                # In sqlite3, executing standard multi-statement is safe through connection executescript
                conn.executescript(schema)
            conn.commit()
        logger.info("History Database setup completed successfully.")
    except Exception as exc:
        logger.error("init_db failed: %s", exc)


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
            with get_db_cursor() as (c, conn):
                query = q("""
                    INSERT INTO intraday_ticks
                        (tick_time, trade_date, symbol, ltp, call_oi, put_oi,
                         pcr, signal, pcr_change, price_chg_pct)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """)
                c.executemany(query, rows)
                conn.commit()
        logger.debug("Saved %d intraday ticks for %s", len(rows), trade_date)
    except Exception as exc:
        logger.error("save_intraday_tick failed: %s", exc)


def save_daily_snapshot(market_rows: list[dict]) -> None:
    """
    Save end-of-day snapshot for all symbols.
    Called once at market close (3:30 PM IST).
    """
    if not market_rows:
        return

    trade_date = datetime.now(IST).strftime("%Y-%m-%d")

    rows = [
        (
            trade_date,
            s["symbol"],
            s.get("ltp"),
            s.get("open") or s.get("ltp"),
            s.get("high") or s.get("ltp"),
            s.get("low") or s.get("ltp"),
            s.get("prev_close") or s.get("prev_ltp"),   # previous close
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
            with get_db_cursor() as (c, conn):
                if is_postgres():
                    query = """
                        INSERT INTO daily_snapshot
                            (trade_date, symbol, ltp, open, high, low, prev_close,
                             call_oi, put_oi, pcr, signal, max_pain, price_chg_pct)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (trade_date, symbol) DO UPDATE SET
                            ltp = EXCLUDED.ltp,
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            prev_close = EXCLUDED.prev_close,
                            call_oi = EXCLUDED.call_oi,
                            put_oi = EXCLUDED.put_oi,
                            pcr = EXCLUDED.pcr,
                            signal = EXCLUDED.signal,
                            max_pain = EXCLUDED.max_pain,
                            price_chg_pct = EXCLUDED.price_chg_pct
                    """
                else:
                    query = """
                        INSERT OR REPLACE INTO daily_snapshot
                            (trade_date, symbol, ltp, open, high, low, prev_close,
                             call_oi, put_oi, pcr, signal, max_pain, price_chg_pct)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """
                c.executemany(query, rows)
                conn.commit()
        logger.info("Saved daily snapshot for %s (%d symbols)", trade_date, len(rows))
    except Exception as exc:
        logger.error("save_daily_snapshot failed: %s", exc)


def prune_old_ticks() -> None:
    """Delete intraday ticks older than TICK_RETENTION_DAYS."""
    cutoff = (date.today() - timedelta(days=TICK_RETENTION_DAYS)).isoformat()
    try:
        with _DB_LOCK:
            with get_db_cursor() as (c, conn):
                c.execute(
                    q("DELETE FROM intraday_ticks WHERE trade_date < ?"), (cutoff,)
                )
                conn.commit()
                rowcount = c.rowcount
        logger.info("Pruned %d old ticks (before %s)", rowcount, cutoff)
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
        with get_db_cursor() as (c, conn):
            query = q("""
                SELECT trade_date, symbol, ltp, call_oi, put_oi, pcr,
                       signal, max_pain, price_chg_pct, prev_close
                FROM   daily_snapshot
                WHERE  symbol = ? AND trade_date >= ?
                ORDER  BY trade_date ASC
            """)
            c.execute(query, (symbol, cutoff))
            rows = c.fetchall()
        
        # Convert date column to string for consistent API format across database engines
        result = []
        for r in rows:
            d = dict(r)
            if hasattr(d.get("trade_date"), "isoformat"):
                d["trade_date"] = d["trade_date"].isoformat()
            result.append(d)
        return result
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
        with get_db_cursor() as (c, conn):
            query = q("""
                SELECT tick_time, ltp, pcr, call_oi, put_oi,
                       signal, pcr_change, price_chg_pct
                FROM   intraday_ticks
                WHERE  symbol = ? AND trade_date = ?
                ORDER  BY tick_time ASC
            """)
            c.execute(query, (symbol, trade_date))
            rows = c.fetchall()
        
        # Convert tick_time to string for consistent API format
        result = []
        for r in rows:
            d = dict(r)
            if hasattr(d.get("tick_time"), "strftime"):
                d["tick_time"] = d["tick_time"].strftime("%Y-%m-%d %H:%M:%S")
            result.append(d)
        return result
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
        with get_db_cursor() as (c, conn):
            # Try exact date first
            query = q("""
                SELECT * FROM daily_snapshot
                WHERE trade_date = ?
                ORDER BY symbol ASC
            """)
            c.execute(query, (trade_date,))
            rows = c.fetchall()

            if not rows:
                # Fall back to most recent available date
                c.execute("SELECT MAX(trade_date) as dt FROM daily_snapshot")
                latest = c.fetchone()
                if latest and latest["dt"]:
                    c.execute(q("""
                        SELECT * FROM daily_snapshot
                        WHERE trade_date = ?
                        ORDER BY symbol ASC
                    """), (latest["dt"],))
                    rows = c.fetchall()

        result = []
        for r in rows:
            d = dict(r)
            if hasattr(d.get("trade_date"), "isoformat"):
                d["trade_date"] = d["trade_date"].isoformat()
            result.append(d)
        return result
    except Exception as exc:
        logger.error("get_all_symbols_history failed: %s", exc)
        return []


def get_previous_day_snapshot() -> dict:
    """
    Return a map of symbol -> snapshot_dict for the most recent trading date before the latest date.
    """
    try:
        with get_db_cursor() as (c, conn):
            # Find the latest date overall
            c.execute("SELECT MAX(trade_date) as dt FROM daily_snapshot")
            row = c.fetchone()
            if not row or not row["dt"]:
                return {}
            latest_date = row["dt"]

            # Find the most recent date strictly before the latest date
            c.execute(q("SELECT MAX(trade_date) as dt FROM daily_snapshot WHERE trade_date < ?"), (latest_date,))
            row = c.fetchone()

            if not row or not row["dt"]:
                return {}

            prev_date = row["dt"]

            # Fetch snapshots for that date
            c.execute(q("""
                SELECT symbol, ltp, call_oi, put_oi, pcr, signal, max_pain, prev_close 
                FROM daily_snapshot WHERE trade_date = ?
            """), (prev_date,))
            rows = c.fetchall()

            return {
                r["symbol"]: {
                    "pcr": r["pcr"],
                    "call_oi": r["call_oi"],
                    "put_oi": r["put_oi"],
                    "ltp": r["ltp"],
                    "prev_close": r["prev_close"],
                    "max_pain": r["max_pain"]
                }
                for r in rows
            }
    except Exception as exc:
        logger.error("get_previous_day_snapshot failed: %s", exc)
        return {}


def get_available_dates() -> list[str]:
    """Return all dates for which we have daily snapshots, newest first."""
    try:
        with get_db_cursor() as (c, conn):
            c.execute("""
                SELECT DISTINCT trade_date
                FROM   daily_snapshot
                ORDER  BY trade_date DESC
                LIMIT  90
            """)
            rows = c.fetchall()
            
        dates = []
        for r in rows:
            val = r["trade_date"]
            if hasattr(val, "isoformat"):
                dates.append(val.isoformat())
            else:
                dates.append(str(val))
        return dates
    except Exception as exc:
        logger.error("get_available_dates failed: %s", exc)
        return []


def get_db_stats() -> dict:
    """Return database statistics for the admin endpoint."""
    try:
        with get_db_cursor() as (c, conn):
            c.execute("SELECT COUNT(*) as n FROM daily_snapshot")
            daily_count = c.fetchone()["n"]
            
            c.execute("SELECT COUNT(*) as n FROM intraday_ticks")
            tick_count = c.fetchone()["n"]
            
            c.execute("SELECT COUNT(DISTINCT trade_date) as n FROM daily_snapshot")
            dates = c.fetchone()["n"]
            
            c.execute("SELECT COUNT(DISTINCT symbol) as n FROM daily_snapshot")
            symbols = c.fetchone()["n"]
            
        if is_postgres():
            db_size_kb = 0
            db_path = "PostgreSQL cloud database"
        else:
            from app.utils.db import _DB_PATH
            db_size_kb = os.path.getsize(_DB_PATH) // 1024 if os.path.exists(_DB_PATH) else 0
            db_path = _DB_PATH
            
        return {
            "daily_rows":    daily_count,
            "intraday_ticks": tick_count,
            "trading_days":  dates,
            "symbols":       symbols,
            "db_size_kb":    db_size_kb,
            "db_path":       db_path,
        }
    except Exception as exc:
        return {"error": str(exc)}


def import_real_eod_bhavcopy(target_date_str: str) -> bool:
    """
    Downloads the real UDiFF F&O Bhavcopy for target_date_str from NSE,
    aggregates option data (Call OI, Put OI, PCR, Max Pain),
    and saves them directly into daily_snapshot table.
    """
    import requests
    import zipfile
    import io
    import pandas as pd
    
    url = f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{target_date_str.replace('-', '')}_F_0000.csv.zip"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    logger.info("Attempting to download real UDiFF EOD Bhavcopy for %s...", target_date_str)
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            logger.warning("Real EOD UDiFF Bhavcopy not available yet (HTTP %d)", r.status_code)
            return False
            
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            names = z.namelist()
            with z.open(names[0]) as f:
                df = pd.read_csv(f)
                df.columns = [c.strip() for c in df.columns]
                
        # Filter for valid F&O instruments
        df = df[df["FinInstrmTp"].isin(["STO", "STF", "IDO", "IDF"])]
        df["TckrSymb"] = df["TckrSymb"].str.strip()
        df["OptnTp"] = df["OptnTp"].fillna("XX").str.strip()
        
        symbols = df["TckrSymb"].unique()
        snapshot_rows = []
        
        for sym in symbols:
            sym_df = df[df["TckrSymb"] == sym]
            
            # Calculate Call/Put OI
            call_oi = int(sym_df[sym_df["OptnTp"] == "CE"]["OpnIntrst"].sum())
            put_oi = int(sym_df[sym_df["OptnTp"] == "PE"]["OpnIntrst"].sum())
            
            pcr = round(put_oi / call_oi, 2) if call_oi > 0 else 1.0
            signal = "Bullish" if pcr >= 1.0 else "Neutral" if pcr >= 0.75 else "Bearish"
            
            # Find closing price from Futures as LTP
            fut_df = sym_df[sym_df["FinInstrmTp"].isin(["STF", "IDF"])]
            if not fut_df.empty:
                ltp = float(fut_df.iloc[0]["ClsPric"])
                open_p = float(fut_df.iloc[0]["OpnPric"]) if pd.notnull(fut_df.iloc[0]["OpnPric"]) and fut_df.iloc[0]["OpnPric"] > 0 else ltp
                high = float(fut_df.iloc[0]["HghPric"]) if pd.notnull(fut_df.iloc[0]["HghPric"]) and fut_df.iloc[0]["HghPric"] > 0 else ltp
                low = float(fut_df.iloc[0]["LwPric"]) if pd.notnull(fut_df.iloc[0]["LwPric"]) and fut_df.iloc[0]["LwPric"] > 0 else ltp
            else:
                ltp = float(sym_df.iloc[0]["ClsPric"]) if not sym_df.empty else 0.0
                open_p = ltp
                high = ltp
                low = ltp
                
            # Max Pain
            opt_df = sym_df[sym_df["FinInstrmTp"].isin(["STO", "IDO"])]
            if not opt_df.empty:
                max_pain = float(opt_df.loc[opt_df["OpnIntrst"].idxmax()]["StrkPric"])
            else:
                max_pain = 0.0
                
            snapshot_rows.append((
                target_date_str,
                sym,
                ltp,
                open_p,
                high,
                low,
                open_p,  # prev_close fallback
                call_oi,
                put_oi,
                pcr,
                signal,
                max_pain,
                0.0      # price_chg_pct
            ))
            
        with _DB_LOCK:
            with get_db_cursor() as (c, conn):
                # Delete existing records for today
                c.execute(q("DELETE FROM daily_snapshot WHERE trade_date = ?"), (target_date_str,))
                
                # Bulk insert daily snapshots
                query_snap = q("""
                    INSERT INTO daily_snapshot
                        (trade_date, symbol, ltp, open, high, low, prev_close,
                         call_oi, put_oi, pcr, signal, max_pain, price_chg_pct)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """)
                c.executemany(query_snap, snapshot_rows)
                
                # Recalculate price change percentages for this date
                c.execute(q("SELECT DISTINCT trade_date FROM daily_snapshot WHERE trade_date < ? ORDER BY trade_date DESC LIMIT 1"), (target_date_str,))
                prev_row = c.fetchone()
                
                if prev_row:
                    prev_date_val = prev_row[0] if isinstance(prev_row, tuple) else prev_row.get("trade_date")
                    prev_date_str = prev_date_val.strftime("%Y-%m-%d") if hasattr(prev_date_val, "strftime") else str(prev_date_val)
                    
                    c.execute(q("SELECT symbol, ltp FROM daily_snapshot WHERE trade_date = ?"), (prev_date_str,))
                    prev_ltps = {r[0] if isinstance(r, tuple) else r.get("symbol"): r[1] if isinstance(r, tuple) else r.get("ltp") for r in c.fetchall()}
                    
                    # Update snapshots
                    for r in snapshot_rows:
                        sym = r[1]
                        ltp = r[2]
                        prev_close = prev_ltps.get(sym) or r[3] or ltp
                        price_chg = round(((ltp - prev_close) / prev_close) * 100, 2) if prev_close > 0 else 0.0
                        c.execute(q("""
                            UPDATE daily_snapshot
                            SET prev_close = ?, price_chg_pct = ?
                            WHERE trade_date = ? AND symbol = ?
                        """), (prev_close, price_chg, target_date_str, sym))
                        
        logger.info("Successfully imported and recalculated real EOD Bhavcopy for %s.", target_date_str)
        return True
    except Exception as exc:
        logger.error("Failed to import real EOD Bhavcopy for %s: %s", target_date_str, exc)
        return False


# Init on import
init_db()
