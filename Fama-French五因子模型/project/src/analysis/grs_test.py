from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import f

from paths import OUTPUT_TABLE_DIR
from utils.data_loader import load_aligned_data
from utils.io import write_csv
from utils.logging import get_logger

LOGGER = get_logger("analysis.grs_test")

OUTPUT_FILE = OUTPUT_TABLE_DIR / "grs_test.csv"

FACTOR_COLUMNS = ["MKT", "SMB", "HML", "RMW", "CMA"]


def compute_grs(factors: pd.DataFrame, portfolios: pd.DataFrame) -> dict:
    """
    Compute GRS test statistic for the FF5 model.
    
    Args:
        factors: DataFrame of factors.
        portfolios: DataFrame of test portfolio returns.
        
    Returns:
        Dictionary containing GRS statistic and p-value.
    """
    factor_data = factors[FACTOR_COLUMNS]
    rf = factors["Rf"]
    excess_returns = portfolios.sub(rf, axis=0)
    excess_returns = excess_returns.dropna()
    factor_data = factor_data.loc[excess_returns.index]

    X = sm.add_constant(factor_data)
    residuals = []
    alphas = []

    for column in excess_returns.columns:
        model = sm.OLS(excess_returns[column], X, missing="drop").fit()
        residuals.append(model.resid)
        alphas.append(model.params.get("const", float("nan")))

    residuals_df = pd.concat(residuals, axis=1)
    residuals_df.columns = excess_returns.columns

    alphas_vector = pd.Series(alphas, index=excess_returns.columns)
    cov_resid = residuals_df.cov()

    T = len(excess_returns)
    N = len(excess_returns.columns)
    K = len(FACTOR_COLUMNS)

    mu_f = factor_data.mean().to_numpy()
    cov_f = factor_data.cov().to_numpy()

    sigma_e_inv = np.linalg.pinv(cov_resid.to_numpy())
    sigma_f_inv = np.linalg.pinv(cov_f)

    term1 = (T - N - K) / N
    term2 = 1 / (1 + mu_f.T @ sigma_f_inv @ mu_f)
    term3 = alphas_vector.to_numpy().T @ sigma_e_inv @ alphas_vector.to_numpy()

    grs_stat = term1 * term2 * term3
    p_value = 1 - f.cdf(grs_stat, N, T - N - K)

    return {
        "N_assets": N,
        "T": T,
        "K_factors": K,
        "GRS_stat": grs_stat,
        "p_value": p_value,
    }


def main() -> None:
    """Main entry point for GRS test."""
    factors, portfolios = load_aligned_data()
    results = compute_grs(factors, portfolios)
    write_csv(pd.DataFrame([results]), OUTPUT_FILE, index=False)
    LOGGER.info("Computed GRS test statistic = %.3f (p=%.3f)", results["GRS_stat"], results["p_value"])


if __name__ == "__main__":
    main()
