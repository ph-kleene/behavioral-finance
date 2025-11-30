from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sklearn.metrics import r2_score

from paths import OUTPUT_FIGURE_DIR
from utils.data_loader import load_factors, load_portfolios, load_regression_results
from utils.logging import get_logger

LOGGER = get_logger("analysis.plot_predicted_vs_actual")

OUTPUT_FIG = OUTPUT_FIGURE_DIR / "predicted_vs_actual.png"

FACTOR_COLS = ["MKT", "SMB", "HML", "RMW", "CMA"]


def compute_means(portfolios: pd.DataFrame, factors: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """
    Compute mean excess returns for portfolios and factors.
    
    Args:
        portfolios: DataFrame of portfolio returns.
        factors: DataFrame of factors.
        
    Returns:
        Tuple of (actual_means, factor_means).
    """
    # Align dates
    common_index = portfolios.index.intersection(factors.index)
    portfolios = portfolios.loc[common_index]
    factors = factors.loc[common_index]

    # Actual excess returns
    rf = factors["Rf"]
    excess_returns = portfolios.sub(rf, axis=0)
    actual_means = excess_returns.mean()

    # Factor means
    factor_means = factors[FACTOR_COLS].mean()
    return actual_means, factor_means


def compute_predicted(
    reg_results: pd.DataFrame, factor_means: pd.Series
) -> pd.Series:
    """
    Compute predicted mean excess returns using regression betas and factor means.
    
    Args:
        reg_results: Regression results DataFrame.
        factor_means: Series of factor means.
        
    Returns:
        Series of predicted mean excess returns.
    """
    df = reg_results.set_index("portfolio")
    predicted = {}
    for port in df.index:
        pred_ret = 0.0
        for f in FACTOR_COLS:
            beta = df.loc[port, f"beta_{f}"]
            f_mean = factor_means[f]
            pred_ret += beta * f_mean
        predicted[port] = pred_ret
    return pd.Series(predicted, name="predicted_mean")


def plot_scatter(actual: pd.Series, predicted: pd.Series) -> None:
    """Plot scatter of actual vs predicted returns."""
    data = pd.DataFrame({"Actual": actual, "Predicted": predicted})
    r2 = r2_score(data["Actual"], data["Predicted"])

    plt.figure(figsize=(8, 8))
    sns.scatterplot(data=data, x="Predicted", y="Actual", s=100)
    
    # Add labels
    for port, row in data.iterrows():
        plt.text(row["Predicted"], row["Actual"], str(port), fontsize=9, ha="right")

    # 45-degree line
    min_val = min(data.min().min(), 0)
    max_val = data.max().max()
    plt.plot([min_val, max_val], [min_val, max_val], "r--", alpha=0.7, label="45-degree line")

    plt.title(f"Actual vs. Predicted Excess Returns (25 Portfolios)\nCross-sectional R2 = {r2:.3f}")
    plt.xlabel("Predicted Mean Excess Return")
    plt.ylabel("Actual Mean Excess Return")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    OUTPUT_FIG.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUTPUT_FIG, dpi=200)
    plt.close()


def main() -> None:
    """Main entry point for predicted vs actual plot."""
    portfolios = load_portfolios()
    factors = load_factors()
    reg_results = load_regression_results()
    
    actual_means, factor_means = compute_means(portfolios, factors)
    predicted_means = compute_predicted(reg_results, factor_means)
    
    # Align indices
    common = actual_means.index.intersection(predicted_means.index)
    plot_scatter(actual_means[common], predicted_means[common])
    LOGGER.info("Saved predicted vs actual plot to %s", OUTPUT_FIG)


if __name__ == "__main__":
    main()
