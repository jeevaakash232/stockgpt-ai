import logging
import pandas as pd
from sqlalchemy import text
from database.connection import engine

logger = logging.getLogger(__name__)

def bulk_insert_bhavcopy(db, df: pd.DataFrame) -> int:
    """
    Highly efficient bulk insert of F&O Bhavcopy records.
    Uses PostgreSQL execute_values / ON CONFLICT DO NOTHING,
    falling back to SQLite INSERT OR IGNORE locally.
    """
    if df.empty:
        return 0

    columns = [
        "trading_date", "symbol", "instrument", "expiry_date", "strike_price",
        "option_type", "open", "high", "low", "close", "settle_price",
        "contracts", "value", "open_interest", "change_in_oi", "timestamp"
    ]
    
    # Format data for database compatibility
    df_data = df[columns].copy()
    
    # Replace NaN/NaT values with None
    df_data = df_data.replace({pd.NA: None, pd.NaT: None})
    df_data = df_data.where(pd.notnull(df_data), None)
    
    # Convert dates to ISO strings
    for col in ["trading_date", "expiry_date", "timestamp"]:
        df_data[col] = df_data[col].apply(lambda x: x.strftime("%Y-%m-%d") if hasattr(x, "strftime") else x)

    values = df_data.values.tolist()
    dialect = engine.dialect.name
    
    try:
        if dialect == "postgresql":
            # Direct raw psycopg2 execute_values for maximum throughput
            from psycopg2.extras import execute_values
            raw_conn = db.connection().connection
            cursor = raw_conn.cursor()
            
            sql = """
                INSERT INTO fo_bhavcopy (
                    trading_date, symbol, instrument, expiry_date, strike_price,
                    option_type, open, high, low, close, settle_price,
                    contracts, value, open_interest, change_in_oi, timestamp
                ) VALUES %s
                ON CONFLICT (trading_date, symbol, instrument, expiry_date, strike_price, option_type) 
                DO NOTHING
            """
            execute_values(cursor, sql, values)
            db.commit()
            rowcount = cursor.rowcount
            cursor.close()
            return rowcount
        else:
            # SQLite fallback insert
            placeholders = ",".join(["?"] * len(columns))
            sql = f"""
                INSERT OR IGNORE INTO fo_bhavcopy (
                    {",".join(columns)}
                ) VALUES ({placeholders})
            """
            raw_conn = db.connection().connection
            cursor = raw_conn.cursor()
            cursor.executemany(sql, values)
            db.commit()
            rowcount = cursor.rowcount
            cursor.close()
            return rowcount
    except Exception as e:
        db.rollback()
        logger.error("bulk_insert_bhavcopy failed: %s", e)
        raise e


def bulk_insert_live_option_chain(db, rows: list[dict]) -> int:
    """
    Bulk insert live option chain ticks.
    """
    if not rows:
        return 0

    columns = [
        "fetch_time", "symbol", "expiry_date", "strike_price",
        "call_oi", "call_change_oi", "call_volume", "call_ltp", "call_iv",
        "put_oi", "put_change_oi", "put_volume", "put_ltp", "put_iv"
    ]

    values = []
    for r in rows:
        values.append([
            r.get("fetch_time"), r.get("symbol"), r.get("expiry_date"), r.get("strike_price"),
            r.get("call_oi"), r.get("call_change_oi"), r.get("call_volume"), r.get("call_ltp"), r.get("call_iv"),
            r.get("put_oi"), r.get("put_change_oi"), r.get("put_volume"), r.get("put_ltp"), r.get("put_iv")
        ])

    dialect = engine.dialect.name
    try:
        if dialect == "postgresql":
            from psycopg2.extras import execute_values
            raw_conn = db.connection().connection
            cursor = raw_conn.cursor()
            sql = """
                INSERT INTO option_chain_live (
                    fetch_time, symbol, expiry_date, strike_price,
                    call_oi, call_change_oi, call_volume, call_ltp, call_iv,
                    put_oi, put_change_oi, put_volume, put_ltp, put_iv
                ) VALUES %s
                ON CONFLICT (fetch_time, symbol, expiry_date, strike_price) 
                DO NOTHING
            """
            execute_values(cursor, sql, values)
            db.commit()
            rowcount = cursor.rowcount
            cursor.close()
            return rowcount
        else:
            placeholders = ",".join(["?"] * len(columns))
            sql = f"""
                INSERT OR IGNORE INTO option_chain_live (
                    {",".join(columns)}
                ) VALUES ({placeholders})
            """
            raw_conn = db.connection().connection
            cursor = raw_conn.cursor()
            cursor.executemany(sql, values)
            db.commit()
            rowcount = cursor.rowcount
            cursor.close()
            return rowcount
    except Exception as e:
        db.rollback()
        logger.error("bulk_insert_live_option_chain failed: %s", e)
        raise e


def insert_expiry_dates(db, symbol: str, expiries: list) -> int:
    """
    Insert expiry dates avoiding duplicates.
    """
    if not expiries:
        return 0

    dialect = engine.dialect.name
    inserted = 0
    try:
        for exp in expiries:
            exp_str = exp.strftime("%Y-%m-%d") if hasattr(exp, "strftime") else exp
            if dialect == "postgresql":
                sql = """
                    INSERT INTO expiry_dates (symbol, expiry_date)
                    VALUES (:symbol, :expiry_date)
                    ON CONFLICT (symbol, expiry_date) DO NOTHING
                """
                res = db.execute(text(sql), {"symbol": symbol, "expiry_date": exp_str})
                inserted += res.rowcount
            else:
                sql = """
                    INSERT OR IGNORE INTO expiry_dates (symbol, expiry_date)
                    VALUES (:symbol, :expiry_date)
                """
                res = db.execute(text(sql), {"symbol": symbol, "expiry_date": exp_str})
                inserted += res.rowcount
        db.commit()
        return inserted
    except Exception as e:
        db.rollback()
        logger.error("insert_expiry_dates failed for %s: %s", symbol, e)
        raise e
