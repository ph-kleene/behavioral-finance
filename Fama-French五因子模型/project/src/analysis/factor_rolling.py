from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from paths import OUTPUT_FIGURE_DIR, OUTPUT_TABLE_DIR, PROCESSED_DATA_DIR
from utils.io import write_csv
from utils.logging import get_logger

LOGGER = get_logger("analysis.factor_rolling")

FACTORS_FILE = PROCESSED_DATA_DIR / "factors_monthly.parquet"
ROLLING_MEAN_CSV = OUTPUT_TABLE_DIR / "factor_rolling_mean.csv"
ROLLING_VOL_CSV = OUTPUT_TABLE_DIR / "factor_rolling_vol.csv"
FIG_PATH = OUTPUT_FIGURE_DIR / "factor_rolling_trends.png"

FACTOR_COLUMNS = ["MKT", "SMB", "HML", "RMW", "CMA"]
WINDOW = 36


def load_factors() -> pd.DataFrame:
    df = pd.read_parquet(FACTORS_FILE)
    df["trade_month"] = pd.to_datetime(df["trade_month"])
    return df.set_index("trade_month").sort_index()


def compute_rolling_stats(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rolling_mean = df[FACTOR_COLUMNS].rolling(WINDOW).mean() * 12
    rolling_vol = df[FACTOR_COLUMNS].rolling(WINDOW).std() * (12 ** 0.5)
    return rolling_mean, rolling_vol


def plot_trends(rolling_mean: pd.DataFrame, rolling_vol: pd.DataFrame) -> None:
    plt.figure(figsize=(10, 8))

    ax1 = plt.subplot(2, 1, 1)
    rolling_mean.plot(ax=ax1)
    ax1.set_title(f"{WINDOW}-month rolling annualized mean")
    ax1.set_ylabel("Annualized mean")

    ax2 = plt.subplot(2, 1, 2)
    rolling_vol.plot(ax=ax2)
    ax2.set_title(f"{WINDOW}-month rolling annualized volatility")
    ax2.set_ylabel("Annualized vol")

    plt.tight_layout()
    FIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(FIG_PATH, dpi=200)
    plt.close()


def main() -> None:
    factors = load_factors()
    rolling_mean, rolling_vol = compute_rolling_stats(factors)
    write_csv(rolling_mean.reset_index(), ROLLING_MEAN_CSV, index=False)
    write_csv(rolling_vol.reset_index(), ROLLING_VOL_CSV, index=False)
    plot_trends(rolling_mean, rolling_vol)
    LOGGER.info("Rolling factor trends saved to %s", FIG_PATH)


if __name__ == "__main__":
    main()
