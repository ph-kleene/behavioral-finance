"""
计算 Fama-French 五因子模型所需的个股财务指标。

计算内容：
- 账面市值比 (BM)
- 盈利能力 (OP)
- 投资风格 (INV)
- 市值 (Size)

数据对齐逻辑：
- t-1 年的财务数据匹配 t 年 7 月至 t+1 年 6 月的回报率。
- Size 分组基于 t 年 6 月的流通市值。
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from paths import PROCESSED_DATA_DIR
from utils.io import write_parquet
from utils.logging import get_logger

LOGGER = get_logger("factors.compute_indicators")

# 输入输出文件路径
FINANCIAL_PANEL = PROCESSED_DATA_DIR / "financial_panel.parquet"
MONTHLY_RETURNS = PROCESSED_DATA_DIR / "monthly_returns.parquet"
OUTPUT_FILE = PROCESSED_DATA_DIR / "factors_intermediate.parquet"

# 金融行业关键词 (用于剔除)
FINANCIAL_KEYWORDS: Sequence[str] = (
    "银行",
    "保险",
    "证券",
    "信托",
    "金融",
    "财险",
    "期货",
    "租赁",
)


def _drop_financials(df: pd.DataFrame) -> pd.DataFrame:
    """
    根据股票简称关键词剔除金融行业公司。
    """
    pattern = "|".join(FINANCIAL_KEYWORDS)
    mask = df["short_name"].astype(str).str.contains(pattern, na=False)
    dropped = int(mask.sum())
    if dropped:
        LOGGER.info("根据关键词剔除 %d 家金融行业公司", dropped)
    return df[~mask]


def load_financials(path: Path = FINANCIAL_PANEL) -> pd.DataFrame:
    """
    加载财务面板数据并计算原始指标。
    
    计算公式：
    - INV (投资) = (总资产_t - 总资产_{t-1}) / 总资产_{t-1}
    - OP (盈利) = 营业利润_t / 股东权益_t
    """
    df = pd.read_parquet(path)
    # 仅使用年报数据
    df = df[df["fiscal_month"] == 12]
    df = df.sort_values(["stkcd", "fiscal_year"])
    
    # 剔除金融股
    df = _drop_financials(df)
    
    # 组合年份 = 财报年份 + 1 (例如 2020年报用于 2021年组合)
    df["portfolio_year"] = df["fiscal_year"] + 1
    
    # 数据清洗：负值处理
    df["book_equity"] = df["total_equity"].clip(lower=0)
    df["operating_profit"] = df["operating_profit"].clip(lower=0)
    df["total_assets"] = df["total_assets"].clip(lower=0)
    
    # 计算滞后一期的总资产
    df["lag_total_assets"] = df.groupby("stkcd")["total_assets"].shift(1)
    
    # 计算指标
    df["inv"] = (df["total_assets"] - df["lag_total_assets"]) / df["lag_total_assets"]
    df["op"] = df["operating_profit"] / df["book_equity"].replace(0, np.nan)
    
    # 剔除缺失值
    df = df.dropna(subset=["lag_total_assets", "inv", "op"])
    return df


def load_market_caps(path: Path = MONTHLY_RETURNS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    加载市值数据。
    
    返回：
    1. december_mv: t-1 年 12 月市值 (用于计算 BM)。
    2. june_mv: t 年 6 月市值 (用于 Size 分组)。
    """
    returns = pd.read_parquet(path, columns=["stkcd", "trade_month", "year", "month", "float_mkt_cap"])
    
    # 12月市值
    december_mv = (
        returns[returns["month"] == 12]
        .rename(columns={"year": "fiscal_year", "float_mkt_cap": "december_me"})
        .loc[:, ["stkcd", "fiscal_year", "december_me"]]
    )
    
    # 6月市值
    june_mv = (
        returns[returns["month"] == 6]
        .rename(columns={"year": "portfolio_year", "float_mkt_cap": "size_mv"})
        .loc[:, ["stkcd", "portfolio_year", "size_mv"]]
    )
    return december_mv, june_mv


def assemble_indicators() -> pd.DataFrame:
    """
    合并财务数据与市值数据，生成最终的指标数据集。
    
    计算公式：
    - BM (账面市值比) = 股东权益_{t-1} / 市值_{t-1, 12月}
    """
    financials = load_financials()
    december_mv, june_mv = load_market_caps()

    # 合并市值数据
    df = financials.merge(december_mv, on=["stkcd", "fiscal_year"], how="left")
    df = df.merge(june_mv, on=["stkcd", "portfolio_year"], how="left")

    # 计算 BM
    df["bm"] = df["book_equity"] / df["december_me"]
    
    # 数据清洗
    df = df.dropna(subset=["bm", "size_mv", "inv", "op"])
    df = df[df["december_me"] > 0]
    df = df[df["size_mv"] > 0]

    # 筛选年份 (根据项目配置)
    df = df[df["portfolio_year"] >= 2011]
    
    columns = [
        "stkcd",
        "short_name",
        "portfolio_year",
        "book_equity",
        "bm",
        "op",
        "inv",
        "size_mv",
        "december_me",
    ]
    return df[columns]


def main() -> None:
    """主程序入口"""
    indicators = assemble_indicators()
    write_parquet(indicators, OUTPUT_FILE, index=False)
    LOGGER.info("保存 %d 条指标数据至 %s", len(indicators), OUTPUT_FILE)


if __name__ == "__main__":
    main()
