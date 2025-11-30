"""
投资组合计算模块

功能：
根据股票的分组 (Size, BM, OP, INV) 和月度收益率，计算各投资组合的加权平均收益率。
支持 2x3, 2x2, 2x2x2x2 等多种分组方案。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from factors.common import prepare_returns_with_groups, value_weighted_return, TWO_WAY_SCHEMES
from paths import PROCESSED_DATA_DIR
from utils.io import write_parquet
from utils.logging import get_logger

LOGGER = get_logger("factors.compute_portfolios")

DEFAULT_GROUP_FILE = PROCESSED_DATA_DIR / "factor_groups.parquet"
DEFAULT_OUTPUT_FILE = PROCESSED_DATA_DIR / "sorted_portfolios.parquet"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="计算不同分组方案下的排序投资组合")
    parser.add_argument(
        "--scheme",
        choices=["2x3", "2x2", "2x2x2x2"],
        default="2x3",
        help="使用的分组方案",
    )
    return parser.parse_args()


def _group_file(scheme: str) -> Path:
    """获取分组文件路径"""
    if scheme == "2x3":
        candidate = PROCESSED_DATA_DIR / "factor_groups_2x3.parquet"
        return candidate if candidate.exists() else DEFAULT_GROUP_FILE
    return PROCESSED_DATA_DIR / f"factor_groups_{scheme}.parquet"


def _output_paths(scheme: str) -> tuple[Path, Path | None]:
    """获取输出文件路径"""
    scheme_path = PROCESSED_DATA_DIR / f"sorted_portfolios_{scheme}.parquet"
    if scheme == "2x3":
        return scheme_path, DEFAULT_OUTPUT_FILE
    return scheme_path, None


def _build_two_way_portfolios(
    df: pd.DataFrame,
    bucket_col: str,
    valid_labels: tuple[str, ...],
    portfolio_type: str,
) -> pd.DataFrame:
    """
    构建 2x3 或 2x2 投资组合 (Size x Style)。
    """
    subset = df.dropna(subset=[bucket_col])
    subset = subset.assign(portfolio=subset["size_bucket"] + subset[bucket_col])
    subset = subset[subset["portfolio"].isin(valid_labels)]
    
    aggregated = (
        subset.groupby(["trade_month", "portfolio"])
        .apply(value_weighted_return, include_groups=False)
        .reset_index(name="return")
    )
    aggregated["portfolio_type"] = portfolio_type
    return aggregated


def _build_four_way_portfolios(df: pd.DataFrame) -> pd.DataFrame:
    """
    构建 2x2x2x2 投资组合 (Size x BM x OP x INV)。
    """
    subset = df.dropna(subset=["size_bucket", "bm_bucket", "op_bucket", "inv_bucket"])
    aggregated = (
        subset.groupby(["trade_month", "size_bucket", "bm_bucket", "op_bucket", "inv_bucket"])
        .apply(value_weighted_return, include_groups=False)
        .reset_index(name="return")
    )
    aggregated["portfolio"] = (
        aggregated["size_bucket"].astype(str)
        + aggregated["bm_bucket"].astype(str)
        + aggregated["op_bucket"].astype(str)
        + aggregated["inv_bucket"].astype(str)
    )
    aggregated["portfolio_type"] = "quad"
    return aggregated


def compute_sorted_portfolios(scheme: str) -> pd.DataFrame:
    """计算所有排序投资组合的收益率"""
    group_file = _group_file(scheme)
    # 使用通用函数准备数据
    returns = prepare_returns_with_groups(group_file)
    
    if scheme in TWO_WAY_SCHEMES:
        configs = TWO_WAY_SCHEMES[scheme]
        bm = _build_two_way_portfolios(returns, "bm_bucket", configs["bm"], "bm")
        op = _build_two_way_portfolios(returns, "op_bucket", configs["op"], "op")
        inv = _build_two_way_portfolios(returns, "inv_bucket", configs["inv"], "inv")
        combined = pd.concat([bm, op, inv], ignore_index=True)
    else:
        combined = _build_four_way_portfolios(returns)
        
    combined = combined.dropna(subset=["return"])
    return combined


def main() -> None:
    """主程序入口"""
    args = _parse_args()
    portfolios = compute_sorted_portfolios(args.scheme)
    
    output_path, legacy_path = _output_paths(args.scheme)
    write_parquet(portfolios, output_path, index=False)
    if legacy_path is not None:
        write_parquet(portfolios, legacy_path, index=False)
        
    LOGGER.info(
        "已保存 %d 条投资组合月度数据 (方案: %s)",
        len(portfolios),
        args.scheme,
    )


if __name__ == "__main__":
    main()
