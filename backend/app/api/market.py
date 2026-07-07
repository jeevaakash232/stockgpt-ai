"""
Market API
----------
GET /api/market
Returns enriched market data for all tracked stocks.
"""

from fastapi import APIRouter, HTTPException
from app.services.market_data import get_market

router = APIRouter()


@router.get("/market", summary="Get live market data")
def market():
    """
    Returns a list of stocks with PCR, signal, OI, LTP and Max Pain.
    """
    try:
        return get_market()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/market/debug")
def market_debug():
    from datetime import date
    from app.utils.db import get_db_cursor
    
    today_str = None
    db_status = "Not Connected"
    max_date = None
    row_count = 0
    error = None
    
    try:
        with get_db_cursor() as (c, conn):
            c.execute("SELECT MAX(trade_date) as dt FROM daily_snapshot")
            row = c.fetchone()
            if row and row["dt"]:
                max_date = str(row["dt"])
                
            c.execute("SELECT COUNT(*) as cnt FROM daily_snapshot")
            row_count = c.fetchone()["cnt"]
            db_status = "Connected"
    except Exception as e:
        error = str(e)
        
    return {
        "server_date_utc": date.today().strftime("%Y-%m-%d"),
        "max_date_in_db": max_date,
        "row_count_in_db": row_count,
        "db_status": db_status,
        "error": error,
        "deploy_signature": "debug_v1"
    }
