import logging
from datetime import date, datetime, timedelta
from sqlalchemy import text
from database.connection import SessionLocal
from database.queries import (
    get_last_available_trading_date,
    get_available_expiries,
    get_fo_bhavcopy_data
)
from database.insert import insert_expiry_dates
from nse.expiry import fetch_and_store_expiries
from nse.bhavcopy import find_last_trading_day, download_and_import_bhavcopy
from nse.option_chain import fetch_and_store_live_option_chain

# Analytics imports
from analytics.pcr import calculate_total_pcr, calculate_put_call_volume_ratio
from analytics.support import calculate_support
from analytics.resistance import calculate_resistance
from analytics.maxpain import calculate_max_pain
from analytics.sentiment import interpret_sentiment
from analytics.indicators import calculate_atm_strike, calculate_oi_buildup

logger = logging.getLogger(__name__)

TRACKED_SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"]

def run_morning_pipeline_job():
    """
    Morning Job (typically run at 8:30 AM).
    Downloads previous day's F&O Bhavcopy and fetches expiry dates.
    """
    logger.info("Starting Morning F&O Data Pipeline Job...")
    db = SessionLocal()
    try:
        # 1. Fetch live expiry dates
        fetch_and_store_expiries(db)
        
        # 2. Detect last trading day and download Bhavcopy
        last_trading_day = find_last_trading_day(db)
        logger.info("Detected last trading day: %s", last_trading_day.isoformat())
        
        # Try downloading
        res = download_and_import_bhavcopy(db, last_trading_day)
        logger.info("Morning Bhavcopy Import Result: %s", res)
        
    except Exception as e:
        logger.error("Error in run_morning_pipeline_job: %s", e)
    finally:
        db.close()


def run_intraday_option_chain_job():
    """
    Intraday Job (run every 5 minutes during market hours).
    Logs live option chain snapshots.
    """
    logger.info("Starting Intraday Option Chain Logging Job...")
    db = SessionLocal()
    try:
        for symbol in TRACKED_SYMBOLS:
            res = fetch_and_store_live_option_chain(db, symbol)
            logger.debug("Live option chain fetch result for %s: %s", symbol, res)
    except Exception as e:
        logger.error("Error in run_intraday_option_chain_job: %s", e)
    finally:
        db.close()


