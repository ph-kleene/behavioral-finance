"""
因子与投资组合计算的通用工具函数。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from paths import PROCESSED_DATA_DIR

RETURNS_FILE = PROCESSED_DATA_DIR / "monthly_returns.parquet"
START_YEAR = 2012
START_MONTH = 7

# 双重排序方案配置
TWO_WAY_SCHEMES: dict[str, dict[str, tuple[str, ...]]] = {
    "2x3": {
        "bm": ("SL", "SN", "SH", "BL", "BN", "BH"),
        "op": ("SW", "SN", "SR", "BW", "BN", "BR"),
        "inv": ("SA", "SN", "SC", "BA", "BN", "BC"),
    },
    "2x2": {
        "bm": ("SL", "SH", "BL", "BH"),
        "op": ("SW", "SR", "BW", "BR"),
        "inv": ("SA", "SC", "BA", "BC"),
    },
}

def prepare_returns_with_groups(
    groups: pd.DataFrame | Path,
    returns_file: Path = RETURNS_FILE,
    start_year: int = START_YEAR,
    start_month: int = START_MONTH,
) -> pd.DataFrame:
    """
    准备收益率数据并合并分组信息。
    
    参数:
        groups: 分组数据 DataFrame 或 parquet 文件路径。
                必须包含 ["stkcd", "portfolio_year"] 列。
        returns_file: 月度收益率文件路径。
        start_year: 起始年份。
        start_month: 起始月份。
        
    返回:
        合并后的 DataFrame，包含收益率和分组信息。
    """
    # 加载收益率
    returns = pd.read_parquet(
        returns_file,
        columns=["stkcd", "trade_month", "year", "month", "float_mkt_cap", "return"],
    )
    
    # 加载分组信息
    if isinstance(groups, Path):
        groups_df = pd.read_parquet(groups)
    else:
        groups_df = groups
        
    # 每年7月调整组合，7月之前使用上一年的分组
    # 例如: 2013年5月 (month=5 < 7) -> 使用 2012 年的分组
    #       2013年8月 (month=8 >= 7) -> 使用 2013 年的分组
    returns["portfolio_year"] = np.where(returns["month"] >= 7, returns["year"], returns["year"] - 1)
    
    # 合并分组信息
    # inner join 确保只保留有分组信息的股票
    merged = returns.merge(groups_df, on=["stkcd", "portfolio_year"], how="inner")
    
    # 筛选时间范围
    mask = (merged["year"] > start_year) | ((merged["year"] == start_year) & (merged["month"] >= start_month))
    merged = merged[mask]
    
    # 剔除无效数据
    merged = merged.dropna(subset=["return", "float_mkt_cap"])
    merged = merged[merged["float_mkt_cap"] > 0]
    
    return merged


def value_weighted_return(group: pd.DataFrame, return_col: str = "return", weight_col: str = "float_mkt_cap") -> float:
    """
    计算市值加权平均收益率。
    
    参数:
        group: 包含收益率和市值的 DataFrame。
        return_col: 收益率列名。
        weight_col: 权重(市值)列名。
    """
    weights = group[weight_col]
    if weights.sum() == 0:
        return np.nan
    return np.average(group[return_col], weights=weights)
