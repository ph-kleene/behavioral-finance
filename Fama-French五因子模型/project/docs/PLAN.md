# Fama-French 五因子模型在中国 A 股市场的实证检验 —— 项目计划

## 0. 项目概览

- **研究对象**：中国 A 股市场普通股（CSMAR 数据库，沪深 A 股）
- **数据区间（原始数据）**：2010-01 ～ 2024-12（财务 + 月度回报 + 无风险利率）
- **模型检验区间**：2012-07 ～ 2024-12  
  因为投资因子 $INV_t$ 需要 $t-2$ 年的总资产数据，所以从 2012 年 7 月开始构建因子并进行回归。
- **方法框架**：严格参照 Fama-French (2015) 五因子模型的 2×3 组合构造思路，并结合中国 A 股文献做必要本土化（例如仅保留 A 股、剔除金融、ST、IPO 不足一年等）。

---

## 1. 研究目标与输出

### 1.1 研究目标

1. 构建符合 Fama-French (2015) 五因子方法论的 **中国 A 股五因子序列**：
    - 市场因子：$MKT = R_m - R_f$
    - 规模因子：$SMB$（Small Minus Big）
    - 价值因子：$HML$（High Minus Low）
    - 盈利因子：$RMW$（Robust Minus Weak）
    - 投资因子：$CMA$（Conservative Minus Aggressive）

2. 在 2012-07 ～ 2024-12 区间内，对上述因子进行：
    - 基本统计与相关性分析
    - 使用多资产（如 25 个测试组合）的 **截面资产定价回归**
    - 对部分因子（尤其 HML）的 **冗余性检验**
    - （有余力可选）GRS 检验截距项是否联合为 0

### 1.2 主要输出

1. 因子序列 CSV（建议路径：`project/output/tables/factors_monthly.csv`），格式示例：
    - `date, MKT, SMB, HML, RMW, CMA, Rf`
2. 组合收益序列 CSV（如 25 组合的月度超额收益），建议路径：
    - `project/output/tables/test_portfolios_25.csv`
3. 图表：
    - 因子累计收益曲线（多因子叠加）
    - 因子间相关系数热力图
    - 回归结果可视化（如 alpha 分布图）
4. Word 分析报告（课程要求）+ 简短 `README` 说明如何运行代码。

---

## 2. 数据与变量定义

### 2.1 数据来源与文件组织（基于当前目录结构）

- 原始数据目录：`project/data/raw/`
  - 资产负债表（合并报表）示例：`FS_Combas*.csv / txt`
  - 利润表示例：`FS_Comins*.csv / txt`
  - 个股月度回报：`TRD_Mnth*.csv / txt`
  - 综合市场月度收益：`TRD_Cnmont*.csv / txt`
  - 无风险利率（月度）：根据助教提供的数据结构确定字段，若在同一表中则合并提取。
- 处理后整洁数据目录：`project/data/processed/`  
  统一生成：
  - `financial_panel.parquet`：按公司-年度的财务面板数据
  - `monthly_returns.parquet`：按公司-月份的个股收益及市值数据
  - `factors_intermediate.parquet`：用于构建因子的中间数据（含 BM, OP, INV 分位组别等）

### 2.2 样本筛选规则

对 **股票层面** 的筛选（参照中文文献常用做法）：

1. **仅保留 A 股**：
    - CSMAR 中可用 `Markettype` 标识，保留：1, 4, 16, 32, 64 等代表 A 股市场的类型。
2. **剔除金融类公司**：
    - 利用行业代码（如 `Indcd` 或 `CSRC` 分类），剔除银行、保险、证券等金融业。
3. **剔除 ST、*ST 股票**：
    - 利用股票简称或 ST 标记字段，在构建分组和计算收益时均剔除这些股票。
4. **剔除上市不足 12 个月的股票**：
    - 对 t 年 6 月形成组合时，只保留在 t 年 6 月已经上市满 12 个月的股票。
5. **仅保留合并报表**：
    - `Typrep = 'A'`（合并报表）作为财务数据来源。
6. **关键变量缺失剔除**：
    - BM 所需：股东权益与市值
    - OP 所需：营业利润与股东权益
    - INV 所需：t-1 与 t-2 年的总资产
    - 缺少上述任一时，该年该股票不用于分组（可在下一年若数据齐全再纳入）。

### 2.3 关键财务变量计算（年度层面）

