"""
Populate Market History Utility
-------------------------------
Fetches current market snapshots for all F&O stocks and populates
the daily_snapshot database table for both yesterday and today.
"""
import sys
import os
from datetime import date, timedelta

# Append backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.utils.db import get_db_cursor, q, is_postgres
from app.services.market_data import _build_market

def main():
    print("Initializing Database Connection...")
    # Make sure tables exist
    from app.services.history_service import init_db
    init_db()

    print("Fetching live market data for ~210 F&O symbols from Angel One (this may take a few seconds)...")
    try:
        market_rows = _build_market()
        print(f"Successfully fetched {len(market_rows)} symbols.")
    except Exception as e:
        print(f"Error fetching market data from Angel One: {e}")
        return

    today_str = date.today().strftime("%Y-%m-%d")
    yesterday_str = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"Inserting data for YESTERDAY ({yesterday_str})...")
    save_snapshot_for_date(market_rows, yesterday_str)

    print(f"Inserting data for TODAY ({today_str})...")
    save_snapshot_for_date(market_rows, today_str)

    print("Data population completed successfully! Run 'python run.py' and reload your browser.")


def save_snapshot_for_date(market_rows, trade_date):
    rows = []
    for s in market_rows:
        if not s.get("symbol") or s.get("ltp", 0.0) <= 0:
            continue
        
        # Determine previous close fallback
        prev_close = s.get("prev_close")
        if prev_close is None:
            # try open or ltp
            prev_close = s.get("open", s.get("ltp", 0.0))

        rows.append((
            trade_date,
            s["symbol"],
            s.get("ltp", 0.0),
            s.get("open", 0.0),
            s.get("high", 0.0),
            s.get("low", 0.0),
            prev_close,
            s.get("call_oi", 0),
            s.get("put_oi", 0),
            s.get("pcr", 0.0),
            s.get("signal", "Neutral"),
            s.get("max_pain", 0.0),
            s.get("price_change", 0.0) if "price_change" in s else s.get("price_chg_pct", 0.0)
        ))

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
        print(f"Saved snapshot for {trade_date} ({len(rows)} symbols inserted/updated)")
    except Exception as e:
        print(f"Failed to save snapshot for {trade_date}: {e}")

if __name__ == "__main__":
    main()
