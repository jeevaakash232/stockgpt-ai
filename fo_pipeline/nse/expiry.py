import logging
from datetime import datetime
from nse.downloader import downloader
from database.insert import insert_expiry_dates

logger = logging.getLogger(__name__)

INDEX_SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"]

def fetch_and_store_expiries(db) -> dict:
    """
    Fetch live expiry dates for indices from official NSE website
    and store them into PostgreSQL.
    """
    url = "https://www.nseindia.com/api/option-chain-indices"
    stats = {}
    
    for symbol in INDEX_SYMBOLS:
        try:
            logger.info("Fetching F&O expiries for index %s...", symbol)
            data = downloader.fetch_api(url, params={"symbol": symbol})
            
            records = data.get("records", {})
            expiry_dates_raw = records.get("expiryDates", [])
            
            if not expiry_dates_raw:
                logger.warning("No expiry dates returned for symbol %s", symbol)
                continue
            
            # Parse dates e.g. "09-Jul-2026"
            parsed_expiries = []
            for date_str in expiry_dates_raw:
                try:
                    dt = datetime.strptime(date_str, "%d-%b-%Y").date()
                    parsed_expiries.append(dt)
                except ValueError as ve:
                    logger.error("Failed to parse date %s: %s", date_str, ve)

            inserted = insert_expiry_dates(db, symbol, parsed_expiries)
            stats[symbol] = {
                "fetched": len(parsed_expiries),
                "inserted": inserted
            }
            logger.info("Successfully fetched %d expiries (inserted %d new) for %s", 
                        len(parsed_expiries), inserted, symbol)
            
        except Exception as e:
            logger.error("Failed to fetch expiries for symbol %s: %s", symbol, e)
            stats[symbol] = {"error": str(e)}
            
    return stats