按照 Fama-French 的定义，并结合 CSMAR 字段进行本土化映射（此处在计划中给出公式层面，具体字段名在代码中注释清晰说明）：

设股票 i 在年度 t 的财务报告期为 t 年末（通常 12 月 31 日）：

1. **账面股权（Book Equity, BE）**：
    - 经典 FF 定义较复杂，中国实务中常用简化版：
    - $BE_{i,t} = 股东权益合计_{i,t}$（或归属于母公司的所有者权益）
    - 若未来查阅到更精细的 BE 构造（例如考虑优先股等），可在代码层面升级，但计划书中先采用课程说明。

2. **市值（流通市值或总市值）**：
    - 为保证与分组口径一致，使用 **t 年 6 月底的流通市值**：
    - $ME_{i,t}^{Jun} = Price_{i,t,Jun} \times Shares_{i,t,Jun}$  
      其中 `Price` 为 6 月末收盘价，`Shares` 为相应流通股数。

3. **Size 指标**（用于 Size 分组）：
    - $Size_t(i) = ME_{i,t}^{Jun}$

4. **BM 指标**（Book-to-Market）：
    - 使用 t-1 年末账面价值与 t-1 年末的市值：
    - $BM_t(i) = \dfrac{BE_{i,t-1}}{ME_{i,t-1}^{Dec}}$

5. **OP 指标**（Operating Profitability，盈利能力）：
    - Fama-French (2015) 美国数据中，OP 大致为：营业收入 − 销售成本 − 管理费用 − 利息支出，再除以（账面股权 + 少数股东权益）。
    - 在 CSMAR 上的简化版本（结合助教说明）：
    - $OP_t(i) = \dfrac{营业利润_{i,t-1}}{股东权益合计_{i,t-1}}$

6. **INV 指标**（Investment，投资风格）：
    - 按照课程与 Fama-French 定义，使用总资产增长率：
    - $INV_t(i) = \dfrac{TA_{i,t-1} - TA_{i,t-2}}{TA_{i,t-2}}$
    - 其中 $TA$ 为总资产。若 $TA_{i,t-2} \le 0$ 或缺失，则该股票在 t 期不参与 INV 分组。

### 2.4 时间对齐原则（关键）

1. **财务报表数据的可得性滞后**：
    - 假设年度 t-1 的财报在 t 年 4 月前后完全披露，Fama-French 的标准做法是在 **t 年 6 月** 使用 t-1 的财务指标进行分组，并从 t 年 7 月到 t+1 年 6 月使用相同的分组标签。
2. **本项目采用的对齐方式**：
    - 对于年度 t：
      - 使用 **t-1 年末** 的 BE、OP、TA 计算 $BM_t(i)$、$OP_t(i)$、$INV_t(i)$；
      - 使用 **t-2 年末** 的 TA 参与 INV。
    - 在 **t 年 6 月末** 计算市值 $ME_{i,t}^{Jun}$ 并据此进行 Size 分组。
    - 得到的分组标签（Size, BM, OP, INV）用于 **t 年 7 月 ～ t+1 年 6 月** 的月度股票组合收益计算。
3. **月度收益与无风险利率**：
    - 个股收益：使用 CSMAR 月个股回报（含现金红利再投资）的月度回报率 `Ri_{i,month}`。
    - 市场组合收益：使用 CSMAR 综合月市场回报 `Rm_{month}`（以流通市值加权的全市场组合）。
    - 无风险利率：使用 CSMAR 提供的一月期国债收益率或 SHIBOR 等作为替代，统一转为 **月度无风险利率** $Rf_{month}$。
    - 超额收益：$R_{i,month} - Rf_{month}$，$MKT_{month} = Rm_{month} - Rf_{month}$。

---

## 3. 因子构建方法（2×3 双排序，严格细化）

### 3.1 分组断点

在每个年份 t 的 6 月底，利用可用样本股票：

1. **Size 分组断点（中位数）**：
    - 用所有 **可交易的 A 股样本** 的 $ME_{i,t}^{Jun}$ 计算中位数。
    - 也可以借鉴 FF 的标准，只用“基准市场”（如沪深主板）计算断点，并将断点应用到全市场，但本项目基础版本先用全样本中位数。
    - 得到：
      - Small（S）：$ME_{i,t}^{Jun}$ 小于等于中位数；
      - Big（B）：$ME_{i,t}^{Jun}$ 大于中位数。

