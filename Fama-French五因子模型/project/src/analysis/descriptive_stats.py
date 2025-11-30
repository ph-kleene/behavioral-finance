from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from paths import OUTPUT_FIGURE_DIR, OUTPUT_TABLE_DIR
from utils.data_loader import load_factors
from utils.io import write_csv
from utils.logging import get_logger

LOGGER = get_logger("analysis.descriptive_stats")

SUMMARY_OUTPUT = OUTPUT_TABLE_DIR / "factor_summary.csv"
CORR_OUTPUT = OUTPUT_TABLE_DIR / "factor_correlation.csv"
CUMRET_FIG = OUTPUT_FIGURE_DIR / "factor_cumulative.png"
CORR_FIG = OUTPUT_FIGURE_DIR / "factor_correlation.png"

FACTOR_COLUMNS = ["MKT", "SMB", "HML", "RMW", "CMA"]


def compute_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Compute descriptive statistics for factors."""
    monthly_mean = df.mean()
    monthly_std = df.std()
    summary = pd.DataFrame({
        "mean": monthly_mean,
        "std": monthly_std,
        "t_stat": monthly_mean / (monthly_std / (len(df) ** 0.5)),
        "annual_mean": monthly_mean * 12,
        "annual_vol": monthly_std * (12 ** 0.5),
        "skew": df.skew(),
        "kurtosis": df.kurtosis(),
    })
    return summary


def plot_cumulative(df: pd.DataFrame) -> None:
    """Plot cumulative returns (linear and log scale)."""
    # Cumulative Return (Linear)
    cumulative = (1 + df).cumprod() - 1
    plt.figure(figsize=(10, 6))
    for column in df.columns:
        plt.plot(cumulative.index, cumulative[column], label=column, linewidth=1.5)
    plt.title("Factor Cumulative Returns (2012-2024)")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Return")
    plt.legend(loc="upper left")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    CUMRET_FIG.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(CUMRET_FIG, dpi=200)
    plt.close()

    # Log Cumulative Wealth
    wealth = (1 + df).cumprod()
    plt.figure(figsize=(10, 6))
    for column in df.columns:
        plt.plot(wealth.index, wealth[column], label=column, linewidth=1.5)
    plt.yscale("log")
    plt.title("Factor Cumulative Wealth (Log Scale)")
    plt.xlabel("Date")
    plt.ylabel("Wealth (Start=1)")
    plt.legend(loc="upper left")
    plt.grid(True, alpha=0.3, which="both")
    plt.tight_layout()
    log_fig = CUMRET_FIG.with_name("factor_cumulative_log.png")
    plt.savefig(log_fig, dpi=200)
    plt.close()


def plot_correlation(df: pd.DataFrame) -> None:
    """Plot factor correlation matrix."""
    corr = df.corr()
    plt.figure(figsize=(6, 5))
    sns.heatmap(corr, annot=True, cmap="RdBu_r", center=0, fmt=".2f")
    plt.title("Factor Correlation Matrix")
    plt.tight_layout()
    plt.savefig(CORR_FIG, dpi=200)
    plt.close()


def main() -> None:
    """Main entry point for descriptive statistics."""
    df = load_factors(include_momentum=True)
    cols = [c for c in FACTOR_COLUMNS + ["MOM"] if c in df.columns]
    factors = df[cols]
    
    summary = compute_summary(factors)
    write_csv(summary.reset_index().rename(columns={"index": "factor"}), SUMMARY_OUTPUT, index=False)
    
    corr = factors.corr()
    write_csv(corr.reset_index().rename(columns={"index": "factor"}), CORR_OUTPUT, index=False)
    
    plot_cumulative(factors)
    plot_correlation(factors)
    LOGGER.info("Exported factor descriptive statistics and plots")


if __name__ == "__main__":
    main()
