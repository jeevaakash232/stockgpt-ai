"""
Stock Detail API
----------------
GET /api/stock/{symbol}   — Full quote + PCR + OI + support/resistance
GET /api/search?q=        — Symbol search suggestions
"""

from fastapi import APIRouter, HTTPException, Query
from app.services.market_service import get_stock_detail
from app.services.yahoo_service  import search_symbols

router = APIRouter()


@router.get("/stock/{symbol}", summary="Full stock detail")
def stock_detail(symbol: str):
    """
    Returns:
      current_price, OHLCV, 52-week high/low, market cap,
      PCR, call OI, put OI, max pain, support, resistance, pivot
    """
    try:
        return get_stock_detail(symbol.upper())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/search", summary="Search NSE symbols")
def search(q: str = Query("", min_length=1, max_length=20)):
    """
    Returns up to 10 symbol suggestions matching the query string.
    """
    try:
        return search_symbols(q)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
