import logging
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from database.connection import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/expiry", summary="Get F&O contract expiry dates")
def get_expiry(symbol: str, db: Session = Depends(get_db)):
    """
    Returns unique expiry dates stored in PostgreSQL for the symbol.
    """
    try:
        sql = "SELECT DISTINCT expiry_date FROM expiry_dates WHERE symbol = :symbol ORDER BY expiry_date ASC"
        res = db.execute(text(sql), {"symbol": symbol.upper()})
        dates = [row[0].isoformat() for row in res.all()]
        return {"symbol": symbol.upper(), "expiry_dates": dates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/option-chain", summary="Get live option chain from database")
def get_option_chain(symbol: str, expiry: str = None, db: Session = Depends(get_db)):
    """
    Returns latest option chain snapshot stored in PostgreSQL.
    """
    symbol = symbol.upper()
    try:
        # Find the latest fetch time for this symbol
        time_sql = "SELECT MAX(fetch_time) FROM option_chain_live WHERE symbol = :symbol"
        max_time = db.execute(text(time_sql), {"symbol": symbol}).scalar()
        if not max_time:
            return {"symbol": symbol, "data": [], "message": "No live option chain logged yet"}
            
        if expiry:
            sql = """
                SELECT * FROM option_chain_live 
                WHERE symbol = :symbol AND fetch_time = :max_time AND expiry_date = :expiry
                ORDER BY strike_price ASC
            """
            res = db.execute(text(sql), {"symbol": symbol, "max_time": max_time, "expiry": expiry})
        else:
            sql = """
                SELECT * FROM option_chain_live 
                WHERE symbol = :symbol AND fetch_time = :max_time
                ORDER BY strike_price ASC
            """
            res = db.execute(text(sql), {"symbol": symbol, "max_time": max_time})
            
        rows = [dict(row) for row in res.mappings().all()]
        # Convert datetime objects to ISO strings
        for row in rows:
            row["fetch_time"] = row["fetch_time"].isoformat()
            row["expiry_date"] = row["expiry_date"].isoformat()
            
        return {
            "symbol": symbol,
            "fetch_time": max_time.isoformat(),
            "expiry": expiry,
            "strikes": rows
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pcr", summary="Get daily PCR by Open Interest")
def get_pcr(symbol: str, trading_date: str = None, db: Session = Depends(get_db)):
    """
    Query PCR calculation for a symbol and date (default latest) from daily_pcr view.
    """
    try:
        if not trading_date:
            sql = "SELECT MAX(trading_date) FROM daily_pcr WHERE symbol = :symbol"
            trading_date = db.execute(text(sql), {"symbol": symbol.upper()}).scalar()
            if not trading_date:
                return {"symbol": symbol, "pcr": 0.0, "message": "No data found"}
                
        sql = "SELECT pcr FROM daily_pcr WHERE symbol = :symbol AND trading_date = :date_val LIMIT 1"
        pcr = db.execute(text(sql), {"symbol": symbol.upper(), "date_val": trading_date}).scalar()
        return {
            "symbol": symbol.upper(),
            "trading_date": trading_date.isoformat() if hasattr(trading_date, "isoformat") else trading_date,
            "pcr": float(pcr) if pcr else 0.0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mean-pcr", summary="Get mean market PCR trend")
def get_mean_pcr(limit: int = 5, db: Session = Depends(get_db)):
    """
    Query overall market mean PCR trend from daily_mean_pcr view.
    """
    try:
        sql = "SELECT * FROM daily_mean_pcr ORDER BY trading_date DESC LIMIT :limit"
        res = db.execute(text(sql), {"limit": limit})
        rows = [
            {"trading_date": r[0].isoformat(), "mean_market_pcr": float(r[1] or 0.0)}
            for r in res.all()
        ]
        return {"mean_pcr_history": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/support", summary="Get option support wall")
def get_support(symbol: str, expiry: str = None, db: Session = Depends(get_db)):
    """
    Query estimated support level (max Put OI strike price) from database.
    """
    try:
        sql = "SELECT support FROM daily_analytics WHERE symbol = :symbol"
        params = {"symbol": symbol.upper()}
        if expiry:
            sql += " AND expiry_date = :expiry"
            params["expiry"] = expiry
        sql += " ORDER BY analysis_date DESC LIMIT 1"
        
        support = db.execute(text(sql), params).scalar()
        return {"symbol": symbol.upper(), "support": float(support) if support else 0.0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resistance", summary="Get option resistance wall")
def get_resistance(symbol: str, expiry: str = None, db: Session = Depends(get_db)):
    """
    Query estimated resistance level (max Call OI strike price) from database.
    """
    try:
        sql = "SELECT resistance FROM daily_analytics WHERE symbol = :symbol"
        params = {"symbol": symbol.upper()}
        if expiry:
            sql += " AND expiry_date = :expiry"
            params["expiry"] = expiry
        sql += " ORDER BY analysis_date DESC LIMIT 1"
        
        resistance = db.execute(text(sql), params).scalar()
        return {"symbol": symbol.upper(), "resistance": float(resistance) if resistance else 0.0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/max-pain", summary="Get max pain strike price")
def get_max_pain(symbol: str, expiry: str = None, db: Session = Depends(get_db)):
    """
    Query calculated max pain strike from the database.
    """
    try:
        sql = "SELECT max_pain FROM daily_analytics WHERE symbol = :symbol"
        params = {"symbol": symbol.upper()}
        if expiry:
            sql += " AND expiry_date = :expiry"
            params["expiry"] = expiry
        sql += " ORDER BY analysis_date DESC LIMIT 1"
        
        mp = db.execute(text(sql), params).scalar()
        return {"symbol": symbol.upper(), "max_pain": float(mp) if mp else 0.0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics", summary="Get F&O analytics by date range/parameters")
def get_analytics(
    symbol: str,
    range_type: str = Query("last5", enum=["today", "yesterday", "last5", "last30", "custom"]),
    custom_date: str = None,
    expiry: str = None,
    db: Session = Depends(get_db)
):
    """
    Module 7: Historical F&O Analytics query.
    Allows range queries based on database calculations.
    """
    symbol = symbol.upper()
    try:
        # Base query
        sql = "SELECT * FROM daily_analytics WHERE symbol = :symbol"
        params = {"symbol": symbol}
        
        if expiry:
            sql += " AND expiry_date = :expiry"
            params["expiry"] = expiry

        # Date range filtering
        if range_type == "today":
            sql += " AND analysis_date = CURRENT_DATE"
        elif range_type == "yesterday":
            sql += " AND analysis_date = CURRENT_DATE - 1"
        elif range_type == "last5":
            sql += " AND analysis_date >= CURRENT_DATE - 5"
        elif range_type == "last30":
            sql += " AND analysis_date >= CURRENT_DATE - 30"
        elif range_type == "custom" and custom_date:
            sql += " AND analysis_date = :custom_date"
            params["custom_date"] = custom_date
            
        sql += " ORDER BY analysis_date DESC"
        
        res = db.execute(text(sql), params)
        rows = [dict(row) for row in res.mappings().all()]
        
        # Convert date types to strings
        for row in rows:
            row["analysis_date"] = row["analysis_date"].isoformat()
            row["expiry_date"] = row["expiry_date"].isoformat()
            row["created_at"] = row["created_at"].isoformat() if row.get("created_at") else None
            
        return {"symbol": symbol, "range": range_type, "records": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-summary", summary="Get overall market F&O summary status")
def get_market_summary(db: Session = Depends(get_db)):
    """
    Retrieve latest general market F&O aggregate statistics.
    """
    try:
        sql = "SELECT * FROM market_summary ORDER BY summary_date DESC LIMIT 1"
        row = db.execute(text(sql)).mappings().first()
        if not row:
            return {"message": "No summaries compiled yet"}
        ret = dict(row)
        ret["summary_date"] = ret["summary_date"].isoformat()
        ret["created_at"] = ret["created_at"].isoformat()
        return ret
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
