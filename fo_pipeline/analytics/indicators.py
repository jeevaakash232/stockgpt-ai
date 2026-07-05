import pandas as pd
import logging

logger = logging.getLogger(__name__)

def calculate_max_call_oi(df: pd.DataFrame) -> dict:
    """Find strike and Call OI value where Call OI is highest."""
    if df.empty:
        return {"strike": 0.0, "value": 0}
    
    if "call_oi" in df.columns:
        idx = df["call_oi"].idxmax()
        row = df.loc[idx]
        return {"strike": float(row["strike_price"]), "value": int(row["call_oi"])}
    elif "open_interest" in df.columns and "option_type" in df.columns:
        call_df = df[df["option_type"] == "CE"]
        if call_df.empty:
            return {"strike": 0.0, "value": 0}
        idx = call_df["open_interest"].idxmax()
        row = call_df.loc[idx]
        return {"strike": float(row["strike_price"]), "value": int(row["open_interest"])}
    return {"strike": 0.0, "value": 0}


def calculate_max_put_oi(df: pd.DataFrame) -> dict:
    """Find strike and Put OI value where Put OI is highest."""
    if df.empty:
        return {"strike": 0.0, "value": 0}
    
    if "put_oi" in df.columns:
        idx = df["put_oi"].idxmax()
        row = df.loc[idx]
        return {"strike": float(row["strike_price"]), "value": int(row["put_oi"])}
    elif "open_interest" in df.columns and "option_type" in df.columns:
        put_df = df[df["option_type"] == "PE"]
        if put_df.empty:
            return {"strike": 0.0, "value": 0}
        idx = put_df["open_interest"].idxmax()
        row = put_df.loc[idx]
        return {"strike": float(row["strike_price"]), "value": int(row["open_interest"])}
    return {"strike": 0.0, "value": 0}


def calculate_max_call_change(df: pd.DataFrame) -> dict:
    """Find strike and Call OI change where change is highest."""
    if df.empty:
        return {"strike": 0.0, "value": 0}
    
    if "call_change_oi" in df.columns:
        idx = df["call_change_oi"].idxmax()
        row = df.loc[idx]
        return {"strike": float(row["strike_price"]), "value": int(row["call_change_oi"])}
    elif "change_in_oi" in df.columns and "option_type" in df.columns:
        call_df = df[df["option_type"] == "CE"]
        if call_df.empty:
            return {"strike": 0.0, "value": 0}
        idx = call_df["change_in_oi"].idxmax()
        row = call_df.loc[idx]
        return {"strike": float(row["strike_price"]), "value": int(row["change_in_oi"])}
    return {"strike": 0.0, "value": 0}


def calculate_max_put_change(df: pd.DataFrame) -> dict:
    """Find strike and Put OI change where change is highest."""
    if df.empty:
        return {"strike": 0.0, "value": 0}
    
    if "put_change_oi" in df.columns:
        idx = df["put_change_oi"].idxmax()
        row = df.loc[idx]
        return {"strike": float(row["strike_price"]), "value": int(row["put_change_oi"])}
    elif "change_in_oi" in df.columns and "option_type" in df.columns:
        put_df = df[df["option_type"] == "PE"]
        if put_df.empty:
            return {"strike": 0.0, "value": 0}
        idx = put_df["change_in_oi"].idxmax()
        row = put_df.loc[idx]
        return {"strike": float(row["strike_price"]), "value": int(row["change_in_oi"])}
    return {"strike": 0.0, "value": 0}


def calculate_oi_difference(df: pd.DataFrame) -> float:
    """Calculate Net Open Interest difference: Put OI - Call OI."""
    if df.empty:
        return 0.0

    if "call_oi" in df.columns and "put_oi" in df.columns:
        return float(df["put_oi"].sum() - df["call_oi"].sum())
    elif "open_interest" in df.columns and "option_type" in df.columns:
        total_call_oi = df[df["option_type"] == "CE"]["open_interest"].sum()
        total_put_oi = df[df["option_type"] == "PE"]["open_interest"].sum()
        return float(total_put_oi - total_call_oi)
    return 0.0


def calculate_atm_strike(df: pd.DataFrame, spot_price: float) -> float:
    """Determine the strike price closest to the underlying spot price."""
    if df.empty or not spot_price:
        return 0.0
        
    strikes = df["strike_price"].unique()
    if len(strikes) == 0:
        return 0.0
        
    # Get closest strike price
    return float(min(strikes, key=lambda x: abs(x - spot_price)))


def calculate_call_volume(df: pd.DataFrame) -> int:
    """Calculate aggregate Call Volume."""
    if df.empty:
        return 0
    if "call_volume" in df.columns:
        return int(df["call_volume"].sum())
    elif "contracts" in df.columns and "option_type" in df.columns:
        return int(df[df["option_type"] == "CE"]["contracts"].sum())
    return 0


def calculate_put_volume(df: pd.DataFrame) -> int:
    """Calculate aggregate Put Volume."""
    if df.empty:
        return 0
    if "put_volume" in df.columns:
        return int(df["put_volume"].sum())
    elif "contracts" in df.columns and "option_type" in df.columns:
        return int(df[df["option_type"] == "PE"]["contracts"].sum())
    return 0


def calculate_oi_buildup(df: pd.DataFrame) -> dict:
    """Compile maximum Call and Put open interest statistics."""
    return {
        "max_call_oi": calculate_max_call_oi(df),
        "max_put_oi": calculate_max_put_oi(df),
        "max_call_change": calculate_max_call_change(df),
        "max_put_change": calculate_max_put_change(df),
        "oi_difference": calculate_oi_difference(df)
    }
