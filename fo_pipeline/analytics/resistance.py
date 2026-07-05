import pandas as pd

def calculate_resistance(df: pd.DataFrame) -> float:
    """
    Calculate Resistance level using Option Chain Call OI concentration.
    Resistance is the strike price with the maximum Call Open Interest.
    """
    if df.empty:
        return 0.0

    # Live OptionChainLive format
    if "call_oi" in df.columns and "strike_price" in df.columns:
        max_call_row = df.loc[df["call_oi"].idxmax()]
        return float(max_call_row["strike_price"])
    # Bhavcopy format
    elif "open_interest" in df.columns and "option_type" in df.columns and "strike_price" in df.columns:
        call_df = df[df["option_type"] == "CE"]
        if call_df.empty:
            return 0.0
        max_call_row = call_df.loc[call_df["open_interest"].idxmax()]
        return float(max_call_row["strike_price"])
        
    return 0.0
