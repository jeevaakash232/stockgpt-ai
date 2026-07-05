"""
Chat API
--------
POST /api/chat
Accepts a question, fetches live market data, queries the AI, returns the answer.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.market_data import get_market
from app.services.ai_service   import ask_ai

router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="The question or analysis request for StockGPT",
    )
    symbol: str = Field(
        default="",
        max_length=30,
        description="Optional: specific stock symbol to include live OI for",
    )


class ChatResponse(BaseModel):
    answer: str


@router.post("/chat", response_model=ChatResponse, summary="Ask StockGPT AI")
def chat(request: ChatRequest):
    """
    Submit a question to StockGPT AI.
    Passes live market data (LTP, PCR, OI) and optional symbol detail to the AI.
    """
    try:
        # Base market data — 20 stocks with live LTP
        market = get_market()

        # If a specific symbol was requested, enrich context with its live option chain
        extra_context = {}
        if request.symbol:
            try:
                from app.services.market_service import get_stock_detail
                extra_context = get_stock_detail(request.symbol.upper())
            except Exception:
                pass

        # Also append live index data for richer context
        try:
            from app.services.yahoo_service import get_indices
            indices = get_indices()
            extra_context["indices"] = indices
        except Exception:
            pass

        answer = ask_ai(request.question, market, extra_context)
        return ChatResponse(answer=answer)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
