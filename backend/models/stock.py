"""
Stock Models
------------
Pydantic models used for request/response validation.
"""

from pydantic import BaseModel


class StockPCR(BaseModel):
    symbol:   str
    call_oi:  int
    put_oi:   int
    ltp:      float = 0.0
    max_pain: float = 0.0
    pcr:      float
    signal:   str
