"""
财务数据清洗模块

功能：
1. 读取 CSMAR 原始资产负债表和利润表文件。
2. 筛选合并报表（Type A）。
3. 提取关键财务变量（总资产、总负债、股东权益、营业利润）。
4. 合并生成年度/半年度财务面板数据。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from paths import PROCESSED_DATA_DIR, RAW_DATA_DIR
from utils.io import ensure_parent, write_parquet
from utils.logging import get_logger

LOGGER = get_logger("data_prep.clean_financials")

# 输入输出文件路径
BALANCE_FILE = RAW_DATA_DIR / "FS_Combas.csv"
INCOME_FILE = RAW_DATA_DIR / "FS_Comins.csv"
OUTPUT_FILE = PROCESSED_DATA_DIR / "financial_panel.parquet"

# 字段映射配置
BALANCE_COLS = {
    "Stkcd": "stkcd",
    "ShortName": "short_name",
    "Accper": "report_date",
    "Typrep": "report_type",
    "A001000000": "total_assets",      # 总资产
    "A002000000": "total_liabilities", # 总负债
    "A003000000": "total_equity",      # 股东权益合计
}

INCOME_COLS = {
    "Stkcd": "stkcd",
    "Accper": "report_date",
    "Typrep": "report_type",
    "B001300000": "operating_profit",  # 营业利润
}


def _load_and_filter_report(
    path: Path,
    col_map: dict[str, str],
    numeric_cols: list[str],
) -> pd.DataFrame:
    """
    通用报表加载与清洗函数。
    
    处理逻辑：
    1. 读取指定列。
    2. 重命名列。
    3. 筛选合并报表 (Typrep='A')。
    4. 处理日期，提取财年和月份。
    5. 仅保留 6月 和 12月 的定期报告。
    6. 转换数值列类型。
    7. 去重（保留最新记录）。
    """
    LOGGER.info("正在加载报表数据: %s", path)
    
    # 读取数据
    df = pd.read_csv(
        path,
        dtype={"Stkcd": str, "Typrep": str},
        parse_dates=["Accper"],
        usecols=list(col_map.keys()),
    )
    df = df.rename(columns=col_map)
    
    # 筛选合并报表
    if "report_type" in df.columns:
        df = df[df["report_type"] == "A"]
    
    # 处理日期
    df["report_date"] = pd.to_datetime(df["report_date"], utc=False)
    df["fiscal_year"] = df["report_date"].dt.year
    df["fiscal_month"] = df["report_date"].dt.month
    
    # 仅保留半年报和年报
    df = df[df["fiscal_month"].isin({6, 12})]
    
    # 转换数值类型
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    
    # 去重
    df = df.sort_values(["stkcd", "report_date"])
    df = df.drop_duplicates(subset=["stkcd", "report_date"], keep="last")
    return df


def load_balance_sheet(path: Path = BALANCE_FILE) -> pd.DataFrame:
    """加载并清洗资产负债表数据"""
    return _load_and_filter_report(
        path,
        BALANCE_COLS,
        ["total_assets", "total_liabilities", "total_equity"],
    )


def load_income_statement(path: Path = INCOME_FILE) -> pd.DataFrame:
    """加载并清洗利润表数据"""
    return _load_and_filter_report(
        path,
        INCOME_COLS,
        ["operating_profit"],
    )


def build_financial_panel() -> pd.DataFrame:
    """
    构建财务面板数据。
    
    将资产负债表和利润表按股票代码和报告日期合并。
    """
    balance = load_balance_sheet()
    income = load_income_statement()
    LOGGER.info("合并资产负债表 (%d 行) 与 利润表 (%d 行)", len(balance), len(income))
    
    df = balance.merge(
        income[["stkcd", "report_date", "operating_profit"]],
        on=["stkcd", "report_date"],
        how="left",
    )
    
    # 填充缺失的营业利润为0 (假设缺失即为无)
    df["operating_profit"] = df["operating_profit"].fillna(0.0)
    
    # 标记半年报/年报
    df["semiannual_label"] = df["fiscal_month"].map({6: "H1", 12: "H2"})
    df = df.sort_values(["stkcd", "report_date"])
    return df


def main() -> None:
    """主程序入口"""
    panel = build_financial_panel()
    LOGGER.info("保存清洗后的财务面板数据 (%d 行) 至 %s", len(panel), OUTPUT_FILE)
    ensure_parent(OUTPUT_FILE)
    write_parquet(panel, OUTPUT_FILE, index=False)


if __name__ == "__main__":
    main()
