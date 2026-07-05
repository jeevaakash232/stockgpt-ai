import logging

logger = logging.getLogger(__name__)

def interpret_sentiment(price_change: float, oi_change: float) -> str:
    """
    Interpret market sentiment based on price action and open interest dynamics.
    
    1. Price Up, Open Interest Up     -> Long Buildup (Bullish)
    2. Price Up, Open Interest Down   -> Short Covering (Bullish)
    3. Price Down, Open Interest Down -> Long Unwinding (Bearish)
    4. Price Down, Open Interest Up   -> Short Buildup (Bearish)
    5. No change                      -> Neutral
    """
    if price_change is None or oi_change is None:
        return "Neutral"

    if price_change > 0:
        if oi_change > 0:
            return "Long Buildup"
        elif oi_change < 0:
            return "Short Covering"
    elif price_change < 0:
        if oi_change > 0:
            return "Short Buildup"
        elif oi_change < 0:
            return "Long Unwinding"
            
    return "Neutral"
