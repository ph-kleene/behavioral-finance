"""
因子分组模块

功能：
根据计算好的指标 (Size, BM, OP, INV) 对股票进行分组。
支持多种分组方案：
- 2x3 (标准 Fama-French): Size (2) x Style (3)
- 2x2: Size (2) x Style (2)
- 2x2x2x2: 四个指标同时独立排序
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from paths import PROCESSED_DATA_DIR
from utils.io import write_parquet
from utils.logging import get_logger

LOGGER = get_logger("factors.assign_groups")

# 输入输出文件路径
INDICATOR_FILE = PROCESSED_DATA_DIR / "factors_intermediate.parquet"
DEFAULT_OUTPUT = PROCESSED_DATA_DIR / "factor_groups.parquet"

# 分组方案配置
SCHEMES = {
    "2x3": {
        "size": {"quantile": 0.5, "labels": ("S", "B")},
        "styles": {
            "bm": {"type": "ternary", "quantiles": (0.3, 0.7), "labels": ("L", "N", "H")},
            "op": {"type": "ternary", "quantiles": (0.3, 0.7), "labels": ("W", "N", "R")},
            "inv": {"type": "ternary", "quantiles": (0.3, 0.7), "labels": ("C", "N", "A")},
        },
    },
    "2x2": {
        "size": {"quantile": 0.5, "labels": ("S", "B")},
        "styles": {
            "bm": {"type": "binary", "quantile": 0.5, "labels": ("L", "H")},
            "op": {"type": "binary", "quantile": 0.5, "labels": ("W", "R")},
            "inv": {"type": "binary", "quantile": 0.5, "labels": ("C", "A")},
        },
    },
    "2x2x2x2": {
        "size": {"quantile": 0.5, "labels": ("S", "B")},
        "styles": {
            "bm": {"type": "binary", "quantile": 0.5, "labels": ("L", "H")},
            "op": {"type": "binary", "quantile": 0.5, "labels": ("W", "R")},
            "inv": {"type": "binary", "quantile": 0.5, "labels": ("C", "A")},
        },
    },
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assign factor grouping buckets")
    parser.add_argument(
        "--scheme",
        choices=SCHEMES.keys(),
        default="2x3",
        help="Grouping scheme to apply",
    )
    return parser.parse_args()


def _assign_size_buckets(df: pd.DataFrame, quantile: float) -> pd.Series:
    """
    分配市值 (Size) 组别。
    
    逻辑：
    每年独立计算分位数断点。
    """
    medians = df.groupby("portfolio_year")["size_mv"].transform(lambda s: s.quantile(quantile))
    return np.where(df["size_mv"] <= medians, "S", "B")


def _assign_style_buckets(
    df: pd.DataFrame,
    column: str,
    config: dict,
) -> pd.Series:
    """
    分配风格因子 (BM, OP, INV) 组别。
    
    支持：
    - 三分位 (ternary): Low (30%), Neutral (40%), High (30%)
    - 二分位 (binary): Low (50%), High (50%)
    """
    if config["type"] == "ternary":
        q_low, q_high = config["quantiles"]
        low = df.groupby("portfolio_year")[column].transform(lambda s: s.quantile(q_low))
        high = df.groupby("portfolio_year")[column].transform(lambda s: s.quantile(q_high))
        
        bucket = pd.Series(config["labels"][1], index=df.index, dtype="object")
        bucket = bucket.mask(df[column].isna())
        bucket = bucket.mask(df[column] <= low, config["labels"][0])
        bucket = bucket.mask(df[column] >= high, config["labels"][2])
        return bucket

    # 二分位逻辑
    median = df.groupby("portfolio_year")[column].transform(lambda s: s.quantile(config["quantile"]))
    bucket = pd.Series(config["labels"][1], index=df.index, dtype="object")
    bucket = bucket.mask(df[column].isna())
    bucket = bucket.mask(df[column] <= median, config["labels"][0])
    bucket = bucket.mask(df[column] > median, config["labels"][1])
    return bucket


def assign_groups(df: pd.DataFrame, scheme: str = "2x3") -> pd.DataFrame:
    """
    执行全部分组逻辑。
    """
    if scheme not in SCHEMES:
        raise ValueError(f"Unsupported scheme: {scheme}")
    
    df = df.copy()
    scheme_cfg = SCHEMES[scheme]
    
    # 分配 Size 组
    df["size_bucket"] = _assign_size_buckets(df, scheme_cfg["size"]["quantile"])
    
    # 分配风格组
    for column, cfg in scheme_cfg["styles"].items():
        df[f"{column}_bucket"] = _assign_style_buckets(df, column, cfg)
    
    # 剔除无法分组的记录
    bucket_cols = ["size_bucket", "bm_bucket", "op_bucket", "inv_bucket"]
    df = df.dropna(subset=bucket_cols)
    return df


def _output_path(scheme: str) -> tuple[Path, Path | None]:
    """确定输出文件路径"""
    scheme_path = PROCESSED_DATA_DIR / f"factor_groups_{scheme}.parquet"
    if scheme == "2x3":
        return scheme_path, DEFAULT_OUTPUT
    return scheme_path, None


def main() -> None:
    """主程序入口"""
    args = _parse_args()
    indicators = pd.read_parquet(INDICATOR_FILE)
    
    groups = assign_groups(indicators, scheme=args.scheme)
    
    output_path, legacy_path = _output_path(args.scheme)
    write_parquet(groups, output_path, index=False)
    if legacy_path is not None:
        write_parquet(groups, legacy_path, index=False)
        
    LOGGER.info(
        "已完成分组 (%s 方案)，共 %d 条记录",
        args.scheme,
        len(groups),
    )
