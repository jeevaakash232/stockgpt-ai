import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# ── Existing routers (unchanged) ──────────────────────────
from app.api.chat   import router as chat_router
from app.api.market import router as market_router
from app.api.pcr    import router as pcr_router

# ── New routers ────────────────────────────────────────────
from app.api.dashboard    import router as dashboard_router
from app.api.stock        import router as stock_router
from app.api.watchlist    import router as watchlist_router
from app.api.option_chain import router as option_chain_router
from app.api.export       import router as export_router

load_dotenv()

# ---------------------------------------------------------------------------
# CORS — allowed origins
# Add your Netlify URL here after deploying the frontend.
# ---------------------------------------------------------------------------
_FRONTEND_URL = os.getenv("FRONTEND_URL", "")   # set in Render env vars

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8080",
    "null",             # file:// protocol (opening index.html directly)
]
if _FRONTEND_URL:
    ALLOWED_ORIGINS.append(_FRONTEND_URL)

app = FastAPI(
    title="StockGPT AI",
    description="AI-powered Indian Stock Market Analysis API",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ───────────────────────────────────────
# Existing (preserved)
app.include_router(chat_router,   prefix="/api", tags=["Chat"])
app.include_router(market_router, prefix="/api", tags=["Market"])
app.include_router(pcr_router,    prefix="/api", tags=["PCR"])

# New
app.include_router(dashboard_router,    prefix="/api", tags=["Dashboard"])
app.include_router(stock_router,        prefix="/api", tags=["Stock"])
app.include_router(watchlist_router,    prefix="/api", tags=["Watchlist"])
app.include_router(option_chain_router, prefix="/api", tags=["OptionChain"])
app.include_router(export_router,       prefix="/api", tags=["Export"])


@app.get("/")
def root():
    return {"status": "StockGPT AI backend is running", "version": "2.0.0"}


@app.on_event("startup")
async def on_startup():
    """Pre-warm caches in background so first request is fast."""
    from app.services.yahoo_service import warm_cache as yahoo_warm
    from app.services.angel_service import warm_cache as angel_warm
    yahoo_warm()
    angel_warm()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
