"""
Watchlist API
-------------
GET    /api/watchlist              — Get full watchlist with live prices
POST   /api/watchlist              — Add symbol  { "symbol": "RELIANCE" }
DELETE /api/watchlist/{symbol}     — Remove symbol
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import watchlist_service

router = APIRouter()


class WatchlistAddRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=30)


@router.get("/watchlist", summary="Get watchlist with live prices")
def get_watchlist():
    try:
        return watchlist_service.get_watchlist_with_prices()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/watchlist", status_code=201, summary="Add symbol to watchlist")
def add_to_watchlist(body: WatchlistAddRequest):
    symbol = body.symbol.upper().strip()
    added  = watchlist_service.add_symbol(symbol)
    if not added:
        raise HTTPException(status_code=409, detail=f"{symbol} is already in your watchlist.")
    return {"message": f"{symbol} added to watchlist."}


@router.delete("/watchlist/{symbol}", summary="Remove symbol from watchlist")
def remove_from_watchlist(symbol: str):
    removed = watchlist_service.remove_symbol(symbol.upper())
    if not removed:
        raise HTTPException(status_code=404, detail=f"{symbol} not found in watchlist.")
    return {"message": f"{symbol} removed from watchlist."}
