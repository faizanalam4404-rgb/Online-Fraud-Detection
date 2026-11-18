"""
FraudGuard – Machine Learning Preprocessing & Feature Engineering
==================================================================
Transforms raw payment parameters into domain-engineered financial features:
- Discrepancy analysis for origin balance exhaustion
- Destination mule zero-trace detection
- Corridor rail risk classification
- Temporal hour-of-day feature extraction

Supports both Polars (default high-performance zero-conflict engine)
and Pandas for maximum compatibility.
"""

try:
    import polars as pl
    _USE_POLARS = True
except ImportError:
    _USE_POLARS = False
    try:
        import pandas as pd
    except ImportError:
        pd = None

CATEGORICAL_FEATURES = ["type"]

NUMERICAL_FEATURES = [
    "amount",
    "oldbalanceOrg",
    "newbalanceOrig",
    "oldbalanceDest",
    "newbalanceDest",
    "hour_of_day",
    "errorBalanceOrig",
    "errorBalanceDest",
    "drainRatio",
    "zeroDestFlag",
    "isHighRiskType"
]

ALL_INPUT_FEATURES = CATEGORICAL_FEATURES + NUMERICAL_FEATURES

def feature_engineering(df):
    """
    Computes domain-specific engineered banking features on DataFrame (Polars or Pandas).
    """
    if _USE_POLARS and isinstance(df, pl.DataFrame):
        # Polars transformations
        expressions = []
        if "hour_of_day" not in df.columns:
            if "step" in df.columns:
                expressions.append((pl.col("step") % 24).alias("hour_of_day"))
            else:
                expressions.append(pl.lit(12).alias("hour_of_day"))

        expressions.extend([
            ((pl.col("newbalanceOrig") + pl.col("amount")) - pl.col("oldbalanceOrg")).alias("errorBalanceOrig"),
            ((pl.col("oldbalanceDest") + pl.col("amount")) - pl.col("newbalanceDest")).alias("errorBalanceDest"),
            (pl.col("amount") / (pl.col("oldbalanceOrg") + 1.0)).clip(0.0, 10.0).alias("drainRatio"),
            ((pl.col("oldbalanceDest") == 0.0) & (pl.col("newbalanceDest") == 0.0)).cast(pl.Int64).alias("zeroDestFlag"),
            pl.col("type").is_in(["TRANSFER", "CASH_OUT"]).cast(pl.Int64).alias("isHighRiskType")
        ])
        return df.with_columns(expressions)
    else:
        # Pandas transformations
        df = df.copy()
        if "hour_of_day" not in df.columns:
            if "step" in df.columns:
                df["hour_of_day"] = df["step"] % 24
            else:
                df["hour_of_day"] = 12

        df["errorBalanceOrig"] = (df["newbalanceOrig"] + df["amount"]) - df["oldbalanceOrg"]
        df["errorBalanceDest"] = (df["oldbalanceDest"] + df["amount"]) - df["newbalanceDest"]
        df["drainRatio"] = (df["amount"] / (df["oldbalanceOrg"] + 1.0)).clip(0.0, 10.0)
        df["zeroDestFlag"] = ((df["oldbalanceDest"] == 0.0) & (df["newbalanceDest"] == 0.0)).astype(int)
        df["isHighRiskType"] = df["type"].isin(["TRANSFER", "CASH_OUT"]).astype(int)
        return df

def build_single_prediction_df(amount_usd, trans_type, old_org, new_orig, old_dest, new_dest, hour_of_day=12):
    """
    Builds a single-row DataFrame formatted identically to the training set schema.
    Returns: (dataframe, engineered_features_dict)
    """
    t_type = str(trans_type).strip().upper()
    amt = float(amount_usd)
    o_org = float(old_org)
    n_orig = float(new_orig)
    o_dest = float(old_dest)
    n_dest = float(new_dest)
    hr = int(hour_of_day)

    err_orig = (n_orig + amt) - o_org
    err_dest = (o_dest + amt) - n_dest
    drain = min(amt / (o_org + 1.0), 10.0)
    zero_dest = 1 if (o_dest == 0.0 and n_dest == 0.0) else 0
    high_risk = 1 if t_type in ["TRANSFER", "CASH_OUT"] else 0

    row_data = {
        "type": [t_type],
        "amount": [amt],
        "oldbalanceOrg": [o_org],
        "newbalanceOrig": [n_orig],
        "oldbalanceDest": [o_dest],
        "newbalanceDest": [n_dest],
        "hour_of_day": [hr],
        "errorBalanceOrig": [err_orig],
        "errorBalanceDest": [err_dest],
        "drainRatio": [drain],
        "zeroDestFlag": [zero_dest],
        "isHighRiskType": [high_risk]
    }

    if _USE_POLARS:
        df = pl.DataFrame(row_data)
    else:
        import pandas as pd
        df = pd.DataFrame(row_data)

    engineered_dict = {
        "errorBalanceOrig": round(err_orig, 2),
        "errorBalanceDest": round(err_dest, 2),
        "drainRatio": round(drain, 4),
        "zeroDestFlag": zero_dest,
        "isHighRiskType": high_risk,
        "hour_of_day": hr
    }

    return df, engineered_dict
