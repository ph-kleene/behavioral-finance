from __future__ import annotations

import numpy as np
import pandas as pd

from factors.common import value_weighted_return
from paths import OUTPUT_TABLE_DIR, PROCESSED_DATA_DIR
from utils.io import write_csv, write_parquet
from utils.logging import get_logger

LOGGER = get_logger("factors.compute_momentum")

RETURNS_FILE = PROCESSED_DATA_DIR / "monthly_returns.parquet"
OUTPUT_PARQUET = PROCESSED_DATA_DIR / "momentum_factor.parquet"
OUTPUT_CSV = OUTPUT_TABLE_DIR / "momentum_factor.csv"

WINDOW_START = 2
WINDOW_END = 12
START_YEAR = 2012
START_MONTH = 7


def load_returns() -> pd.DataFrame:
    cols = ["stkcd", "trade_month", "year", "month", "float_mkt_cap", "return"]
    df = pd.read_parquet(RETURNS_FILE, columns=cols)
    df = df.sort_values(["stkcd", "trade_month"])
    return df


def compute_prior_returns(df: pd.DataFrame) -> pd.DataFrame:
    window = WINDOW_END - WINDOW_START + 1
    prior = (
        df.groupby("stkcd")["return"]
        .apply(lambda s: (1 + s).shift(WINDOW_START).rolling(window).apply(np.prod, raw=True) - 1)
        .reset_index(level=0, drop=True)
    )
    df["prior_return"] = prior
    return df


def construct_momentum(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["portfolio_year"] = np.where(df["month"] >= 7, df["year"], df["year"] - 1)
    df = df.dropna(subset=["prior_return", "float_mkt_cap", "return"])
    df = df[df["float_mkt_cap"] > 0]

    labels = []
    for year, group in df.groupby("portfolio_year"):
        median_size = group["float_mkt_cap"].quantile(0.5)
        prior_high = group["prior_return"].quantile(0.7)
        prior_low = group["prior_return"].quantile(0.3)
        size_label = np.where(group["float_mkt_cap"] <= median_size, "S", "B")
        momentum_label = np.where(group["prior_return"] >= prior_high, "H", np.where(group["prior_return"] <= prior_low, "L", "N"))
        labels.append(pd.DataFrame({
            "stkcd": group["stkcd"],
            "portfolio_year": year,
            "size_label": size_label,
            "momentum_label": momentum_label,
        }))
    label_df = pd.concat(labels, ignore_index=True)
    merged = df.merge(label_df, on=["stkcd", "portfolio_year"], how="inner")
    merged = merged[merged["momentum_label"].isin(["H", "L"])]

    mask = (merged["year"] > START_YEAR) | ((merged["year"] == START_YEAR) & (merged["month"] >= START_MONTH))
    merged = merged[mask]

    grouped = (
        merged.groupby(["trade_month", "size_label", "momentum_label"])
        .apply(value_weighted_return, include_groups=False)
        .reset_index(name="return")
    )

    pivot = grouped.pivot_table(index="trade_month", columns=["size_label", "momentum_label"], values="return")
    pivot.sort_index(inplace=True)

    smom = pivot["S", "H"] - pivot["S", "L"]
    bmom = pivot["B", "H"] - pivot["B", "L"]
    result = pd.DataFrame({
        "SMOM": smom,
        "BMOM": bmom,
    })
    result["MOM"] = (result["SMOM"] + result["BMOM"]) / 2
    return result.dropna()


def main() -> None:
    returns = load_returns()
    returns = compute_prior_returns(returns)
    momentum = construct_momentum(returns)
    write_parquet(momentum.reset_index(), OUTPUT_PARQUET, index=False)
    write_csv(momentum.reset_index(), OUTPUT_CSV, index=False)
    LOGGER.info("Computed momentum factor with %d months", len(momentum))


if __name__ == "__main__":
    main()