2. **BM、OP、INV 分位点（30%、70%）**：
    - 计算 $BM_t(i)$、$OP_t(i)$、$INV_t(i)$ 时，仅使用在对应财务数据非缺失且当年参与交易的股票。
    - 对每个指标分别求 30%、70% 分位数：
      - BM：Low (L) < P30; Neutral (N) 介于 P30～P70; High (H) ≥ P70
      - OP：Weak (W) < P30; Neutral (N) 介于 P30～P70; Robust (R) ≥ P70
      - INV：Aggressive (A) < P30（高投资：总资产增长快）或按 FF 标准：更高投资率为「A」，更低为「C」；  
         Conservative (C) ≥ P70（低投资率）；Neutral (N) 介于 P30～P70  
         注意：中国文献中对符号方向有时相反，计划中明确采用 **高投资率 = Aggressive，低投资率 = Conservative**，与 FF 相同。

### 3.2 三组 2×3 双重排序

对每年 t 用 **Size 与 BM/OP/INV** 进行三次独立的 2×3 排序，各得到 6 个市值加权组合：

1. **Size-BM（S/B × L/N/H）**：
    - SL：小市值 & 低 BM
    - SN：小市值 & 中 BM
    - SH：小市值 & 高 BM
    - BL：大市值 & 低 BM
    - BN：大市值 & 中 BM
    - BH：大市值 & 高 BM

2. **Size-OP（S/B × W/N/R）**：
    - SW：小市值 & 弱盈利
    - SN_OP：小市值 & 中盈利（为与 BM 中的 SN 区分，内部实现可命名为 `SN_OP`）
    - SR：小市值 & 强盈利
    - BW：大市值 & 弱盈利
    - BN_OP：大市值 & 中盈利（内部命名为 `BN_OP`）
    - BR：大市值 & 强盈利

3. **Size-INV（S/B × A/N/C）**：
    - SA：小市值 & 高投资（Aggressive）
    - SN_INV：小市值 & 中投资
    - SC：小市值 & 低投资（Conservative）
    - BA：大市值 & 高投资
    - BN_INV：大市值 & 中投资
    - BC：大市值 & 低投资

> 说明：在最终因子公式中，为避免混淆，计划中统一写作 SH/SL 等，代码中会以清晰命名标识对应组合。

### 3.3 组合收益的计算

在每个 **月度** $m$（落在 t 年 7 月 ～ t+1 年 6 月之间）：

1. 对每一个 2×3 组合（如 SL、SN、…、BA），收集在该月仍有交易数据的股票 i。
2. 用各股票的市值权重进行加权：
    - 一般用上月末市值作为权重基准，也可以用当月初市值。
    - $R_{P,m} = \dfrac{\sum_{i \in P} ME_{i,m-1} \times R_{i,m}}{\sum_{i \in P} ME_{i,m-1}}$
3. 所有组合的月度收益均为 **简单回报率**，与 CSMAR 文件中定义保持一致（通常包含现金分红再投资）。

### 3.4 五个因子收益率的构造公式

在每个 **月度 m**（对应某个 t 年度的分组）：

1. **规模因子 SMB（Small Minus Big）**

    - 先构造三个 SMB 部分因子：
      - $SMB_{BM,m} = \dfrac{1}{3}(R_{SL,m} + R_{SN,m} + R_{SH,m}) - \dfrac{1}{3}(R_{BL,m} + R_{BN,m} + R_{BH,m})$
      - $SMB_{OP,m} = \dfrac{1}{3}(R_{SW,m} + R_{SN\_OP,m} + R_{SR,m}) - \dfrac{1}{3}(R_{BW,m} + R_{BN\_OP,m} + R_{BR,m})$
      - $SMB_{INV,m} = \dfrac{1}{3}(R_{SA,m} + R_{SN\_INV,m} + R_{SC,m}) - \dfrac{1}{3}(R_{BA,m} + R_{BN\_INV,m} + R_{BC,m})$

    - 最终 SMB：
      - $SMB_m = \dfrac{1}{3}(SMB_{BM,m} + SMB_{OP,m} + SMB_{INV,m})$

2. **价值因子 HML（High Minus Low）**

    - 使用 Size-BM 组合中的 Value（高 BM）和 Growth（低 BM）组合：
      - $HML_m = \dfrac{1}{2}(R_{SH,m} + R_{BH,m}) - \dfrac{1}{2}(R_{SL,m} + R_{BL,m})$

