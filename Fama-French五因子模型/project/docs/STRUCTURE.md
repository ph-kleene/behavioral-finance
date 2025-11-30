# 项目文件规约 (Project Structure & Conventions)

为了保证代码的可读性、可维护性和复现性，本项目遵循以下文件结构和命名规范。

## 1. 目录结构

```
project/
├── data/                   # 数据存放目录
│   ├── raw/                # 原始数据 (不应修改)
│   │   ├── TRD_Mnth.csv    # 月个股回报
│   │   ├── FS_Combas.csv   # 资产负债表
│   │   ├── FS_Comins.csv   # 利润表
│   │   └── ...
│   └── processed/          # 清洗后的中间数据
│       ├── clean_financials.pkl
│       ├── clean_returns.pkl
│       └── factors_monthly.csv # 最终因子序列
├── src/                    # 源代码目录
│   ├── config.py           # 配置文件 (路径、参数常量)
│   ├── utils.py            # 通用工具函数 (数据加载、日期处理)
│   ├── 01_data_cleaning.py # 数据清洗与指标计算
│   ├── 02_factor_construction.py # 因子构建 (2x3分组)
│   ├── 03_model_testing.py # 模型检验 (回归、GRS)
│   └── 04_visualization.py # 绘图脚本
├── output/                 # 输出结果
│   ├── figures/            # 图片 (png, pdf)
│   └── tables/             # 表格 (csv, excel, latex)
└── docs/                   # 文档与报告
    ├── report.docx         # 最终分析报告
    ├── PLAN.md             # 项目计划
    └── STRUCTURE.md        # 本文件
```

## 2. 命名规范

### 文件命名
*   **Python 脚本**：使用小写字母和下划线，按执行顺序编号。
    *   例：`01_data_cleaning.py`, `02_factor_construction.py`
*   **数据文件**：清晰描述内容，区分 raw 和 processed。
    *   例：`raw_balance_sheet.csv`, `factor_returns_2012_2024.csv`

### 变量命名 (Python)
*   **DataFrame 列名**：统一使用英文大写，与 CSMAR 原始代码或标准缩写保持一致。
    *   `STKCD`: 证券代码
    *   `TRDMNT`: 交易月份 (YYYY-MM)
    *   `MRETWD`: 考虑现金红利再投资的月个股回报率
    *   `SIZE`: 流通市值
    *   `BM`: 账面市值比
    *   `OP`: 营运利润率
    *   `INV`: 投资风格
*   **因子变量**：
    *   `SMB`, `HML`, `RMW`, `CMA`, `MKT_RF`, `RF`

## 3. 数据处理规范
*   **路径引用**：所有路径应在 `config.py` 中定义，避免在脚本中硬编码绝对路径。使用 `os.path.join` 或 `pathlib` 确保跨平台兼容性。
*   **中间保存**：耗时较长的数据处理步骤（如清洗后的财务数据）应保存为 `.pkl` (Pickle) 或 `.parquet` 格式，以便快速读取，避免重复计算。

## 4. 代码规范
*   **注释**：关键逻辑（特别是分组逻辑、时间对齐逻辑）必须添加注释。
*   **函数化**：避免写面条代码，将独立功能（如“计算加权收益率”）封装为函数。
*   **异常处理**：注意处理除以零、空值等情况。

## 5. 提交清单
最终提交时应包含：
1.  `src/` 下的所有代码。
2.  `output/` 下的关键图表。
3.  `docs/` 下的分析报告。
4.  `PLAN.md` 和 `STRUCTURE.md`。
