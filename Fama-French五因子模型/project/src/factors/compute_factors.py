from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from paths import OUTPUT_TABLE_DIR, PROCESSED_DATA_DIR
from utils.io import write_csv, write_parquet
from utils.logging import get_logger

LOGGER = get_logger("factors.compute_factors")

MARKET_FILE = PROCESSED_DATA_DIR / "market_returns.parquet"
RF_FILE = PROCESSED_DATA_DIR / "risk_free.parquet"
DEFAULT_PORTFOLIO_FILE = PROCESSED_DATA_DIR / "sorted_portfolios.parquet"
DEFAULT_PARQUET = PROCESSED_DATA_DIR / "factors_monthly.parquet"
DEFAULT_CSV = OUTPUT_TABLE_DIR / "factors_monthly.csv"

TWO_WAY_CONFIG = {
    "2x3": {
        "bm": {
            "small": ("SL", "SN", "SH"),
            "big": ("BL", "BN", "BH"),
            "high": ("SH", "BH"),
            "low": ("SL", "BL"),
        },
        "op": {
            "small": ("SW", "SN", "SR"),
            "big": ("BW", "BN", "BR"),
            "high": ("SR", "BR"),
            "low": ("SW", "BW"),
        },
        "inv": {
            "small": ("SA", "SN", "SC"),
            "big": ("BA", "BN", "BC"),
            "high": ("SC", "BC"),
            "low": ("SA", "BA"),
        },
    },
    "2x2": {
        "bm": {
            "small": ("SL", "SH"),
            "big": ("BL", "BH"),
            "high": ("SH", "BH"),
            "low": ("SL", "BL"),
        },
        "op": {
            "small": ("SW", "SR"),
            "big": ("BW", "BR"),
            "high": ("SR", "BR"),
            "low": ("SW", "BW"),
        },
        "inv": {
            "small": ("SA", "SC"),
            "big": ("BA", "BC"),
            "high": ("SC", "BC"),
            "low": ("SA", "BA"),
        },
    },
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute Fama-French factors for multiple schemes")
    parser.add_argument(
        "--scheme",
        choices=["2x3", "2x2", "2x2x2x2"],
        default="2x3",
        help="Portfolio construction scheme",
    )
    return parser.parse_args()


def _portfolio_file(scheme: str) -> Path:
    if scheme == "2x3":
        candidate = PROCESSED_DATA_DIR / "sorted_portfolios_2x3.parquet"
        return candidate if candidate.exists() else DEFAULT_PORTFOLIO_FILE
    return PROCESSED_DATA_DIR / f"sorted_portfolios_{scheme}.parquet"


def _output_paths(scheme: str) -> tuple[Path, Path | None, Path, Path | None]:
    parquet_path = PROCESSED_DATA_DIR / f"factors_monthly_{scheme}.parquet"
    csv_path = OUTPUT_TABLE_DIR / f"factors_monthly_{scheme}.csv"
    if scheme == "2x3":
        return parquet_path, DEFAULT_PARQUET, csv_path, DEFAULT_CSV
    return parquet_path, None, csv_path, None


def _pivot(portfolios: pd.DataFrame, portfolio_type: str) -> pd.DataFrame:
    subset = portfolios[portfolios["portfolio_type"] == portfolio_type]
    pivot = subset.pivot(index="trade_month", columns="portfolio", values="return")
    return pivot.sort_index()


def _mean_cols(pivot: pd.DataFrame, columns: tuple[str, ...]) -> pd.Series:
    available = [col for col in columns if col in pivot.columns]
    if not available:
        return pd.Series(index=pivot.index, dtype="float64")
    return pivot[available].mean(axis=1)


def _combine_two_way(portfolios: pd.DataFrame, scheme: str) -> pd.DataFrame:
    """
    计算基于双重排序 (2x3 或 2x2) 的因子收益率。
    
    计算逻辑 (以 2x3 为例):
    SMB = (SMB_BM + SMB_OP + SMB_INV) / 3
    HML = (SH + BH) / 2 - (SL + BL) / 2
    ...
    """
    config = TWO_WAY_CONFIG[scheme]
    bm = _pivot(portfolios, "bm")
    op = _pivot(portfolios, "op")
    inv = _pivot(portfolios, "inv")
    index = bm.index.intersection(op.index).intersection(inv.index)
    factors = pd.DataFrame(index=index)

    factors["SMB_BM"] = _mean_cols(bm, config["bm"]["small"]) - _mean_cols(bm, config["bm"]["big"])
    factors["HML"] = _mean_cols(bm, config["bm"]["high"]) - _mean_cols(bm, config["bm"]["low"])

    factors["SMB_OP"] = _mean_cols(op, config["op"]["small"]) - _mean_cols(op, config["op"]["big"])
    factors["RMW"] = _mean_cols(op, config["op"]["high"]) - _mean_cols(op, config["op"]["low"])

    factors["SMB_INV"] = _mean_cols(inv, config["inv"]["small"]) - _mean_cols(inv, config["inv"]["big"])
    factors["CMA"] = _mean_cols(inv, config["inv"]["high"]) - _mean_cols(inv, config["inv"]["low"])

    factors["SMB"] = (factors["SMB_BM"] + factors["SMB_OP"] + factors["SMB_INV"]) / 3
    return factors


def _group_mean(df: pd.DataFrame, column: str) -> pd.DataFrame:
    return df.groupby(["trade_month", column])["return"].mean().unstack(column)


def _group_mean_pair(df: pd.DataFrame, columns: list[str], expected_levels: list[list[str]]) -> pd.DataFrame:
    pivot = df.groupby(["trade_month", *columns])["return"].mean().unstack(columns)
    if not isinstance(pivot.columns, pd.MultiIndex):
        return pivot
    # ensure expected level order
    desired = pd.MultiIndex.from_product(expected_levels, names=columns)
    return pivot.reindex(columns=desired)


def _combine_four_way(portfolios: pd.DataFrame) -> pd.DataFrame:
    """
    计算基于四重排序 (2x2x2x2) 的因子收益率。
    
    计算逻辑:
    控制其他三个变量，计算目标变量的高低组差值。
    例如 HML: 在每个 Size-OP-INV 组合内计算 (High BM - Low BM)，然后取平均。
    """
    df = portfolios.copy()
    base_index = df["trade_month"].unique()
    factors = pd.DataFrame(index=sorted(base_index))

    size_means = _group_mean(df, "size_bucket")
    bm_means = _group_mean(df, "bm_bucket")
    op_means = _group_mean(df, "op_bucket")
    inv_means = _group_mean(df, "inv_bucket")

    cross_bm = _group_mean_pair(df, ["size_bucket", "bm_bucket"], [["S", "B"], ["L", "H"]])
    cross_op = _group_mean_pair(df, ["size_bucket", "op_bucket"], [["S", "B"], ["W", "R"]])
    cross_inv = _group_mean_pair(df, ["size_bucket", "inv_bucket"], [["S", "B"], ["A", "C"]])

    def _col(df_means: pd.DataFrame, col: str) -> pd.Series:
        if col not in df_means.columns:
            return pd.Series(index=factors.index, dtype="float64")
        return df_means[col].reindex(index=factors.index)

    factors["HML"] = _col(bm_means, "H") - _col(bm_means, "L")
    factors["RMW"] = _col(op_means, "R") - _col(op_means, "W")
    factors["CMA"] = _col(inv_means, "C") - _col(inv_means, "A")

    def _smb_component(cross: pd.DataFrame) -> pd.Series:
        small = cross.loc[:, ("S", slice(None))].mean(axis=1)
        big = cross.loc[:, ("B", slice(None))].mean(axis=1)
        return small.reindex(index=factors.index) - big.reindex(index=factors.index)

    factors["SMB_BM"] = _smb_component(cross_bm)
    factors["SMB_OP"] = _smb_component(cross_op)
    factors["SMB_INV"] = _smb_component(cross_inv)
    factors["SMB"] = (factors["SMB_BM"] + factors["SMB_OP"] + factors["SMB_INV"]) / 3

    return factors.sort_index()


def compute_factors(scheme: str) -> pd.DataFrame:
    portfolios = pd.read_parquet(_portfolio_file(scheme))
    if scheme in TWO_WAY_CONFIG:
        factor_df = _combine_two_way(portfolios, scheme)
    else:
        factor_df = _combine_four_way(portfolios)

    market = pd.read_parquet(MARKET_FILE).rename(columns={"market_return": "Rm"})
    rf = pd.read_parquet(RF_FILE)

    merged = factor_df.merge(market, left_index=True, right_on="trade_month", how="left")
    merged = merged.merge(rf, on="trade_month", how="left")
    merged.rename(columns={"risk_free": "Rf"}, inplace=True)
    merged["MKT"] = merged["Rm"] - merged["Rf"]
    merged = _add_cmao(merged)
    columns_order = [
        "MKT",
        "SMB",
        "HML",
        "RMW",
        "CMA",
        "CMAO",
        "SMB_BM",
        "SMB_OP",
        "SMB_INV",
        "Rm",
        "Rf",
    ]
    merged = merged.set_index("trade_month")[columns_order].dropna()
    merged = merged[merged.index >= "2012-07-31"]
    return merged


def _add_cmao(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算正交化的 CMA (CMAO)。
    
    逻辑：
    CMAO 是 CMA 对 MKT, SMB, HML, RMW 回归的残差。
    用于剔除 CMA 中已被其他因子解释的部分。
    """
    required = ["MKT", "SMB", "HML", "RMW", "CMA"]
    if not all(col in df.columns for col in required):
        df["CMAO"] = np.nan
        return df
    subset = df.dropna(subset=required)
    df["CMAO"] = np.nan
    if subset.empty:
        return df
    X = subset[["MKT", "SMB", "HML", "RMW"]].to_numpy(dtype=float)
    y = subset["CMA"].to_numpy(dtype=float)
    X_aug = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(X_aug, y, rcond=None)
    residuals = y - X_aug @ beta
    df.loc[subset.index, "CMAO"] = residuals
    return df


def main() -> None:
    args = _parse_args()
    factors = compute_factors(args.scheme)
    parquet_path, legacy_parquet, csv_path, legacy_csv = _output_paths(args.scheme)
    write_parquet(factors.reset_index(), parquet_path, index=False)
    write_csv(factors.reset_index(), csv_path, index=False)
    if legacy_parquet is not None:
        write_parquet(factors.reset_index(), legacy_parquet, index=False)
    if legacy_csv is not None:
        write_csv(factors.reset_index(), legacy_csv, index=False)
    LOGGER.info(
        "Saved %d monthly factors for %s scheme",
        len(factors),
        args.scheme,
    )


if __name__ == "__main__":
    main()