3. **盈利因子 RMW（Robust Minus Weak）**

    - 使用 Size-OP 组合：
      - $RMW_m = \dfrac{1}{2}(R_{SR,m} + R_{BR,m}) - \dfrac{1}{2}(R_{SW,m} + R_{BW,m})$

4. **投资因子 CMA（Conservative Minus Aggressive）**

    - 使用 Size-INV 组合：
      - $CMA_m = \dfrac{1}{2}(R_{SC,m} + R_{BC,m}) - \dfrac{1}{2}(R_{SA,m} + R_{BA,m})$

5. **市场因子 MKT**

    - $MKT_m = R_{mkt,m} - R_{f,m}$  
      其中 $R_{mkt,m}$ 为中国 A 股市场的 **流通市值加权综合收益**。

> 以上公式完全对应 Ken French 官方网站 “Fama/French 5 Factors (2×3)” 的定义，只是将美国市场的 NYSE/AMEX/NASDAQ 替换为中国的 A 股。

---

## 4. 模型检验设计

### 4.1 描述性统计与相关性分析

1. 对因子序列（MKT, SMB, HML, RMW, CMA）在 2012-07 ～ 2024-12 的月度数据计算：
    - 均值、标准差、最小值、最大值、偏度、峰度
    - 年化收益和年化波动率：  
      - 年化收益 = 月度均值 × 12  
      - 年化波动率 = 月度标准差 × $\sqrt{12}$
2. 计算因子之间的皮尔逊相关系数，输出相关矩阵并可视化（热力图）。

### 4.2 测试资产的构造

建议构造 **25 个测试组合**（以便与文献对接）：

1. 使用 BM 与 Size 的 5×5 排序（或参考 Fama-French 数据库 “25 Portfolios Formed on Size and Book-to-Market (5×5)” 的思路）：
    - 对 Size 使用 20%, 40%, 60%, 80% 等分位点划分 5 组；
    - 对 BM 使用相同方式划分 5 组；
    - 形成 25 个市值加权组合，每月重平衡一次；
    - 得到每月该组合的收益 $R_{p,m}$ 和超额收益 $R_{p,m} - R_{f,m}$。
2. 或者简单采用课程提供的其他排序方式，只要测试资产足够多样、覆盖尺寸与价值横截面的异质性即可。

### 4.3 因子回归

对每个测试组合 p，在样本区间上估计：

$$
R_{p,m} - R_{f,m} = \alpha_p + b_p MKT_m + s_p SMB_m + h_p HML_m + r_p RMW_m + c_p CMA_m + \varepsilon_{p,m}
$$

1. 使用 OLS 回归，输出：
    - $\alpha_p$ 及其 t 统计量；
    - 各因子载荷 $b_p, s_p, h_p, r_p, c_p$ 及 t 统计量；
    - 回归的 $R^2$ 和调整后 $R^2$。
2. 汇总 25 个组合的回归结果，重点分析：
    - 绝大部分组合的 $\alpha_p$ 是否统计上接近 0；
    - 不同类型组合（小盘价值、高盈利、低投资等）在各因子上的暴露是否符合经济直觉。

#### 4.3.1 脚本实现与可选模型

- `analysis/regression_ff5.py` 现支持 `--model`（`capm|ff3|carhart|ff5|ff5_mom`）与 `--scheme`（`2x3|2x2|2x2x2x2`）参数。
- 当模型包含 MOM 因子时，脚本会自动合并 `data/processed/momentum_factor.parquet`。
- 回归结果依模型与分组方案保存为 `output/tables/regression_results_<model>_<scheme>.csv`，便于横向比较。

### 4.4 冗余因子检验（重点关注 HML）

根据 Fama-French (2015)，HML 在五因子框架中可能是冗余的。可以进行如下检验：

1. 以 HML 自身（或 2×3 Value minus Growth 组合）作为被解释变量，跑回归：
    $$
    HML_m = a + b \, MKT_m + s \, SMB_m + r \, RMW_m + c \, CMA_m + u_m
    $$
2. 若截距 $a$ 较小且不显著，同时 $R^2$ 很高，说明 HML 收益大部分被其他因子解释，可视为“近似冗余”。

也可以对 RMW、CMA 分别做类似检验，观察它们是否带来增量解释力。

### 4.5 （可选）GRS 检验

