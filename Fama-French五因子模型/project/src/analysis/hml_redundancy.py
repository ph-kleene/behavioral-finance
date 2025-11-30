from __future__ import annotations

import pandas as pd
import statsmodels.api as sm

from paths import OUTPUT_TABLE_DIR
from utils.data_loader import load_factors
from utils.io import write_csv
from utils.logging import get_logger

LOGGER = get_logger("analysis.hml_redundancy")

OUTPUT_FILE = OUTPUT_TABLE_DIR / "hml_redundancy_regression.csv"
FACTOR_COLUMNS = ["MKT", "SMB", "RMW", "CMA"]


def run_regression(factors: pd.DataFrame) -> pd.DataFrame:
    """
    Run regression of HML on other factors to test redundancy.
    
    Args:
        factors: DataFrame of factors.
        
    Returns:
        DataFrame with regression summary.
    """
    y = factors["HML"]
    X = sm.add_constant(factors[FACTOR_COLUMNS])
    model = sm.OLS(y, X, missing="drop").fit()

    result = {
        "alpha": model.params.get("const", float("nan")),
        "alpha_t": model.tvalues.get("const", float("nan")),
        "adj_r2": model.rsquared_adj,
    }
    for col in FACTOR_COLUMNS:
        result[f"beta_{col}"] = model.params.get(col, float("nan"))
        result[f"t_{col}"] = model.tvalues.get(col, float("nan"))
    return pd.DataFrame([result])


def main() -> None:
    """Main entry point for HML redundancy test."""
    factors = load_factors()
    summary = run_regression(factors)
    write_csv(summary, OUTPUT_FILE, index=False)
    LOGGER.info(
        "HML redundancy regression done: alpha %.4f (t=%.2f)",
        summary.loc[0, "alpha"],
        summary.loc[0, "alpha_t"],
    )


if __name__ == "__main__":
    main()
