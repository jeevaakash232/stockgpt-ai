"""
PCR API
-------
GET /api/pcr
Returns PCR values and sentiment signals for all tracked stocks.
"""

from fastapi import APIRouter, HTTPException
from app.services.market_data import get_market

router = APIRouter()


@router.get("/pcr", summary="Get PCR data for all stocks")
def pcr():
    """
    Returns PCR, Call OI, Put OI and signal for every tracked instrument.
    Uses get_market() as the single data source to avoid duplication.
    """
    try:
        stocks = get_market()
        return [
            {
                "symbol":  s["symbol"],
                "callOI":  s["call_oi"],
                "putOI":   s["put_oi"],
                "PCR":     s["pcr"],
                "signal":  s["signal"],
            }
            for s in stocks
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
