"""
Dashboard API
-------------
GET /api/dashboard              — Full dashboard payload (cached 60 s)
GET /api/top-gainers?limit=25   — Top gaining stocks (default 25, max 50)
GET /api/top-losers?limit=25    — Top losing stocks
GET /api/most-active?limit=25   — Most active by volume
GET /api/indices                — NIFTY, BANKNIFTY, SENSEX, VIX
"""

from fastapi import APIRouter, HTTPException, Query
from app.services.market_service import (
    get_dashboard,
    get_top_gainers,
    get_top_losers,
    get_most_active,
    get_indices,
)

router = APIRouter()


@router.get("/dashboard", summary="Full dashboard payload")
def dashboard():
    try:
        return get_dashboard()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/top-gainers", summary="Top gaining stocks today")
def top_gainers(limit: int = Query(default=25, ge=1, le=50)):
    try:
        return get_top_gainers()[:limit]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/top-losers", summary="Top losing stocks today")
def top_losers(limit: int = Query(default=25, ge=1, le=50)):
    try:
        return get_top_losers()[:limit]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/most-active", summary="Most active stocks by volume")
def most_active(limit: int = Query(default=25, ge=1, le=50)):
    try:
        return get_most_active()[:limit]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/indices", summary="NIFTY, BANKNIFTY, SENSEX, India VIX")
def indices():
    try:
        return get_indices()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
