"""
Option Chain API
----------------
GET /api/option-chain/{symbol}  — Full NSE option chain with PCR, max pain, strikes
"""

from fastapi import APIRouter, HTTPException
from app.services.nse_service import get_option_chain

router = APIRouter()


@router.get("/option-chain/{symbol}", summary="NSE option chain data")
def option_chain(symbol: str, expiry: str = None):
    """
    Returns:
      underlying price, PCR, signal, max pain, call/put OI per strike,
      expiry dates (nearest 5).
    """
    try:
        return get_option_chain(symbol.upper(), expiry)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
