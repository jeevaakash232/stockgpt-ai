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
