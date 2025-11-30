"""
股票与市场回报率清洗模块

功能：
1. 读取 CSMAR 个股月度回报率文件。
2. 筛选 A 股市场股票。
3. 剔除 ST 股票和上市不满 12 个月的股票。
4. 读取市场综合回报率和无风险利率。
5. 生成标准化的月度回报率数据文件。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from paths import (
    ALLOWED_A_MARKET_TYPES,
    MARKET_WIDE_CODE,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    RISK_FREE_CODE,
)
from utils.io import ensure_parent, write_parquet
from utils.logging import get_logger

LOGGER = get_logger("data_prep.clean_returns")

# 输入输出文件路径
RETURNS_FILE = RAW_DATA_DIR / "TRD_Mnth.csv"
MARKET_FILE = RAW_DATA_DIR / "TRD_Cnmont.csv"
RF_FILE = RAW_DATA_DIR / "TRD_Nrrate.csv"
FINANCIAL_PANEL = PROCESSED_DATA_DIR / "financial_panel.parquet"

RETURNS_OUTPUT = PROCESSED_DATA_DIR / "monthly_returns.parquet"
MARKET_OUTPUT = PROCESSED_DATA_DIR / "market_returns.parquet"
RF_OUTPUT = PROCESSED_DATA_DIR / "risk_free.parquet"


def _load_financial_short_names() -> set[str]:
    """
    加载股票简称，用于识别 ST 股票。
    依赖于 financial_panel.parquet 文件。
    """
    if not FINANCIAL_PANEL.exists():
        return set()
    df = pd.read_parquet(FINANCIAL_PANEL, columns=["stkcd", "short_name"])
    df["short_name"] = df["short_name"].astype(str)
    # 识别包含 "ST" 的股票
    st_mask = df["short_name"].str.upper().str.contains("ST", na=False)
    return set(df.loc[st_mask, "stkcd"].unique())


def load_monthly_returns(path: Path = RETURNS_FILE) -> pd.DataFrame:
    """
    加载并清洗个股月度回报率数据。
    
    筛选规则：
    1. 仅保留 A 股 (Markettype 在允许列表中)。
    2. 剔除上市不满 12 个月的观测值。
    3. 剔除 ST 股票。
    4. 剔除回报率或市值缺失的记录。
    """
    LOGGER.info("正在加载个股月度回报率: %s", path)
    df = pd.read_csv(
        path,
        dtype={"Stkcd": str, "Trdmnt": str, "Markettype": int},
        usecols=["Stkcd", "Trdmnt", "Msmvosd", "Mretwd", "Markettype"],
    )
    
    # 筛选 A 股
    df = df[df["Markettype"].isin(ALLOWED_A_MARKET_TYPES)]
    
    # 重命名列
    df.rename(
        columns={
            "Stkcd": "stkcd",
            "Trdmnt": "trade_month",
            "Msmvosd": "float_mkt_cap_thousand",
            "Mretwd": "return",
            "Markettype": "market_type",
        },
        inplace=True,
    )
    
    # 处理日期和数值
    df["trade_month"] = pd.to_datetime(df["trade_month"], format="%Y-%m") + pd.offsets.MonthEnd(0)
    df["return"] = pd.to_numeric(df["return"], errors="coerce")
    # 市值单位转换：千元 -> 元
    df["float_mkt_cap"] = pd.to_numeric(df["float_mkt_cap_thousand"], errors="coerce") * 1_000
    df.drop(columns=["float_mkt_cap_thousand"], inplace=True)
    
    # 剔除缺失值和无效市值
    df = df.dropna(subset=["return", "float_mkt_cap"])
    df = df[df["float_mkt_cap"] > 0]

    # 剔除上市不满 12 个月的记录
    df = df.sort_values(["stkcd", "trade_month"])
    first_month = df.groupby("stkcd")["trade_month"].transform("min")
    trade_period = df["trade_month"].dt.to_period("M").astype(int)
    first_period = first_month.dt.to_period("M").astype(int)
    months_since_listing = trade_period - first_period
    df = df[months_since_listing >= 12]

    # 剔除 ST 股票
    st_blacklist = _load_financial_short_names()
    if st_blacklist:
        df = df[~df["stkcd"].isin(st_blacklist)]

    df["year"] = df["trade_month"].dt.year
    df["month"] = df["trade_month"].dt.month
    return df


def load_market_returns(path: Path = MARKET_FILE) -> pd.DataFrame:
    """
    加载市场综合回报率 (Rm)。
    仅保留全市场综合指数 (Markettype=69)。
    """
    LOGGER.info("正在加载市场综合回报率: %s", path)
    df = pd.read_csv(path, dtype={"Markettype": int, "Trdmnt": str})
    df = df[df["Markettype"] == MARKET_WIDE_CODE]
    df.rename(columns={"Trdmnt": "trade_month", "Cmretwdos": "market_return"}, inplace=True)
    
    df["trade_month"] = pd.to_datetime(df["trade_month"], format="%Y-%m") + pd.offsets.MonthEnd(0)
    df["market_return"] = pd.to_numeric(df["market_return"], errors="coerce")
    df = df.dropna(subset=["market_return"])
    return df[["trade_month", "market_return"]]


def load_risk_free(path: Path = RF_FILE) -> pd.DataFrame:
    """
    加载无风险利率 (Rf) 并转换为月度小数形式。
    """
    LOGGER.info("正在加载无风险利率: %s", path)
    df = pd.read_csv(path, dtype={"Nrr1": str, "Clsdt": str, "Nrrmtdt": float})
    df = df[df["Nrr1"] == RISK_FREE_CODE]
    
    df["date"] = pd.to_datetime(df["Clsdt"], format="%Y-%m-%d")
    df["trade_month"] = df["date"].dt.to_period("M").dt.to_timestamp("M")
    
    rates = pd.to_numeric(df["Nrrmtdt"], errors="coerce")
    # 转换为小数 (原数据通常为百分比)
    df["rf"] = rates / 100.0
    
    # 按月取平均
    monthly = (
        df.groupby("trade_month")["rf"].mean().rename("risk_free").reset_index()
    )
    return monthly


def main() -> None:
    """主程序入口"""
    stock_returns = load_monthly_returns()
    ensure_parent(RETURNS_OUTPUT)
    write_parquet(stock_returns, RETURNS_OUTPUT, index=False)
    LOGGER.info("保存个股月度回报率 (%d 行) 至 %s", len(stock_returns), RETURNS_OUTPUT)

    market_returns = load_market_returns()
    write_parquet(market_returns, MARKET_OUTPUT, index=False)
    LOGGER.info("保存市场回报率 (%d 行) 至 %s", len(market_returns), MARKET_OUTPUT)

    risk_free = load_risk_free()
    write_parquet(risk_free, RF_OUTPUT, index=False)
    LOGGER.info("保存无风险利率 (%d 行) 至 %s", len(risk_free), RF_OUTPUT)


if __name__ == "__main__":
    main()
