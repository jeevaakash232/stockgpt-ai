import pandas as pd

def calculate_support(df: pd.DataFrame) -> float:
    """
    Calculate Support level using Option Chain Put OI concentration.
    Support is the strike price with the maximum Put Open Interest.
    """
    if df.empty:
        return 0.0

    # Live OptionChainLive format
    if "put_oi" in df.columns and "strike_price" in df.columns:
        max_put_row = df.loc[df["put_oi"].idxmax()]
        return float(max_put_row["strike_price"])
    # Bhavcopy format
    elif "open_interest" in df.columns and "option_type" in df.columns and "strike_price" in df.columns:
        put_df = df[df["option_type"] == "PE"]
        if put_df.empty:
            return 0.0
        max_put_row = put_df.loc[put_df["open_interest"].idxmax()]
        return float(max_put_row["strike_price"])
        
    return 0.0
