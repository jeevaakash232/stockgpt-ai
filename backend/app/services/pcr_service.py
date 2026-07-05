"""
PCR Service
-----------
Single source of truth for PCR calculation and signal logic.
Used by market_data.py and pcr API.
"""


def calculate_pcr(call_oi: int, put_oi: int) -> float:
    """Put-Call Ratio = Put OI / Call OI. Returns 0 if Call OI is zero."""
    if call_oi == 0:
        return 0.0
    return round(put_oi / call_oi, 2)


def signal(pcr: float) -> str:
    """Interpret a PCR value as a market sentiment signal."""
    if pcr > 1.2:
        return "Strong Bullish"
    elif pcr >= 1.0:
        return "Bullish"
    elif pcr >= 0.8:
        return "Neutral"
    return "Bearish"