def run_evening_analytics_job():
    """
    Evening Job (run at 5:30 PM).
    Generates analytics from bhavcopy for the day and saves daily_analytics.
    """
    logger.info("Starting Evening F&O Analytics Job...")
    db = SessionLocal()
    try:
        trading_date = get_last_available_trading_date(db)
        # Find previous trading date to calculate changes
        prev_date = find_last_trading_day(db, start_from=trading_date - timedelta(days=1))
        
        logger.info("Generating F&O analytics for trading_date: %s (compared with %s)", 
                    trading_date.isoformat(), prev_date.isoformat())
                    
        bullish_cnt = 0
        bearish_cnt = 0
        neutral_cnt = 0
        total_market_oi = 0
        pcr_values = []
        
        for symbol in TRACKED_SYMBOLS:
            expiries = get_available_expiries(db, symbol)
            # Take nearest expiry for analytics summary
            if not expiries:
                continue
            expiry_date = expiries[0]
            
            # 1. Get today's bhavcopy data for this symbol + expiry
            df_today = get_fo_bhavcopy_data(db, symbol, trading_date, expiry_date)
            if df_today.empty:
                continue
                
            # Filter option contracts (exclude index futures)
            df_options = df_today[df_today["option_type"].isin(["CE", "PE"])]
            if df_options.empty:
                continue
                
            # 2. Get previous close & OI for change metrics
            prev_close = 0.0
            prev_oi = 0
            
            # Query future close for price change
            fut_sql = """
                SELECT close, open_interest FROM fo_bhavcopy 
                WHERE symbol = :symbol 
                  AND trading_date = :prev_date 
                  AND instrument = 'FUTIDX'
                LIMIT 1
            """
            prev_row = db.execute(text(fut_sql), {"symbol": symbol, "prev_date": prev_date}).first()
            if prev_row:
                prev_close = float(prev_row[0] or 0.0)
                prev_oi = int(prev_row[1] or 0)
                
            # Get today's future close
            curr_row = db.execute(text("""
                SELECT close, open_interest FROM fo_bhavcopy 
                WHERE symbol = :symbol 
                  AND trading_date = :trading_date 
                  AND instrument = 'FUTIDX'
                LIMIT 1
            """), {"symbol": symbol, "trading_date": trading_date}).first()
            
            spot_price = float(curr_row[0] or 0.0) if curr_row else 0.0
            curr_oi = int(curr_row[1] or 0) if curr_row else 0
            
            price_change = spot_price - prev_close if prev_close else 0.0
            oi_change = curr_oi - prev_oi if prev_oi else 0
            
            # Calculate metrics
            pcr = calculate_total_pcr(df_options)
            vol_ratio = calculate_put_call_volume_ratio(df_options)
            support = calculate_support(df_options)
            resistance = calculate_resistance(df_options)
            max_pain = calculate_max_pain(df_options)
            atm_strike = calculate_atm_strike(df_options, spot_price)
            sentiment = interpret_sentiment(price_change, oi_change)
            
            # Track market totals
            pcr_values.append(pcr)
            total_market_oi += curr_oi
            
            if sentiment in ["Long Buildup", "Short Covering"]:
                bullish_cnt += 1
            elif sentiment in ["Short Buildup", "Long Unwinding"]:
                bearish_cnt += 1
            else:
                neutral_cnt += 1
                
            # Get max Call / Put OIs and changes
            buildup = calculate_oi_buildup(df_options)
            max_c_oi = buildup["max_call_oi"]
            max_p_oi = buildup["max_put_oi"]
            max_c_chg = buildup["max_call_change"]
            max_p_chg = buildup["max_put_change"]
            
            # 3. Upsert into daily_analytics
            sql = """
                INSERT INTO daily_analytics (
                    analysis_date, symbol, expiry_date, total_pcr, mean_pcr,
                    max_call_oi, max_put_oi, max_call_oi_strike, max_put_oi_strike,
                    max_call_change, max_put_change, support, resistance, max_pain,
                    put_call_volume_ratio, atm_strike, sentiment
                ) VALUES (
                    :date_val, :symbol, :expiry_date, :pcr, :mean_pcr,
                    :max_c_oi_val, :max_p_oi_val, :max_c_oi_strike, :max_p_oi_strike,
                    :max_c_chg, :max_p_chg, :support, :resistance, :max_pain,
                    :vol_ratio, :atm_strike, :sentiment
                ) ON CONFLICT (analysis_date, symbol, expiry_date) DO UPDATE SET
                    total_pcr = EXCLUDED.total_pcr,
                    max_call_oi = EXCLUDED.max_call_oi,
                    max_put_oi = EXCLUDED.max_put_oi,
                    support = EXCLUDED.support,
                    resistance = EXCLUDED.resistance,
                    max_pain = EXCLUDED.max_pain,
                    sentiment = EXCLUDED.sentiment
            """
            db.execute(text(sql), {
                "date_val": trading_date,
                "symbol": symbol,
                "expiry_date": expiry_date,
                "pcr": pcr,
                "mean_pcr": pcr, # single ticker PCR representation
                "max_c_oi_val": max_c_oi["value"],
                "max_c_oi_strike": max_c_oi["strike"],
                "max_p_oi_val": max_p_oi["value"],
                "max_p_oi_strike": max_p_oi["strike"],
                "max_c_chg": max_c_chg["value"],
                "max_p_chg": max_p_chg["value"],
                "support": support,
                "resistance": resistance,
                "max_pain": max_pain,
                "vol_ratio": vol_ratio,
                "atm_strike": atm_strike,
                "sentiment": sentiment
            })
            
        # 4. Save Market Summary
        if pcr_values:
            avg_pcr = sum(pcr_values) / len(pcr_values)
            db.execute(text("""
                INSERT INTO market_summary (
                    summary_date, bullish_count, bearish_count, neutral_count,
                    total_market_oi, avg_market_pcr
                ) VALUES (:date_val, :bullish, :bearish, :neutral, :total_oi, :avg_pcr)
                ON CONFLICT (summary_date) DO UPDATE SET
                    bullish_count = EXCLUDED.bullish_count,
                    bearish_count = EXCLUDED.bearish_count,
                    neutral_count = EXCLUDED.neutral_count,
                    avg_market_pcr = EXCLUDED.avg_market_pcr
            """), {
                "date_val": trading_date,
                "bullish": bullish_cnt,
                "bearish": bearish_cnt,
                "neutral": neutral_cnt,
                "total_oi": total_market_oi,
                "avg_pcr": round(avg_pcr, 2)
            })
            
        db.commit()
        logger.info("Evening analytics completed successfully for trading_date: %s", trading_date.isoformat())
        
    except Exception as e:
        db.rollback()
        logger.error("Error in run_evening_analytics_job: %s", e)
    finally:
        db.close()
