"""
项目路径配置模块

定义项目根目录、数据目录、输出目录以及关键常量的路径。
"""
from __future__ import annotations

from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 数据目录结构
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"          # 原始数据
PROCESSED_DATA_DIR = DATA_DIR / "processed"  # 处理后数据

# 输出目录结构
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_TABLE_DIR = OUTPUT_DIR / "tables"     # 结果表格
OUTPUT_FIGURE_DIR = OUTPUT_DIR / "figures"   # 结果图表

# 市场类型常量 (CSMAR定义)
# 1, 4, 16, 32, 64 通常代表A股市场不同板块
ALLOWED_A_MARKET_TYPES = {1, 4, 16, 32, 64}
MARKET_WIDE_CODE = 69       # 全市场综合指数代码
RISK_FREE_CODE = "NRI01"    # 无风险利率代码 (如一年期定存或国债)

# 因子构建时间范围
FACTOR_START_YEAR = 2010
FACTOR_END_YEAR = 2024

# 自动创建必要的输出目录
for _dir in (PROCESSED_DATA_DIR, OUTPUT_TABLE_DIR, OUTPUT_FIGURE_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