1. 使用 25 个测试组合，检验所有组合回归的截距项联合为 0。
2. 需要构造多元检验统计量（GRS 统计量），在计划中仅注明步骤，具体实现可以：
    - 若时间充裕，可按公式手写实现；
    - 若时间有限，可以注明“在报告中给出公式与理论说明”，代码可选做。

---

## 5. 编码与文件结构规划

### 5.1 代码目录建议

在 `project/src/` 下建议按功能拆分模块（Python 为例）：

- `data_prep/`
  - `load_csmar.py`：封装原始 CSV/TXT 的读取。
  - `clean_financials.py`：财务报表合并、变量提取、筛选 A 股/非金融/ST 等。
  - `clean_returns.py`：月个股收益、市场收益、无风险利率清洗与对齐。
  - 输出：`financial_panel.parquet`、`monthly_returns.parquet`。

- `factors/`
  - `compute_indicators.py`：基于年度财报计算 BM、OP、INV、Size。
  - `assign_groups.py`：按年度生成 Size/BM/OP/INV 的 2×3 分组标签。
  - `compute_portfolios.py`：计算 2×3 组合月度收益（SL, SN, …, BC）。
  - `compute_factors.py`：根据 2×3 组合收益计算 SMB_BM、SMB_OP、SMB_INV、SMB、HML、RMW、CMA、MKT。
  - 输出：`factors_monthly.csv`。

- `tests_assets/`
  - `build_25portfolios.py`：构造 Size-BM 5×5 组合并导出月度收益。
  
- `analysis/`
  - `descriptive_stats.py`：因子描述统计与相关性。
  - `regression_ff5.py`：多元线性回归、冗余检验。
  - `grs_test.py`（可选）：实现 GRS 检验。
  - 绘图脚本：`plot_factor_cumret.py`、`plot_corr_heatmap.py` 等。

- `main.py`（或 `run_all.py`）：
  - 串联以上模块，实现“一键跑完”的脚本。

### 5.2 运行顺序与依赖

建议提供 `run_all.sh` 或 `Makefile`，大致顺序：

1. `python -m data_prep.load_csmar`
2. `python -m data_prep.clean_financials`
3. `python -m data_prep.clean_returns`
4. `python -m factors.compute_indicators`
5. `python -m factors.assign_groups`
6. `python -m factors.compute_portfolios`
7. `python -m factors.compute_factors`
8. `python -m tests_assets.build_25portfolios`
9. `python -m analysis.descriptive_stats`
10. `python -m analysis.regression_ff5`
11. （可选）`python -m analysis.grs_test`

---

## 6. 时间计划与里程碑

### Step 1：数据清洗与指标计算

- 完成 CSMAR 原始数据读取脚本（可以先对一小部分年份测试）。
- 清洗财务报表与个股月度收益数据，构造：
  - `financial_panel.parquet`
  - `monthly_returns.parquet`
- 基于 2010-2014 年数据先试算 BM、OP、INV 与 Size，检查是否合理（如 OP 不应大规模为负，INV 的分布应集中在 -0.5 到 0.5 之间等）。

### Step 2：因子构建与验证

- 实现 2×3 排序与组合收益计算。
- 按公式计算 SMB_BM、SMB_OP、SMB_INV、SMB、HML、RMW、CMA、MKT。
- 生成完整因子序列 `factors_monthly.csv`，绘制简单的因子累计收益曲线，检查是否存在明显错误（如曲线极端剧烈、因子水平异常大等）。

### Step 3：模型回归与报告撰写

- 构建 25 个 Size-BM 5×5 组合，计算测试资产月度收益。
- 进行五因子回归，输出回归表格和简要可视化。
- 做 HML 冗余检验，若有时间再做 GRS 检验。
- 在 Word 报告中：
  - 清晰说明数据来源、样本筛选与因子构建方法；
  - 展示因子统计特征与回归结果；
  - 讨论中国 A 股市场中五因子模型的适用性与与原文结论的异同；
  - 列出参考文献（包括 Fama-French 原文、课程 reference 提供的中国市场研究等）。

---

## 7. 参考文献（计划中先列出核心文献）

- Fama, Eugene F., and Kenneth R. French, 2015, “A Five-Factor Asset Pricing Model,” *Journal of Financial Economics*.
- Fama, Eugene F., and Kenneth R. French, 官方 Data Library: “Fama/French 5 Factors (2x3)”。  
- 课程提供的中国市场实证论文（见 `行为金融学2025_作业资料/reference` 文件夹）。  
- 《因子投资：方法与实践》第二章（课程 reference 节选）。

