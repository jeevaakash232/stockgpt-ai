import logging
from datetime import datetime
from nse.downloader import downloader
from database.insert import bulk_insert_live_option_chain

logger = logging.getLogger(__name__)

INDEX_SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"]

def fetch_and_store_live_option_chain(db, symbol: str) -> dict:
    """
    Fetch the live option chain for a symbol (index or stock) from the official
    NSE API, and bulk insert all strike rows into PostgreSQL.
    """
    symbol = symbol.upper()
    is_index = symbol in INDEX_SYMBOLS
    
    url = "https://www.nseindia.com/api/option-chain-indices" if is_index else "https://www.nseindia.com/api/option-chain-equities"
    
    try:
        logger.info("Fetching live F&O option chain for %s...", symbol)
        data = downloader.fetch_api(url, params={"symbol": symbol})
        
        records = data.get("records", {})
        strike_data = data.get("filtered", {}).get("data", []) or records.get("data", [])
        
        if not strike_data:
            logger.warning("No live option chain strike data returned for symbol %s", symbol)
            return {"symbol": symbol, "success": False, "reason": "No data returned"}

        fetch_time = datetime.now()
        rows_to_insert = []
        
        for item in strike_data:
            strike = float(item.get("strikePrice", 0))
            expiry_str = item.get("expiryDate")
            if not expiry_str:
                continue
            
            try:
                # Parse "09-Jul-2026"
                expiry_date = datetime.strptime(expiry_str, "%d-%b-%Y").date()
            except ValueError:
                continue
                
            ce = item.get("CE", {})
            pe = item.get("PE", {})
            
            row = {
                "fetch_time": fetch_time,
                "symbol": symbol,
                "expiry_date": expiry_date,
                "strike_price": strike,
                
                # Call side
                "call_oi": ce.get("openInterest", 0) or 0,
                "call_change_oi": ce.get("changeinOpenInterest", 0) or 0,
                "call_volume": ce.get("totalTradedVolume", 0) or 0,
                "call_ltp": ce.get("lastPrice", 0.0) or 0.0,
                "call_iv": ce.get("impliedVolatility", 0.0) or 0.0,
                
                # Put side
                "put_oi": pe.get("openInterest", 0) or 0,
                "put_change_oi": pe.get("changeinOpenInterest", 0) or 0,
                "put_volume": pe.get("totalTradedVolume", 0) or 0,
                "put_ltp": pe.get("lastPrice", 0.0) or 0.0,
                "put_iv": pe.get("impliedVolatility", 0.0) or 0.0,
            }
            rows_to_insert.append(row)
            
        inserted = bulk_insert_live_option_chain(db, rows_to_insert)
        logger.info("Successfully fetched option chain and inserted %d live strike records for %s", 
                    inserted, symbol)
        
        return {
            "symbol": symbol,
            "success": True,
            "inserted_rows": inserted,
            "fetch_time": fetch_time.isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to fetch live option chain for symbol %s: %s", symbol, e)
        return {"symbol": symbol, "success": False, "reason": str(e)}
