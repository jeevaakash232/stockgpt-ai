import pandas as pd
import logging

logger = logging.getLogger(__name__)

def calculate_max_pain(df: pd.DataFrame) -> float:
    """
    Calculate the Max Pain strike price.
    Max Pain is the strike at which option buyers lose the most money
    (and writers gain the most).
    """
    if df.empty:
        return 0.0

    # 1. Standardise option records to list of {strike, call_oi, put_oi}
    strikes_data = []
    
    # Live OptionChainLive format
    if "call_oi" in df.columns and "put_oi" in df.columns and "strike_price" in df.columns:
        for _, r in df.iterrows():
            strikes_data.append({
                "strike": float(r["strike_price"]),
                "call_oi": int(r["call_oi"]),
                "put_oi": int(r["put_oi"])
            })
    # Bhavcopy format
    elif "open_interest" in df.columns and "option_type" in df.columns and "strike_price" in df.columns:
        strike_groups = df.groupby("strike_price")
        for st_val, group in strike_groups:
            c_oi = group[group["option_type"] == "CE"]["open_interest"].sum()
            p_oi = group[group["option_type"] == "PE"]["open_interest"].sum()
            strikes_data.append({
                "strike": float(st_val),
                "call_oi": int(c_oi),
                "put_oi": int(p_oi)
            })
    else:
        logger.warning("calculate_max_pain: unrecognized columns %s", df.columns)
        return 0.0

    if not strikes_data:
        return 0.0

    strike_prices = [s["strike"] for s in strikes_data]
    pain_map = {}

    for test_strike in strike_prices:
        total_pain = 0.0
        for s in strikes_data:
            strike = s["strike"]
            # Call buyers lose if expiry strike (test_strike) is below written strike (strike)
            # Wait, call value at expiry is max(0, Spot - Strike).
            # Option buyer loses their premium if Spot <= Strike.
            # But the "Pain" calculation standardly computes the value of options at expiry:
            # Pain for Calls: Call_OI * max(0, Spot - Strike)
            # Pain for Puts: Put_OI * max(0, Strike - Spot)
            # Let's verify: at test_strike (Spot), the payout to Call buyers is max(0, test_strike - strike).
            # The seller has to pay this amount out. So this is the pain/loss for option writers.
            # Max Pain minimizes the total liability of option sellers (writers).
            # Liability = Call_OI * max(0, test_strike - strike) + Put_OI * max(0, strike - test_strike)
            if test_strike > strike:
                total_pain += s["call_oi"] * (test_strike - strike)
            elif test_strike < strike:
                total_pain += s["put_oi"] * (strike - test_strike)
                
        pain_map[test_strike] = total_pain

    if not pain_map:
        return 0.0
        
    # Return the strike price that minimizes total writer liability (pain)
    return float(min(pain_map, key=pain_map.get))
