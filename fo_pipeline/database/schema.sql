-- ===========================================================================
-- Database Schema for NSE F&O Data Pipeline
-- ===========================================================================

-- 1. Expiry Dates Table
CREATE TABLE IF NOT EXISTS expiry_dates (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(30) NOT NULL,
    expiry_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (symbol, expiry_date)
);
CREATE INDEX IF NOT EXISTS idx_expiry_symbol ON expiry_dates(symbol);

-- 2. F&O Bhavcopy Table
CREATE TABLE IF NOT EXISTS fo_bhavcopy (
    id SERIAL PRIMARY KEY,
    trading_date DATE NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    instrument VARCHAR(30) NOT NULL,
    expiry_date DATE NOT NULL,
    strike_price DOUBLE PRECISION NOT NULL,
    option_type VARCHAR(10) NOT NULL, -- XX, CE, PE
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    settle_price DOUBLE PRECISION,
    contracts BIGINT,
    value DOUBLE PRECISION,
    open_interest BIGINT,
    change_in_oi BIGINT,
    timestamp DATE,
    UNIQUE (trading_date, symbol, instrument, expiry_date, strike_price, option_type)
);
CREATE INDEX IF NOT EXISTS idx_bhav_symbol ON fo_bhavcopy(symbol);
CREATE INDEX IF NOT EXISTS idx_bhav_expiry ON fo_bhavcopy(expiry_date);
CREATE INDEX IF NOT EXISTS idx_bhav_strike ON fo_bhavcopy(strike_price);
CREATE INDEX IF NOT EXISTS idx_bhav_opt_type ON fo_bhavcopy(option_type);
CREATE INDEX IF NOT EXISTS idx_bhav_trading_date ON fo_bhavcopy(trading_date);

-- 3. Live Option Chain Table
CREATE TABLE IF NOT EXISTS option_chain_live (
    id SERIAL PRIMARY KEY,
    fetch_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    symbol VARCHAR(30) NOT NULL,
    expiry_date DATE NOT NULL,
    strike_price DOUBLE PRECISION NOT NULL,
    call_oi BIGINT,
    call_change_oi BIGINT,
    call_volume BIGINT,
    call_ltp DOUBLE PRECISION,
    call_iv DOUBLE PRECISION,
    put_oi BIGINT,
    put_change_oi BIGINT,
    put_volume BIGINT,
    put_ltp DOUBLE PRECISION,
    put_iv DOUBLE PRECISION,
    UNIQUE (fetch_time, symbol, expiry_date, strike_price)
);
CREATE INDEX IF NOT EXISTS idx_live_sym_expiry ON option_chain_live(symbol, expiry_date);
CREATE INDEX IF NOT EXISTS idx_live_fetch_time ON option_chain_live(fetch_time);

-- 4. Daily Analytics Table
CREATE TABLE IF NOT EXISTS daily_analytics (
    id SERIAL PRIMARY KEY,
    analysis_date DATE NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    expiry_date DATE NOT NULL,
    total_pcr DOUBLE PRECISION,
    mean_pcr DOUBLE PRECISION,
    max_call_oi BIGINT,
    max_put_oi BIGINT,
    max_call_oi_strike DOUBLE PRECISION,
    max_put_oi_strike DOUBLE PRECISION,
    max_call_change BIGINT,
    max_put_change BIGINT,
    support DOUBLE PRECISION,
    resistance DOUBLE PRECISION,
    max_pain DOUBLE PRECISION,
    put_call_volume_ratio DOUBLE PRECISION,
    atm_strike DOUBLE PRECISION,
    sentiment VARCHAR(30),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (analysis_date, symbol, expiry_date)
);

