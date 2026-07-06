"""
Populate Real History snapshots
-------------------------------
Downloads a real derivatives Bhavcopy from a past Friday (May 24, 2024)
from the NSE archives, calculates the actual PCR for all F&O symbols,
and inserts it into the database for yesterday's date (2026-07-05).
"""
import sys
import os
import zipfile
import requests
import pandas as pd
from datetime import date

# Append backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.utils.db import get_db_cursor, q, is_postgres

def download_file(url, local_filename):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }
    try:
        r = requests.get(url, headers=headers, stream=True, timeout=30)
        if r.status_code == 200:
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk:
                        f.write(chunk)
            return True
        else:
            print(f"Download failed: HTTP {r.status_code}")
            return False
    except Exception as e:
        print(f"Download error: {e}")
        return False

def main():
    # We will use Friday, May 24, 2024 as the reference historical date
    url = "https://archives.nseindia.com/content/historical/DERIVATIVES/2024/MAY/fo24MAY2024bhav.csv.zip"
    zip_path = "fo24MAY2024bhav.csv.zip"
    csv_path = "fo24MAY2024bhav.csv"
    
    print(f"Downloading real NSE F&O Bhavcopy from: {url}")
    if not download_file(url, zip_path):
        print("Failed to download historical Bhavcopy from NSE.")
        return
        
    print("Extracting ZIP archive...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(".")
    except Exception as e:
        print(f"Failed to extract ZIP: {e}")
        return
        
    print("Parsing Bhavcopy...")
    try:
        df = pd.read_csv(csv_path)
        df.columns = [c.strip() for c in df.columns]
    except Exception as e:
        print(f"Failed to parse CSV: {e}")
        return
        
    # Filter for Options and Futures
    df = df[df['INSTRUMENT'].isin(['OPTIDX', 'OPTSTK', 'FUTIDX', 'FUTSTK'])]
    df['SYMBOL'] = df['SYMBOL'].str.strip()
    df['OPTION_TYP'] = df['OPTION_TYP'].str.strip()
    
    # Yesterday's date
    yesterday_str = "2026-07-05"
    
    print(f"Aggregating options data for {yesterday_str}...")
    symbols = df['SYMBOL'].unique()
    rows = []
    
    for sym in symbols:
        sym_df = df[df['SYMBOL'] == sym]
        
        # Calculate Call/Put OI
        call_oi = int(sym_df[sym_df['OPTION_TYP'] == 'CE']['OPEN_INT'].sum())
        put_oi = int(sym_df[sym_df['OPTION_TYP'] == 'PE']['OPEN_INT'].sum())
        
        # Calculate PCR
        pcr = round(put_oi / call_oi, 2) if call_oi > 0 else 1.0
        signal = "Bullish" if pcr >= 1.0 else "Neutral" if pcr >= 0.75 else "Bearish"
        
        # Find closing price from Futures as LTP
        fut_df = sym_df[sym_df['INSTRUMENT'].isin(['FUTIDX', 'FUTSTK'])]
        if not fut_df.empty:
            ltp = float(fut_df.iloc[0]['CLOSE'])
            open_p = float(fut_df.iloc[0]['OPEN'])
            high = float(fut_df.iloc[0]['HIGH'])
            low = float(fut_df.iloc[0]['LOW'])
        else:
            # Fallback to Option close
            ltp = float(sym_df.iloc[0]['CLOSE']) if not sym_df.empty else 0.0
            open_p = ltp
            high = ltp
            low = ltp
            
        # Determine Max Pain (strike with maximum OI)
        opt_df = sym_df[sym_df['INSTRUMENT'].isin(['OPTIDX', 'OPTSTK'])]
        if not opt_df.empty:
            max_pain = float(opt_df.loc[opt_df['OPEN_INT'].idxmax()]['STRIKE_PR'])
        else:
            max_pain = 0.0
            
        rows.append((
            yesterday_str,
            sym,
            ltp,
            open_p,
            high,
            low,
            open_p, # prev_close fallback
            call_oi,
            put_oi,
            pcr,
            signal,
            max_pain,
            0.0 # price_chg_pct
        ))

    print(f"Connecting to database and saving {len(rows)} snapshots...")
    try:
        with get_db_cursor() as (c, conn):
            if is_postgres():
                query = """
                    INSERT INTO daily_snapshot
                        (trade_date, symbol, ltp, open, high, low, prev_close,
                         call_oi, put_oi, pcr, signal, max_pain, price_chg_pct)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (trade_date, symbol) DO UPDATE SET
                        ltp = EXCLUDED.ltp,
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        prev_close = EXCLUDED.prev_close,
                        call_oi = EXCLUDED.call_oi,
                        put_oi = EXCLUDED.put_oi,
                        pcr = EXCLUDED.pcr,
                        signal = EXCLUDED.signal,
                        max_pain = EXCLUDED.max_pain,
                        price_chg_pct = EXCLUDED.price_chg_pct
                """
            else:
                query = """
                    INSERT OR REPLACE INTO daily_snapshot
                        (trade_date, symbol, ltp, open, high, low, prev_close,
                         call_oi, put_oi, pcr, signal, max_pain, price_chg_pct)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """
            c.executemany(q(query), rows)
            conn.commit()
        print(f"Successfully loaded {len(rows)} yesterday records into the database.")
    except Exception as e:
        print(f"Failed to save snapshots: {e}")
    finally:
        # Cleanup files
        if os.path.exists(zip_path):
            os.remove(zip_path)
        if os.path.exists(csv_path):
            os.remove(csv_path)
            
if __name__ == "__main__":
    main()
