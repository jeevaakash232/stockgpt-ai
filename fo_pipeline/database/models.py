from sqlalchemy import Column, Integer, String, Date, Float, BigInteger, Boolean, DateTime, text
from database.connection import Base

class ExpiryDate(Base):
    __tablename__ = "expiry_dates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(30), nullable=False)
    expiry_date = Column(Date, nullable=False)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class FOBhavcopy(Base):
    __tablename__ = "fo_bhavcopy"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trading_date = Column(Date, nullable=False)
    symbol = Column(String(30), nullable=False, index=True)
    instrument = Column(String(30), nullable=False)
    expiry_date = Column(Date, nullable=False, index=True)
    strike_price = Column(Float, nullable=False, index=True)
    option_type = Column(String(10), nullable=False, index=True) # XX, CE, PE
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    settle_price = Column(Float)
    contracts = Column(BigInteger)
    value = Column(Float)
    open_interest = Column(BigInteger)
    change_in_oi = Column(BigInteger)
    timestamp = Column(Date)

class OptionChainLive(Base):
    __tablename__ = "option_chain_live"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fetch_time = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), index=True)
    symbol = Column(String(30), nullable=False, index=True)
    expiry_date = Column(Date, nullable=False, index=True)
    strike_price = Column(Float, nullable=False)
    call_oi = Column(BigInteger)
    call_change_oi = Column(BigInteger)
    call_volume = Column(BigInteger)
    call_ltp = Column(Float)
    call_iv = Column(Float)
    put_oi = Column(BigInteger)
    put_change_oi = Column(BigInteger)
    put_volume = Column(BigInteger)
    put_ltp = Column(Float)
    put_iv = Column(Float)

class DailyAnalytics(Base):
    __tablename__ = "daily_analytics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_date = Column(Date, nullable=False, index=True)
    symbol = Column(String(30), nullable=False, index=True)
    expiry_date = Column(Date, nullable=False, index=True)
    total_pcr = Column(Float)
    mean_pcr = Column(Float)
    max_call_oi = Column(BigInteger)
    max_put_oi = Column(BigInteger)
    max_call_oi_strike = Column(Float)
    max_put_oi_strike = Column(Float)
    max_call_change = Column(BigInteger)
    max_put_change = Column(BigInteger)
    support = Column(Float)
    resistance = Column(Float)
    max_pain = Column(Float)
    put_call_volume_ratio = Column(Float)
    atm_strike = Column(Float)
    sentiment = Column(String(30))
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class MarketSummary(Base):
    __tablename__ = "market_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    summary_date = Column(Date, nullable=False, unique=True)
    bullish_count = Column(Integer)
    bearish_count = Column(Integer)
    neutral_count = Column(Integer)
    total_market_oi = Column(BigInteger)
    avg_market_pcr = Column(Float)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class TradingCalendar(Base):
    __tablename__ = "trading_calendar"

    id = Column(Integer, primary_key=True, autoincrement=True)
    calendar_date = Column(Date, nullable=False, unique=True)
    is_holiday = Column(Boolean, default=False)
    holiday_description = Column(String(100))

class PipelineLog(Base):
    __tablename__ = "pipeline_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    log_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    module = Column(String(50), nullable=False)
    level = Column(String(10), nullable=False)
    message = Column(DateTime, nullable=False) # Wait, type should be text/string
    message = Column(String, nullable=False)
