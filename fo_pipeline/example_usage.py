"""
Example Usage Script for the NSE F&O Data Pipeline.
Demonstrates running components programmatically.
"""
import sys
import os
import logging
from datetime import date

# Append current directory to path to enable local imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.connection import SessionLocal, get_db
from main import init_db_schema
from nse.expiry import fetch_and_store_expiries
from nse.bhavcopy import find_last_trading_day, download_and_import_bhavcopy
from nse.option_chain import fetch_and_store_live_option_chain
from scheduler.jobs import run_evening_analytics_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("example_usage")

def run_demo():
    logger.info("Initializing database schema...")
    init_db_schema()
    
    logger.info("Initializing F&O Pipeline Session...")
    db = SessionLocal()
    try:
        # Step 1: Fetch and save index contract expiry dates
        logger.info("--- Step 1: Fetching Expiry Dates ---")
        exp_stats = fetch_and_store_expiries(db)
        logger.info("Expiry stats: %s", exp_stats)

        # Step 2: Detect the last active trading day
        logger.info("--- Step 2: Detecting Last Trading Day ---")
        last_day = find_last_trading_day(db)
        logger.info("Last active trading day detected: %s", last_day.isoformat())

        # Step 3: Fetch and import Bhavcopy for the last trading day
        logger.info("--- Step 3: Importing F&O Bhavcopy ---")
        bhav_result = download_and_import_bhavcopy(db, last_day)
        logger.info("Bhavcopy result: %s", bhav_result)

        # Step 4: Fetch and store live option chain snapshot
        logger.info("--- Step 4: Fetching Live Option Chain ---")
        oc_result = fetch_and_store_live_option_chain(db, "NIFTY")
        logger.info("Live option chain result: %s", oc_result)

        # Step 5: Run evening analytics generation job
        logger.info("--- Step 5: Running Daily Analytics Summary ---")
        run_evening_analytics_job()
        
        logger.info("Demo executed successfully!")
        
    except Exception as e:
        logger.error("Error occurred during F&O Pipeline demo run: %s", e, exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    run_demo()