-- 5. Market Summary Table
CREATE TABLE IF NOT EXISTS market_summary (
    id SERIAL PRIMARY KEY,
    summary_date DATE NOT NULL UNIQUE,
    bullish_count INTEGER,
    bearish_count INTEGER,
    neutral_count INTEGER,
    total_market_oi BIGINT,
    avg_market_pcr DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Trading Calendar Table
CREATE TABLE IF NOT EXISTS trading_calendar (
    id SERIAL PRIMARY KEY,
    calendar_date DATE NOT NULL UNIQUE,
    is_holiday BOOLEAN DEFAULT FALSE,
    holiday_description VARCHAR(100)
);

-- 7. Pipeline Logs Table
CREATE TABLE IF NOT EXISTS pipeline_logs (
    id SERIAL PRIMARY KEY,
    log_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    module VARCHAR(50) NOT NULL,
    level VARCHAR(10) NOT NULL,
    message TEXT NOT NULL
);

-- ===========================================================================
-- Database Views for ML models and AI Analysis
-- ===========================================================================

-- 1. Daily PCR View
CREATE OR REPLACE VIEW daily_pcr AS
SELECT 
    trading_date,
    symbol,
    expiry_date,
    SUM(CASE WHEN option_type = 'PE' THEN open_interest ELSE 0 END) as total_put_oi,
    SUM(CASE WHEN option_type = 'CE' THEN open_interest ELSE 0 END) as total_call_oi,
    CASE 
        WHEN SUM(CASE WHEN option_type = 'CE' THEN open_interest ELSE 0 END) = 0 THEN 0.0
        ELSE ROUND(CAST(SUM(CASE WHEN option_type = 'PE' THEN open_interest ELSE 0 END) AS NUMERIC) / 
                   NULLIF(SUM(CASE WHEN option_type = 'CE' THEN open_interest ELSE 0 END), 0), 2)
    END as pcr
FROM fo_bhavcopy
WHERE option_type IN ('CE', 'PE')
GROUP BY trading_date, symbol, expiry_date;

-- 2. Daily Mean PCR View
CREATE OR REPLACE VIEW daily_mean_pcr AS
SELECT 
    trading_date,
    AVG(pcr) as mean_market_pcr
FROM daily_pcr
GROUP BY trading_date;

-- 3. Support & Resistance View (from Bhavcopy)
CREATE OR REPLACE VIEW daily_support_resistance AS
SELECT 
    trading_date,
    symbol,
    expiry_date,
    -- Simple Pivot Point support & resistance estimation
    ROUND(AVG(close), 2) as close_price,
    ROUND(MAX(high), 2) as high_price,
    ROUND(MIN(low), 2) as low_price
FROM fo_bhavcopy
GROUP BY trading_date, symbol, expiry_date;

-- 4. Max Option Interest Summary
CREATE OR REPLACE VIEW max_oi_summary AS
WITH CallOI AS (
    SELECT trading_date, symbol, expiry_date, strike_price, open_interest,
           ROW_NUMBER() OVER (PARTITION BY trading_date, symbol, expiry_date ORDER BY open_interest DESC) as rn
    FROM fo_bhavcopy
    WHERE option_type = 'CE'
),
PutOI AS (
    SELECT trading_date, symbol, expiry_date, strike_price, open_interest,
           ROW_NUMBER() OVER (PARTITION BY trading_date, symbol, expiry_date ORDER BY open_interest DESC) as rn
    FROM fo_bhavcopy
    WHERE option_type = 'PE'
)
SELECT 
    c.trading_date,
    c.symbol,
    c.expiry_date,
    c.strike_price as max_call_strike,
    c.open_interest as max_call_oi,
    p.strike_price as max_put_strike,
    p.open_interest as max_put_oi
FROM CallOI c
JOIN PutOI p ON c.trading_date = p.trading_date 
            AND c.symbol = p.symbol 
            AND c.expiry_date = p.expiry_date
WHERE c.rn = 1 AND p.rn = 1;

-- 5. ATM Summary View
CREATE OR REPLACE VIEW atm_summary AS
SELECT 
    trading_date,
    symbol,
    expiry_date,
    strike_price as atm_strike
FROM (
    SELECT 
        b.trading_date,
        b.symbol,
        b.expiry_date,
        b.strike_price,
        ROW_NUMBER() OVER (PARTITION BY b.trading_date, b.symbol, b.expiry_date ORDER BY ABS(b.strike_price - u.close)) as rn
    FROM fo_bhavcopy b
    -- join with underlying future close to determine spot approximation
    LEFT JOIN fo_bhavcopy u ON b.trading_date = u.trading_date 
                           AND b.symbol = u.symbol 
                           AND b.expiry_date = u.expiry_date 
                           AND u.instrument = 'FUTSTK' -- or FUTIDX
    WHERE b.option_type IN ('CE', 'PE')
) t
WHERE rn = 1;

-- 6. Overall Market Sentiment View
CREATE OR REPLACE VIEW market_sentiment AS
SELECT 
    analysis_date,
    symbol,
    expiry_date,
    total_pcr,
    sentiment,
    CASE 
        WHEN sentiment = 'Long Buildup' THEN 2
        WHEN sentiment = 'Short Covering' THEN 1
        WHEN sentiment = 'Neutral' THEN 0
        WHEN sentiment = 'Long Unwinding' THEN -1
        WHEN sentiment = 'Short Buildup' THEN -2
        ELSE 0
    END as sentiment_score
FROM daily_analytics;
