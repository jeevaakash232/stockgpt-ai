import os
import zipfile
import logging
import pandas as pd
from datetime import datetime, date, timedelta
from nse.downloader import downloader
from database.insert import bulk_insert_bhavcopy
from database.queries import is_holiday

logger = logging.getLogger(__name__)

# Temporary directory for zip files and CSV files
TEMP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "temp"))

def get_bhavcopy_url(target_date: date) -> str:
    """
    Generate the official NSE derivatives UDiFF Bhavcopy URL.
    Format: https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_20260709_F_0000.csv.zip
    """
    date_str = target_date.strftime("%Y%m%d")
    return f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{date_str}_F_0000.csv.zip"


def find_last_trading_day(db, start_from: date = None) -> date:
    """
    Scan backward to detect the most recent active NSE trading date,
    skipping weekends and database holidays.
    """
    curr = start_from or date.today()
    
    # If today is after market close, start checking from today, else start checking from yesterday
    if datetime.now().hour < 18 and not start_from:
        curr = curr - timedelta(days=1)
        
    for _ in range(15):  # check up to 15 days back
        # Skip Saturday (5) and Sunday (6)
        if curr.weekday() >= 5 or is_holiday(db, curr):
            curr -= timedelta(days=1)
            continue
        return curr
        
    return curr


def download_and_import_bhavcopy(db, target_date: date) -> dict:
    """
    Workflow to download, unzip, parse, and upload the F&O Bhavcopy.
    Supports both legacy and new UDiFF formats.
    """
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    url = get_bhavcopy_url(target_date)
    zip_filename = f"BhavCopy_NSE_FO_0_0_0_{target_date.strftime('%Y%m%d')}_F_0000.csv.zip"
    zip_path = os.path.join(TEMP_DIR, zip_filename)
    
    logger.info("Attempting download for F&O Bhavcopy date: %s", target_date.isoformat())
    
    success = downloader.download_file(url, zip_path)
    if not success:
        # Fallback to legacy URL structure if UDiFF fails
        logger.warning("UDiFF Bhavcopy download failed for %s. Retrying legacy archives URL...", target_date.isoformat())
        year = target_date.strftime("%Y")
        month_name = target_date.strftime("%b").upper()
        day = target_date.strftime("%d")
        url = f"https://archives.nseindia.com/content/historical/DERIVATIVES/{year}/{month_name}/fo{day}{month_name}{year}bhav.csv.zip"
        zip_filename = f"fo{target_date.strftime('%d%b%Y').upper()}bhav.csv.zip"
        zip_path = os.path.join(TEMP_DIR, zip_filename)
        success = downloader.download_file(url, zip_path)
        
    if not success:
        logger.warning("Legacy Bhavcopy download also failed for %s. (Could be a holiday)", target_date.isoformat())
        return {"date": target_date.isoformat(), "success": False, "reason": "Download failed"}
        
    csv_file_path = None
    try:
        # Unzip Bhavcopy
        logger.info("Unzipping F&O Bhavcopy: %s", zip_filename)
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(TEMP_DIR)
            # Find the extracted CSV file name
            extracted_files = zip_ref.namelist()
            csv_file_name = next((f for f in extracted_files if f.endswith(".csv")), None)
            if csv_file_name:
                csv_file_path = os.path.join(TEMP_DIR, csv_file_name)
                
        if not csv_file_path or not os.path.exists(csv_file_path):
            raise FileNotFoundError("Bhavcopy CSV file not found inside zip archive")
            
        logger.info("Parsing Bhavcopy CSV into DataFrame: %s", csv_file_path)
        
        # Read F&O CSV using pandas
        df = pd.read_csv(csv_file_path)
        
        # Standardise headers (strip whitespaces)
        df.columns = [c.strip() for c in df.columns]
        
        # Detect if this is UDiFF format
        is_udiff = "FinInstrmTp" in df.columns
        
        if is_udiff:
            logger.info("Detected UDiFF format. Adapting columns...")
            df["trading_date"] = pd.to_datetime(df["TradDt"]).dt.date
            df["expiry_date"]  = pd.to_datetime(df["XpryDt"]).dt.date
            df["timestamp"]    = df["trading_date"]
            
            # Map UDiFF option types
            df["OptnTp"] = df["OptnTp"].fillna("XX").astype(str).str.strip()
            df["option_type"] = df["OptnTp"]
            
            # Map instrument types
            inst_map = {"STO": "OPTSTK", "STF": "FUTSTK", "IDO": "OPTIDX", "IDF": "FUTIDX"}
            df["instrument"] = df["FinInstrmTp"].str.strip().map(inst_map).fillna("XX")
            
            # Map values
            df["symbol"] = df["TckrSymb"].str.strip()
            df["strike_price"] = df["StrkPric"].fillna(0.0).astype(float)
            df["open"] = df["OpnPric"].fillna(0.0).astype(float)
            df["high"] = df["HghPric"].fillna(0.0).astype(float)
            df["low"] = df["LwPric"].fillna(0.0).astype(float)
            df["close"] = df["ClsPric"].fillna(0.0).astype(float)
            df["settle_price"] = df["SttlmPric"].fillna(0.0).astype(float)
            df["contracts"] = df["TtlTradgVol"].fillna(0).astype(int)
            df["value"] = df["TtlTrfVal"].fillna(0.0).astype(float) / 100000.0 # convert to lakhs
            df["open_interest"] = df["OpnIntrst"].fillna(0).astype(int)
            df["change_in_oi"] = df["ChngInOpnIntrst"].fillna(0).astype(int)
        else:
            # Legacy format processing
            df["trading_date"] = pd.to_datetime(df["TIMESTAMP"], format="%d-%b-%Y").dt.date
            df["expiry_date"]  = pd.to_datetime(df["EXPIRY_DT"], format="%d-%b-%Y").dt.date
            df["timestamp"]    = df["trading_date"]
            df["OPTION_TYPE"]  = df["OPTION_TYPE"].fillna("XX").astype(str).str.strip()
            
            rename_map = {
                "INSTRUMENT":    "instrument",
                "SYMBOL":        "symbol",
                "STRIKE_PR":     "strike_price",
                "OPTION_TYPE":    "option_type",
                "OPEN":          "open",
                "HIGH":          "high",
                "LOW":           "low",
                "CLOSE":         "close",
                "SETTLE_PR":     "settle_price",
                "CONTRACTS":     "contracts",
                "VAL_INLAKH":    "value",
                "OPEN_INT":      "open_interest",
                "CHG_IN_OI":     "change_in_oi"
            }
            df = df.rename(columns=rename_map)
            df["symbol"] = df["symbol"].str.strip()
            df["instrument"] = df["instrument"].str.strip()
        
        # Bulk load into PostgreSQL
        logger.info("Executing bulk insert to database...")
        inserted_rows = bulk_insert_bhavcopy(db, df)
        
        logger.info("F&O Bhavcopy import successful for %s. Inserted: %d records", 
                    target_date.isoformat(), inserted_rows)
        
        return {
            "date": target_date.isoformat(),
            "success": True,
            "inserted_rows": inserted_rows
        }
        
    except Exception as e:
        logger.error("Failed importing Bhavcopy for %s: %s", target_date.isoformat(), e)
        return {"date": target_date.isoformat(), "success": False, "reason": str(e)}
        
    finally:
        # Cleanup files
        if os.path.exists(zip_path):
            os.remove(zip_path)
        if csv_file_path and os.path.exists(csv_file_path):
            os.remove(csv_file_path)
