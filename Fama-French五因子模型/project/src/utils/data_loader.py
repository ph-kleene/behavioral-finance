from __future__ import annotations

import pandas as pd

from paths import PROCESSED_DATA_DIR, OUTPUT_TABLE_DIR

FACTORS_FILE = PROCESSED_DATA_DIR / "factors_monthly.parquet"
PORTFOLIOS_FILE = PROCESSED_DATA_DIR / "test_portfolios_25.parquet"
MOMENTUM_FILE = PROCESSED_DATA_DIR / "momentum_factor.parquet"
REG_RESULTS_FILE = OUTPUT_TABLE_DIR / "regression_results_ff5_2x3.csv"

def load_factors(include_momentum: bool = False) -> pd.DataFrame:
    """
    Load monthly factors data.
    
    Args:
        include_momentum: Whether to merge momentum factor.
        
    Returns:
        DataFrame with factors indexed by trade_month.
    """
    if not FACTORS_FILE.exists():
        raise FileNotFoundError(f"Factors file not found: {FACTORS_FILE}")
        
    df = pd.read_parquet(FACTORS_FILE)
    df["trade_month"] = pd.to_datetime(df["trade_month"])
    df = df.set_index("trade_month").sort_index()

    if include_momentum and MOMENTUM_FILE.exists():
        mom = pd.read_parquet(MOMENTUM_FILE)
        mom["trade_month"] = pd.to_datetime(mom["trade_month"])
        mom = mom.set_index("trade_month")[["MOM"]]
        df = df.join(mom, how="left")
        
    return df

def load_portfolios() -> pd.DataFrame:
    """
    Load test portfolios (25 Size-BM portfolios).
    
    Returns:
        DataFrame with portfolio returns indexed by trade_month.
    """
    if not PORTFOLIOS_FILE.exists():
        raise FileNotFoundError(f"Portfolios file not found: {PORTFOLIOS_FILE}")
        
    df = pd.read_parquet(PORTFOLIOS_FILE)
    df["trade_month"] = pd.to_datetime(df["trade_month"])
    return df.set_index("trade_month").sort_index()

def load_regression_results() -> pd.DataFrame:
    """
    Load regression results for FF5 2x3 model.
    
    Returns:
        DataFrame with regression statistics.
    """
    if not REG_RESULTS_FILE.exists():
        raise FileNotFoundError(f"Regression results not found: {REG_RESULTS_FILE}")
        
    return pd.read_csv(REG_RESULTS_FILE)

def load_aligned_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load factors and portfolios, aligned by date index.
    
    Returns:
        Tuple of (factors, portfolios) DataFrames.
    """
    factors = load_factors()
    portfolios = load_portfolios()
    
    common_index = factors.index.intersection(portfolios.index)
    return factors.loc[common_index], portfolios.loc[common_index]
