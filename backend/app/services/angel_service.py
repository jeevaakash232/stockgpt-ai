"""
Angel One SmartAPI Service
--------------------------
Provides LIVE option chain, PCR, OI, Max Pain and stock quotes
using Angel One SmartAPI (completely free).

How it works:
  1. Instrument master (Angel One public JSON) — cached 24h
     Contains token numbers for every NSE option contract.
  2. getMarketData FULL — fetches live OI + LTP per token
  3. PCR / Max Pain calculated from live OI data

Credentials from .env:
  ANGEL_API_KEY, ANGEL_CLIENT_ID, ANGEL_PASSWORD, ANGEL_TOTP_SECRET
"""

import os
import json
import logging
import threading
import time
import urllib.request
from datetime import datetime, date
from typing import Optional

import pyotp
from dotenv import load_dotenv
from SmartApi import SmartConnect

from app.services import cache_service
from app.services.pcr_service import calculate_pcr, signal as pcr_signal

logger = logging.getLogger(__name__)
load_dotenv(override=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INSTRUMENT_MASTER_URL = (
    "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
)

# Disk cache path — saves the 156k-record JSON locally, reloaded daily
_CACHE_DIR  = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_MASTER_FILE = os.path.join(_CACHE_DIR, "instrument_master.json")
_MASTER_DATE_FILE = os.path.join(_CACHE_DIR, "instrument_master_date.txt")

# NSE symbol → Angel One token for ALL F&O equity symbols + indices
# Auto-generated from Angel One instrument master (NFO OPTSTK + NSE EQ)
CASH_TOKENS = {
    "360ONE": "13061", "ABB": "13", "ABCAPITAL": "21614",
    "ADANIENSOL": "10217", "ADANIENT": "25", "ADANIGREEN": "3563",
    "ADANIPORTS": "15083", "ADANIPOWER": "17388", "ALKEM": "11703",
    "AMBER": "1185", "AMBUJACEM": "1270", "ANGELONE": "324",
    "APLAPOLLO": "25780", "APOLLOHOSP": "157", "ASHOKLEY": "212",
    "ASIANPAINT": "236", "ASTRAL": "14418", "AUBANK": "21238",
    "AUROPHARMA": "275", "AXISBANK": "5900", "BAJAJ-AUTO": "16669",
    "BAJAJFINSV": "16675", "BAJAJHLDNG": "305", "BAJFINANCE": "317",
    "BANDHANBNK": "2263", "BANKBARODA": "4668", "BANKINDIA": "4745",
    "BANKNIFTY": "26009", "BDL": "2144", "BEL": "383",
    "BHARATFORG": "422", "BHARTIARTL": "10604", "BHEL": "438",
    "BIOCON": "11373", "BLUESTARCO": "8311", "BOSCHLTD": "2181",
    "BPCL": "526", "BRITANNIA": "547", "BSE": "19585",
    "CAMS": "342", "CANBK": "10794", "CDSL": "21174",
    "CGPOWER": "760", "CHOLAFIN": "685", "CIPLA": "694",
    "COALINDIA": "20374", "COCHINSHIP": "21508", "COFORGE": "11543",
    "COLPAL": "15141", "CONCOR": "4749", "CROMPTON": "17094",
    "CUMMINSIND": "1901", "DABUR": "772", "DALBHARAT": "8075",
    "DELHIVERY": "9599", "DIVISLAB": "10940", "DIXON": "21690",
    "DLF": "14732", "DMART": "19913", "DRREDDY": "881",
    "EICHERMOT": "910", "ETERNAL": "5097", "EXIDEIND": "676",
    "FEDERALBNK": "1023", "FINNIFTY": "26037", "FORCEMOT": "11573",
    "FORTIS": "14592", "GAIL": "4717", "GLENMARK": "7406",
    "GMRAIRPORT": "13528", "GODFRYPHLP": "1181", "GODREJCP": "10099",
    "GODREJPROP": "17875", "GRASIM": "1232", "HAL": "2303",
    "HAVELLS": "9819", "HCLTECH": "7229", "HDFCAMC": "4244",
    "HDFCBANK": "1333", "HDFCLIFE": "467", "HEROMOTOCO": "1348",
    "HINDALCO": "1363", "HINDPETRO": "1406", "HINDUNILVR": "1394",
    "HINDZINC": "1424", "HYUNDAI": "25844", "ICICIBANK": "4963",
    "ICICIGI": "21770", "ICICIPRULI": "18652", "IDEA": "14366",
    "IDFCFIRSTB": "11184", "IEX": "220", "INDHOTEL": "1512",
    "INDIANB": "14309", "INDIGO": "11195", "INDUSINDBK": "5258",
    "INDUSTOWER": "29135", "INFY": "1594", "INOXWIND": "7852",
    "IOC": "1624", "IREDA": "20261", "IRFC": "2029",
    "ITC": "1660", "JINDALSTEL": "6733", "JIOFIN": "18143",
    "JSWENERGY": "17869", "JSWSTEEL": "11723", "JUBLFOOD": "18096",
    "KALYANKJIL": "2955", "KAYNES": "12092", "KEI": "13310",
    "KFINTECH": "13359", "KOTAKBANK": "1922", "KPITTECH": "9683",
    "LAURUSLABS": "19234", "LICHSGFIN": "1997", "LICI": "9480",
    "LODHA": "3220", "LT": "11483", "LTF": "24948",
    "LTM": "17818", "LUPIN": "10440", "M&M": "2031",
    "MANAPPURAM": "19061", "MANKIND": "15380", "MARICO": "4067",
    "MARUTI": "10999", "MAXHEALTH": "22377", "MAZDOCK": "509",
    "MCX": "31181", "MFSL": "2142", "MOTHERSON": "4204",
    "MOTILALOFS": "14947", "MPHASIS": "4503", "MUTHOOTFIN": "23650",
    "NAM-INDIA": "357", "NATIONALUM": "6364", "NAUKRI": "13751",
    "NBCC": "31415", "NESTLEIND": "17963", "NHPC": "17400",
    "NIFTY": "26000", "NMDC": "15332", "NTPC": "11630",
    "NUVAMA": "18721", "NYKAA": "6545", "OBEROIRLTY": "20242",
    "OFSS": "10738", "OIL": "17438", "ONGC": "2475",
    "PAGEIND": "14413", "PATANJALI": "17029", "PAYTM": "6705",
    "PERSISTENT": "18365", "PETRONET": "11351", "PFC": "14299",
    "PGEL": "25358", "PHOENIXLTD": "14552", "PIDILITIND": "2664",
    "PIIND": "24184", "PNB": "10666", "PNBHOUSING": "18908",
    "POLICYBZR": "6656", "POLYCAB": "9590", "POWERGRID": "14977",
    "POWERINDIA": "18457", "PRESTIGE": "20302", "RADICO": "10990",
    "RBLBANK": "18391", "RECLTD": "15355", "RELIANCE": "2885",
    "RVNL": "9552", "SAIL": "2963", "SBICARD": "17971",
    "SBILIFE": "21808", "SBIN": "3045", "SENSEX": "1",
    "SHREECEM": "3103", "SHRIRAMFIN": "4306", "SIEMENS": "3150",
    "SOLARINDS": "13332", "SONACOMS": "4684", "SRF": "3273",
    "SUNPHARMA": "3351", "SUPREMEIND": "3363", "SUZLON": "12018",
    "SWIGGY": "27066", "TATACONSUM": "3432", "TATAELXSI": "3411",
    "TATAPOWER": "3426", "TATASTEEL": "3499", "TCS": "11536",
    "TECHM": "13538", "TIINDIA": "312", "TITAN": "3506",
    "TORNTPHARM": "3518", "TRENT": "1964", "TVSMOTOR": "8479",
    "ULTRACEMCO": "11532", "UNIONBANK": "10753", "UNITDSPR": "10447",
    "UNOMINDA": "14154", "UPL": "11287", "VBL": "18921",
    "VEDL": "3063", "VOLTAS": "3718", "WAAREEENER": "25907",
    "WIPRO": "3787", "YESBANK": "11915", "ZYDUSLIFE": "7929",
}

# F&O symbols that have weekly options (OPTIDX)
INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY"}

CACHE_TTL          = 60       # seconds — live data
INSTRUMENT_TTL     = 86400    # seconds — 24h for instrument master
MAX_STRIKES_BATCH  = 50       # Angel One free tier: max 50 tokens per API call
ATM_WINDOW         = 20       # Only fetch ATM ± 20 strikes (40 total = 2 batches of 20)

_session_lock   = threading.RLock()
_smart_obj: Optional[SmartConnect] = None
_session_expiry: float = 0


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def _get_session() -> SmartConnect:
    """Return authenticated SmartConnect, auto-renewing after 23h."""
    global _smart_obj, _session_expiry

    with _session_lock:
        now = time.time()
        if _smart_obj is not None and now < _session_expiry:
            return _smart_obj

        load_dotenv(override=True)
        api_key     = os.getenv("ANGEL_API_KEY",     "").strip()
        client_id   = os.getenv("ANGEL_CLIENT_ID",   "").strip()
        password    = os.getenv("ANGEL_PASSWORD",     "").strip()
        totp_secret = os.getenv("ANGEL_TOTP_SECRET", "").strip()

        if not all([api_key, client_id, password, totp_secret]):
            raise EnvironmentError(
                "Angel One credentials missing in .env: "
                "ANGEL_API_KEY, ANGEL_CLIENT_ID, ANGEL_PASSWORD, ANGEL_TOTP_SECRET"
            )

        obj  = SmartConnect(api_key=api_key)
        obj.timeout = 15   # increase from default 7s to 15s
        totp = pyotp.TOTP(totp_secret).now()
        resp = obj.generateSession(client_id, password, totp)

        if not resp.get("status"):
            raise ConnectionError(
                f"Angel One login failed: {resp.get('message', 'Unknown error')}"
            )

        _smart_obj      = obj
        _session_expiry = now + (23 * 3600)
        logger.info("Angel One session created — client: %s", client_id)
        return _smart_obj


# ---------------------------------------------------------------------------
# Instrument Master
# ---------------------------------------------------------------------------

def _load_instrument_master() -> list[dict]:
    """
    Load Angel One instrument master.
    Uses a local disk cache (data/instrument_master.json) refreshed daily.
    Falls back to in-memory cache after first load for speed.
    """
    return cache_service.get_or_fetch(
        "angel_instrument_master",
        _fetch_or_load_instrument_master,
        ttl=INSTRUMENT_TTL,
    )


def _fetch_or_load_instrument_master() -> list[dict]:
    """Load from disk if today's file exists, otherwise download and save."""
    os.makedirs(_CACHE_DIR, exist_ok=True)
    today = str(date.today())

    # Check if we have today's cached file on disk
    if os.path.isfile(_MASTER_FILE) and os.path.isfile(_MASTER_DATE_FILE):
        with open(_MASTER_DATE_FILE, "r") as f:
            cached_date = f.read().strip()
        if cached_date == today:
            logger.info("Loading instrument master from disk cache...")
            with open(_MASTER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info("Instrument master loaded from disk: %d instruments", len(data))
            return data

    # Download fresh copy
    return _fetch_instrument_master()


def _fetch_instrument_master() -> list[dict]:
    logger.info("Downloading Angel One instrument master...")
    req = urllib.request.Request(
        INSTRUMENT_MASTER_URL,
        headers={"User-Agent": "StockGPT/2.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    logger.info("Instrument master downloaded: %d instruments", len(data))

    # Save to disk for today
    os.makedirs(_CACHE_DIR, exist_ok=True)
    with open(_MASTER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)
    with open(_MASTER_DATE_FILE, "w") as f:
        f.write(str(date.today()))
    logger.info("Instrument master saved to disk cache.")
    # Clear the in-memory index so it gets rebuilt from new data
    global _instrument_index
    with _instrument_index_lock:
        _instrument_index = {}
    return data


def _get_option_tokens(symbol: str, expiry: str, opt_type: str) -> list[dict]:
    """
    Return list of {token, strike} for a symbol+expiry+CE/PE.
    Strike is divided by 100 to get actual value (Angel stores as *100).
    Uses a pre-built index for O(1) lookups instead of scanning 156k records.
    """
    index = _get_instrument_index()
    key   = (symbol.upper(), expiry, opt_type)
    return index.get(key, [])


def _get_nearest_expiries(symbol: str) -> list[str]:
    """Return the nearest 5 expiry dates for a symbol from the instrument master."""
    index   = _get_instrument_index()
    sym_up  = symbol.upper()
    expiries = set()

    for (sym, exp, _) in index.keys():
        if sym == sym_up:
            expiries.add(exp)

    def _sort_key(e):
        try:
            return datetime.strptime(e, "%d%b%Y")
        except ValueError:
            return datetime.max

    return sorted(expiries, key=_sort_key)[:5]


# Pre-built index: (symbol, expiry, CE/PE) -> list of {token, strike}
_instrument_index: dict = {}
_instrument_index_lock = threading.Lock()


def _get_instrument_index() -> dict:
    """
    Build and cache a lookup index from the instrument master.
    Built once per day (whenever master is refreshed).
    """
    global _instrument_index
    with _instrument_index_lock:
        if _instrument_index:
            return _instrument_index
        instruments = _load_instrument_master()
        idx: dict = {}
        for inst in instruments:
            if inst.get("exch_seg") != "NFO":
                continue
            itype = inst.get("instrumenttype", "")
            if itype not in ("OPTIDX", "OPTSTK"):
                continue
            sym    = inst.get("name", "").upper()
            expiry = inst.get("expiry", "")
            symbol_name = inst.get("symbol", "")
            if not (sym and expiry and symbol_name):
                continue
            opt_type = "CE" if symbol_name.endswith("CE") else ("PE" if symbol_name.endswith("PE") else None)
            if not opt_type:
                continue
            try:
                strike = round(float(inst["strike"]) / 100, 0)
            except (KeyError, ValueError):
                continue
            key = (sym, expiry, opt_type)
            if key not in idx:
                idx[key] = []
            idx[key].append({"token": inst["token"], "strike": strike})
        _instrument_index = idx
        logger.info("Instrument index built: %d symbol/expiry/type combinations", len(idx))
        return _instrument_index


# ---------------------------------------------------------------------------
# Fetch OI from live market data
# ---------------------------------------------------------------------------

def _fetch_oi_for_tokens(tokens: list[str]) -> dict[str, dict]:
    """
    Fetch live OI + LTP for a list of NFO tokens.
    Returns dict: token -> {oi, ltp}
    Batches calls to stay within API limits (100 tokens per call).
    """
    smart   = _get_session()
    result  = {}

    for i in range(0, len(tokens), MAX_STRIKES_BATCH):
        batch = tokens[i : i + MAX_STRIKES_BATCH]
        try:
            resp = smart.getMarketData("FULL", {"NFO": batch})
            if not resp or not resp.get("status"):
                logger.warning("getMarketData failed for batch: %s", resp)
                continue
            for item in (resp.get("data", {}).get("fetched") or []):
                token = item.get("symbolToken") or item.get("token", "")
                result[str(token)] = {
                    "oi":  int(item.get("opnInterest", 0) or 0),
                    "ltp": float(item.get("ltp", 0) or 0),
                }
        except Exception as exc:
            logger.error("OI batch fetch error: %s", exc)
        time.sleep(0.05)  # small delay between batches

    return result


# ---------------------------------------------------------------------------
# Option Chain — the main public function
# ---------------------------------------------------------------------------

def get_option_chain_live(symbol: str) -> dict:
    """
    Returns LIVE option chain with per-strike Call/Put OI,
    total OI, PCR, Max Pain. Cached 60s.
    """
    key = f"angel_oc:{symbol.upper()}"
    return cache_service.get_or_fetch(
        key,
        lambda: _fetch_option_chain_live(symbol),
        ttl=CACHE_TTL,
    )


def _fetch_option_chain_live(symbol: str) -> dict:
    symbol   = symbol.upper()

    try:
        # 1. Get nearest expiry
        expiries = _get_nearest_expiries(symbol)
        if not expiries:
            logger.warning("No expiries found for %s, using fallback", symbol)
            return _fallback_oc(symbol)

        nearest_expiry = expiries[0]
        logger.info("Option chain [%s] expiry: %s", symbol, nearest_expiry)

        # 2. Get tokens for CE and PE
        ce_tokens = _get_option_tokens(symbol, nearest_expiry, "CE")
        pe_tokens = _get_option_tokens(symbol, nearest_expiry, "PE")

        if not ce_tokens and not pe_tokens:
            logger.warning("No tokens found for %s %s", symbol, nearest_expiry)
            return _fallback_oc(symbol)

        # Limit to ATM ± 20 strikes to stay within API token limits
        # Get the underlying price to find ATM strike
        underlying_price = _get_underlying_price(symbol)
        
        def atm_sort_key(item):
            return abs(item["strike"] - underlying_price) if underlying_price else item["strike"]

        ce_tokens_limited = sorted(ce_tokens, key=atm_sort_key)[:ATM_WINDOW]
        pe_tokens_limited = sorted(pe_tokens, key=atm_sort_key)[:ATM_WINDOW]

        all_tokens_info = {t["token"]: t["strike"] for t in ce_tokens_limited + pe_tokens_limited}
        token_list      = list(all_tokens_info.keys())  # max 40 tokens, well within limit

        # 3. Fetch live OI
        oi_data = _fetch_oi_for_tokens(token_list)

        # 4. Build strike table
        strike_map: dict[float, dict] = {}

        for item in ce_tokens_limited:
            tk = item["token"]
            st = item["strike"]
            if st not in strike_map:
                strike_map[st] = {"strike": st, "call_oi": 0, "put_oi": 0,
                                   "call_ltp": 0.0, "put_ltp": 0.0}
            live = oi_data.get(tk, {})
            strike_map[st]["call_oi"]  += live.get("oi",  0)
            strike_map[st]["call_ltp"]  = live.get("ltp", 0.0)

        for item in pe_tokens_limited:
            tk = item["token"]
            st = item["strike"]
            if st not in strike_map:
                strike_map[st] = {"strike": st, "call_oi": 0, "put_oi": 0,
                                   "call_ltp": 0.0, "put_ltp": 0.0}
            live = oi_data.get(tk, {})
            strike_map[st]["put_oi"]  += live.get("oi",  0)
            strike_map[st]["put_ltp"]  = live.get("ltp", 0.0)

        strikes       = sorted(strike_map.values(), key=lambda x: x["strike"])
        total_call_oi = sum(s["call_oi"] for s in strikes)
        total_put_oi  = sum(s["put_oi"]  for s in strikes)

        if total_call_oi == 0 and total_put_oi == 0:
            logger.warning("Zero OI returned for %s — market may be closed", symbol)
            return _fallback_oc(symbol)

        pcr      = calculate_pcr(total_call_oi, total_put_oi)
        max_pain = _calculate_max_pain(strikes)

        # Get underlying price
        underlying = _get_underlying_price(symbol)

        logger.info(
            "Live OC [%s]: %d strikes | call_oi=%d | put_oi=%d | pcr=%.2f | max_pain=%.0f",
            symbol, len(strikes), total_call_oi, total_put_oi, pcr, max_pain
        )

        return {
            "symbol":        symbol,
            "underlying":    underlying,
            "expiry":        nearest_expiry,
            "expiry_dates":  expiries,
            "total_call_oi": total_call_oi,
            "total_put_oi":  total_put_oi,
            "pcr":           pcr,
            "signal":        pcr_signal(pcr),
            "max_pain":      max_pain,
            "strikes":       strikes[:60],
            "source":        "angel_one_live",
        }

    except Exception as exc:
        logger.error("Option chain live failed [%s]: %s", symbol, exc)
        return _fallback_oc(symbol)


def _get_underlying_price(symbol: str) -> float:
    """Get the current index/stock price from Angel One."""
    try:
        token = CASH_TOKENS.get(symbol.upper())
        if not token:
            return 0.0
        smart = _get_session()
        resp  = smart.ltpData(
            "NSE",
            symbol if symbol in INDEX_SYMBOLS else f"{symbol}-EQ",
            token
        )
        if resp and resp.get("status"):
            return float(resp["data"].get("ltp", 0))
    except Exception as exc:
        logger.debug("Underlying price fetch failed [%s]: %s", symbol, exc)
    return 0.0


# ---------------------------------------------------------------------------
# Live Quote (cash segment)
# ---------------------------------------------------------------------------

def get_live_quote(symbol: str) -> dict:
    """Live OHLCV + change for a single NSE stock. Cached 60s."""
    key = f"angel_quote:{symbol.upper()}"
    return cache_service.get_or_fetch(
        key,
        lambda: _fetch_live_quote(symbol),
        ttl=CACHE_TTL,
    )


def _fetch_live_quote(symbol: str) -> dict:
    symbol = symbol.upper()
    token  = CASH_TOKENS.get(symbol)
    if not token:
        raise ValueError(f"Token not mapped for: {symbol}")

    smart    = _get_session()
    exchange = "NSE"
    trade_sym = symbol if symbol in INDEX_SYMBOLS else f"{symbol}-EQ"

    resp = smart.ltpData(exchange, trade_sym, token)
    if not resp or not resp.get("status"):
        raise ConnectionError(f"ltpData failed for {symbol}: {resp}")

    d     = resp["data"]
    ltp   = float(d.get("ltp",   0))
    close = float(d.get("close", 0))
    chg   = round(ltp - close, 2)   if close else 0.0
    pct   = round((chg / close) * 100, 2) if close else 0.0

    return {
        "symbol":     symbol,
        "ltp":        ltp,
        "open":       float(d.get("open",  0)),
        "high":       float(d.get("high",  0)),
        "low":        float(d.get("low",   0)),
        "close":      close,
        "change":     chg,
        "change_pct": pct,
        "source":     "angel_one_live",
    }


# ---------------------------------------------------------------------------
# Max Pain
# ---------------------------------------------------------------------------

def _calculate_max_pain(strikes: list[dict]) -> float:
    if not strikes:
        return 0.0
    prices    = [s["strike"] for s in strikes]
    pain_map  = {}
    for test in prices:
        pain = sum(
            s["call_oi"] * max(0, s["strike"] - test) +
            s["put_oi"]  * max(0, test - s["strike"])
            for s in strikes
        )
        pain_map[test] = pain
    return min(pain_map, key=pain_map.get)


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------

def _fallback_oc(symbol: str) -> dict:
    from app.services.market_data import get_market
    mkt    = {s["symbol"]: s for s in get_market()}
    s      = mkt.get(symbol.upper(), {})
    c_oi   = s.get("call_oi", 0)
    p_oi   = s.get("put_oi",  0)
    pcr    = calculate_pcr(c_oi, p_oi)
    return {
        "symbol":        symbol,
        "underlying":    s.get("ltp", 0),
        "expiry":        None,
        "expiry_dates":  [],
        "total_call_oi": c_oi,
        "total_put_oi":  p_oi,
        "pcr":           pcr,
        "signal":        pcr_signal(pcr),
        "max_pain":      s.get("max_pain", 0),
        "strikes":       [],
        "source":        "sample_fallback",
        "note":          "Live OI unavailable — market may be closed or data delayed.",
    }


# ---------------------------------------------------------------------------
# Startup warm-up
# ---------------------------------------------------------------------------

def warm_cache() -> None:
    """Pre-load instrument master and login in background at startup."""
    import threading
    def _warm():
        try:
            _get_session()
            _load_instrument_master()
            logger.info("Angel One warm-up complete.")
        except Exception as exc:
            logger.warning("Angel One warm-up failed: %s", exc)
    threading.Thread(target=_warm, daemon=True, name="angel-warmup").start()
