import logging
import pandas as pd
from datetime import date
from sqlalchemy import text

logger = logging.getLogger(__name__)

def get_fo_bhavcopy_data(db, symbol: str, trading_date: date, expiry_date: date = None) -> pd.DataFrame:
    """
    Query F&O Bhavcopy data from database for a specific trading date.
    Returns a Pandas DataFrame.
    """
    symbol = symbol.upper()
    try:
        if expiry_date:
            sql = """
                SELECT * FROM fo_bhavcopy 
                WHERE symbol = :symbol 
                  AND trading_date = :trading_date 
                  AND expiry_date = :expiry_date
                ORDER BY strike_price ASC
            """
            params = {"symbol": symbol, "trading_date": trading_date, "expiry_date": expiry_date}
        else:
            sql = """
                SELECT * FROM fo_bhavcopy 
                WHERE symbol = :symbol 
                  AND trading_date = :trading_date
                ORDER BY strike_price ASC
            """
            params = {"symbol": symbol, "trading_date": trading_date}
            
        res = db.execute(text(sql), params)
        rows = res.mappings().all()
        return pd.DataFrame(rows)
    except Exception as e:
        logger.error("get_fo_bhavcopy_data failed: %s", e)
        return pd.DataFrame()


def get_live_option_chain_data(db, symbol: str, expiry_date: date = None) -> pd.DataFrame:
    """
    Fetch the most recent live option chain records from database.
    """
    symbol = symbol.upper()
    try:
        # Find the latest fetch time for this symbol
        time_sql = "SELECT MAX(fetch_time) as max_time FROM option_chain_live WHERE symbol = :symbol"
        max_time = db.execute(text(time_sql), {"symbol": symbol}).scalar()
        
        if not max_time:
            return pd.DataFrame()

        if expiry_date:
            sql = """
                SELECT * FROM option_chain_live 
                WHERE symbol = :symbol 
                  AND fetch_time = :fetch_time 
                  AND expiry_date = :expiry_date
                ORDER BY strike_price ASC
            """
            params = {"symbol": symbol, "fetch_time": max_time, "expiry_date": expiry_date}
        else:
            sql = """
                SELECT * FROM option_chain_live 
                WHERE symbol = :symbol 
                  AND fetch_time = :fetch_time
                ORDER BY strike_price ASC
            """
            params = {"symbol": symbol, "fetch_time": max_time}
            
        res = db.execute(text(sql), params)
        rows = res.mappings().all()
        return pd.DataFrame(rows)
    except Exception as e:
        logger.error("get_live_option_chain_data failed: %s", e)
        return pd.DataFrame()


def get_available_expiries(db, symbol: str) -> list[date]:
    """
    Retrieve expiry dates for a symbol.
    """
    symbol = symbol.upper()
    try:
        sql = "SELECT DISTINCT expiry_date FROM expiry_dates WHERE symbol = :symbol ORDER BY expiry_date ASC"
        res = db.execute(text(sql), {"symbol": symbol})
        return [row[0] for row in res.all()]
    except Exception as e:
        logger.error("get_available_expiries failed: %s", e)
        return []


def is_holiday(db, date_val: date) -> bool:
    """
    Check if a date is listed as an NSE holiday.
    """
    try:
        sql = "SELECT is_holiday FROM trading_calendar WHERE calendar_date = :date_val"
        res = db.execute(text(sql), {"date_val": date_val}).scalar()
        return bool(res)
    except Exception as e:
        logger.error("is_holiday check failed: %s", e)
        # Fallback: check standard Saturday/Sunday
        return date_val.weekday() >= 5


def get_last_available_trading_date(db) -> date:
    """
    Find the most recent date we have F&O Bhavcopy records for.
    """
    try:
        sql = "SELECT MAX(trading_date) FROM fo_bhavcopy"
        res = db.execute(text(sql)).scalar()
        if res:
            return res if isinstance(res, date) else pd.to_datetime(res).date()
    except Exception as e:
        logger.error("get_last_available_trading_date failed: %s", e)
    return date.today()
