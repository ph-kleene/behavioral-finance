# 李志冰 (2017) 参考文献要点与当前管线差异

> 数据来源：`docs/reference_ff5_lizhibing.txt`

## 样本与数据处理
- **时间范围**：1994-07 至 2015-08 的 A 股月度数据（254 个月），三个月定期存款利率作为无风险利率。
- **股票筛选**：仅保留沪深 A 股；剔除上市首 120 个交易日；使用合并报表财务数据；以流通股本计算市值权重。
- **财务指标**：
  - Size：t 年 6 月末的流通市值。
  - BM：t-1 年末账面价值 / t-1 年 12 月末流通市值。
  - OP：营业利润 / 股东权益合计（t-1 年末）。
  - INV： (TA_{t-1} - TA_{t-2}) / TA_{t-2}。

## 因子构建
- **三种分组法**：
  1. 2×3（Size 中位数 × 指标 30/70 分位）。
  2. 2×2（Size/指标均用 50% 分位）。
  3. 2×2×2×2（四个指标同步按 50% 切分，形成 16 组合）。
- **动量因子**：以 t-1 月底的过去 12→2 个月累计收益 `Prior(2,12)` 排序，结合 Size 中位数获得小/大盘动量组合，构建 MOM。
- **正交化投资因子**：五因子回归时对 CMA 做正交处理 (CMAO) 以消除与其他因子共线影响。

## 当前对齐进展

- **样本区间**：目前清洗与因子构造覆盖 2012-07～2024-12，较文献的 1994-07～2015-08 更短且更靠后；需要在报告中说明样本差异，或追加更早区间的数据。
- **多分组方案**：已在 `factors.assign_groups`、`factors.compute_portfolios`、`factors.compute_factors` 中实现 2×3、2×2、2×2×2×2 三套分组逻辑，并生成对应的组合/因子文件（`factor_groups_<scheme>.parquet`、`sorted_portfolios_<scheme>.parquet`、`factors_monthly_<scheme>.parquet`）。
- **动量因子**：`factors.compute_momentum` 计算 Prior(2,12) 回报并结合 Size 中位数形成动量组合，输出 `momentum_factor.parquet/csv`，可与任意分组方案联用。
- **回归模型**：`analysis/regression_ff5.py` 引入 `--model`（capm/ff3/carhart/ff5/ff5_mom）与 `--scheme` 选项，结果落地 `output/tables/regression_results_<model>_<scheme>.csv`，满足 CAPM、FF3、Carhart4、FF5、FF5+MOM 的对比需求。
- **输出记录**：PLAN.md 已记录新 CLI，便于复现多模型/多分组的回归结果。
- **风格/冗余检验脚本**：新增 `analysis/factor_diagnostics.py`，对 RMW / CMA / MOM 进行 FF3 风格回归，并对 HML/RMW/CMA/MOM 做冗余性检验，结果写入 `output/tables/factor_style_tests_<scheme>.csv` 与 `factor_redundancy_tests_<scheme>.csv`。
- **CMA 正交化**：`factors.compute_factors` 生成 CMAO（对 CMA 在 MKT/SMB/HML/RMW 上回归后的残差），`analysis/regression_ff5.py` 新增 `ff5_cmao`、`ff5_cmao_mom` 模型，输出文件自动扩展。
- **最新输出**：已对 2×3 scheme 重新运行因子、风格检验与三套回归（FF5、FF5+CMAO、FF5+CMAO+MOM），相关 CSV 均在 `output/tables/`。
- **模型指标**：`analysis/model_metrics.py` 汇总 `regression_results_*`，计算 mean|α|、比例指标与近似 GRS，结果保存为 `output/tables/model_metrics_<scheme>.csv`，覆盖 2×3/2×2/2×2×2×2。

## 实证检验
1. **风格效应检验**：RMW、CMA、MOM 对 FF3 回归，关注风险调整后 α。
2. **冗余检验**：用其余四个因子回归某一因子收益，检验 α 是否显著（尤其是 CMA 在全样本中表现冗余）。
3. **模型比较**：
   - CAPM、FF3、Carhart4、FF5、FF5+MOM 等回归。
   - 评价指标：GRS 统计量、\(A|\alpha|\)、\(A|\alpha|/A|r|\)、\(A\alpha^2/A r^2)\) 评估剩余截距大小。
4. **分时期分析**：以 2007-06 为分界（股改完成后）做子样本检验，比较各因子溢价和模型效率。
5. **动量/反转讨论**：验证 FF5 是否能吸收 MOM 效应，报告动量（或反转）在股改前后显著性差异。

## 最新分析结论与限制说明 (2025-11-26 更新)

### 1. 数据窗口与分时期分析限制
- **现状**：项目原始数据始于 2010 年，由于投资因子 (INV) 构建需要滞后 2 年的总资产数据，有效因子样本区间为 **2012-07 至 2024-12**。
- **限制**：李志冰 (2017) 文中以 2007-06（股权分置改革完成）为界进行的子样本分析无法复现。
- **对策**：后续分析将聚焦于 2012-2024 这一“后股改”成熟时期的实证检验，不再尝试进行 2007 年前后的对比。

### 2. 动量因子 (MOM) 显著性讨论
- **实证结果**：在 2012-2024 样本区间内，对 MOM 因子进行 FF5 冗余检验（即 MOM 对 MKT, SMB, HML, RMW, CMA 回归）：
  - **Alpha**：0.0225 (t = 7.28)，统计上高度显著。
  - **结论**：FF5 模型 **无法吸收** 中国 A 股市场在此期间的动量效应。这与部分文献认为 FF5 能解释动量的结论不同，表明在中国市场动量因子仍具有独立的定价能力。

### 3. 五因子冗余性检验
- **HML 冗余性**：HML 对其他四因子回归的截距 $\alpha = 0.0025$ ($t=1.11$)，不显著。支持 FF5 框架下 HML 冗余的假设。
- **CMA/RMW 冗余性**：
  - CMA 截距 $\alpha = -0.0004$ ($t=-0.24$)，不显著。
  - RMW 截距 $\alpha = 0.0017$ ($t=0.83$)，不显著。
  - **分析**：在 2012-2024 区间，价值、盈利与投资因子之间存在较强的共线性（如 CMA 与 HML 负相关 $t=-11.5$），导致互为冗余。这可能暗示该时期 A 股市场的风格因子结构较为单一，或受特定宏观环境影响。

## 下一步计划
1. **报告撰写**：基于上述发现，撰写最终分析报告，重点阐述 FF5 在中国市场的适用性（HML 冗余）及动量因子的独立性。
2. **可视化**：生成因子累积收益图与相关性热力图，直观展示因子间的强相关性。
