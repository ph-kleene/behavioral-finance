from __future__ import annotations

import numpy as np
import pandas as pd

from factors.common import prepare_returns_with_groups, value_weighted_return
from paths import OUTPUT_TABLE_DIR, PROCESSED_DATA_DIR
from utils.io import write_csv, write_parquet
from utils.logging import get_logger

LOGGER = get_logger("tests_assets.build_25portfolios")

INDICATOR_FILE = PROCESSED_DATA_DIR / "factors_intermediate.parquet"
OUTPUT_PARQUET = PROCESSED_DATA_DIR / "test_portfolios_25.parquet"
OUTPUT_CSV = OUTPUT_TABLE_DIR / "test_portfolios_25.csv"


def _quintile_transform(series: pd.Series) -> pd.Series:
    try:
        return pd.qcut(series, q=5, labels=[1, 2, 3, 4, 5], duplicates="drop").astype(float)
    except ValueError:
        return pd.Series(np.nan, index=series.index)


def build_sort_labels() -> pd.DataFrame:
    indicators = pd.read_parquet(INDICATOR_FILE)
    indicators["size_bin"] = (
        indicators.groupby("portfolio_year")
        ["size_mv"]
        .transform(_quintile_transform)
        .astype(float)
    )
    indicators["bm_bin"] = (
        indicators.groupby("portfolio_year")
        ["bm"]
        .transform(_quintile_transform)
        .astype(float)
    )
    indicators = indicators.dropna(subset=["size_bin", "bm_bin"])
    indicators["size_bin"] = indicators["size_bin"].astype(int)
    indicators["bm_bin"] = indicators["bm_bin"].astype(int)
    return indicators[["stkcd", "portfolio_year", "size_bin", "bm_bin"]]


def build_test_portfolios() -> pd.DataFrame:
    labels = build_sort_labels()
    # 使用通用函数准备数据
    merged = prepare_returns_with_groups(labels)
    
    merged["portfolio"] = merged["size_bin"].astype(int).astype(str) + merged["bm_bin"].astype(int).astype(str)
    
    grouped = (
        merged.groupby(["trade_month", "portfolio"])
        .apply(value_weighted_return, include_groups=False)
        .reset_index(name="return")
    )
    wide = grouped.pivot(index="trade_month", columns="portfolio", values="return")
    wide = wide.sort_index()
    wide = wide.add_prefix("p")
    return wide


def main() -> None:
    portfolios = build_test_portfolios()
    write_parquet(portfolios.reset_index(), OUTPUT_PARQUET, index=False)
    write_csv(portfolios.reset_index(), OUTPUT_CSV, index=False)
    LOGGER.info("Saved 25 testing portfolios with %d monthly observations", len(portfolios))


if __name__ == "__main__":
    main()
