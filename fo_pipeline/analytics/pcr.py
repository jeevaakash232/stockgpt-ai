import pandas as pd
import logging

logger = logging.getLogger(__name__)

def calculate_total_pcr(df: pd.DataFrame) -> float:
    """
    Calculate Put-Call Ratio (PCR) by Open Interest.
    Formula: Total Put Open Interest / Total Call Open Interest
    """
    if df.empty:
        return 0.0
        
    # Check if we have call_oi/put_oi columns (live OptionChainLive format)
    if "call_oi" in df.columns and "put_oi" in df.columns:
        total_call_oi = df["call_oi"].sum()
        total_put_oi = df["put_oi"].sum()
    # Check if we have open_interest and option_type (bhavcopy format)
    elif "open_interest" in df.columns and "option_type" in df.columns:
        total_call_oi = df[df["option_type"] == "CE"]["open_interest"].sum()
        total_put_oi = df[df["option_type"] == "PE"]["open_interest"].sum()
    else:
        logger.warning("calculate_total_pcr: unrecognized columns %s", df.columns)
        return 0.0

    if total_call_oi == 0:
        return 0.0
    return round(float(total_put_oi / total_call_oi), 2)


def calculate_mean_pcr(df_pcr_list: list[float]) -> float:
    """
    Calculate arithmetic mean of a list of PCR values.
    """
    valid_pcrs = [p for p in df_pcr_list if p is not None and p > 0]
    if not valid_pcrs:
        return 0.0
    return round(sum(valid_pcrs) / len(valid_pcrs), 2)


def calculate_put_call_volume_ratio(df: pd.DataFrame) -> float:
    """
    Calculate Put-Call Ratio by Traded Volume.
    Formula: Total Put Volume / Total Call Volume
    """
    if df.empty:
        return 0.0

    # Live OptionChainLive format
    if "call_volume" in df.columns and "put_volume" in df.columns:
        total_call_vol = df["call_volume"].sum()
        total_put_vol = df["put_volume"].sum()
    # Bhavcopy format (contracts column)
    elif "contracts" in df.columns and "option_type" in df.columns:
        total_call_vol = df[df["option_type"] == "CE"]["contracts"].sum()
        total_put_vol = df[df["option_type"] == "PE"]["contracts"].sum()
    else:
        return 0.0

    if total_call_vol == 0:
        return 0.0
    return round(float(total_put_vol / total_call_vol), 2)
