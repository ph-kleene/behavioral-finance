from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import statsmodels.api as sm

from paths import OUTPUT_TABLE_DIR, PROCESSED_DATA_DIR
from utils.io import write_csv
from utils.logging import get_logger

LOGGER = get_logger("analysis.regression_ff5")

PORTFOLIOS_FILE = PROCESSED_DATA_DIR / "test_portfolios_25.parquet"
FACTOR_FILE_BASE = PROCESSED_DATA_DIR / "factors_monthly"
REG_RESULTS_BASE = OUTPUT_TABLE_DIR / "regression_results"
MOMENTUM_FILE = PROCESSED_DATA_DIR / "momentum_factor.parquet"

FACTOR_SETS = {
    "capm": {"scheme": "2x3", "columns": ["MKT"]},
    "ff3": {"scheme": "2x3", "columns": ["MKT", "SMB", "HML"]},
    "carhart": {"scheme": "2x3", "columns": ["MKT", "SMB", "HML", "MOM"]},
    "ff5": {"scheme": "2x3", "columns": ["MKT", "SMB", "HML", "RMW", "CMA"]},
    "ff5_mom": {"scheme": "2x3", "columns": ["MKT", "SMB", "HML", "RMW", "CMA", "MOM"]},
    "ff5_cmao": {"scheme": "2x3", "columns": ["MKT", "SMB", "HML", "RMW", "CMAO"]},
    "ff5_cmao_mom": {"scheme": "2x3", "columns": ["MKT", "SMB", "HML", "RMW", "CMAO", "MOM"]},
}


def _format_date(date_str: str) -> str:
    return pd.to_datetime(date_str).strftime("%Y%m")


def _window_suffix(start: str | None, end: str | None) -> str:
    parts = []
    if start:
        parts.append(f"from{_format_date(start)}")
    if end:
        parts.append(f"to{_format_date(end)}")
    return "" if not parts else "_" + "_".join(parts)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run portfolio regressions for various factor sets")
    parser.add_argument(
        "--model",
        choices=FACTOR_SETS.keys(),
        default="ff5",
        help="Factor model to estimate",
    )
    parser.add_argument(
        "--scheme",
        choices=["2x3", "2x2", "2x2x2x2"],
        default="2x3",
        help="Factor construction scheme",
    )
    parser.add_argument("--start", type=str, default=None, help="Optional start date YYYY-MM")
    parser.add_argument("--end", type=str, default=None, help="Optional end date YYYY-MM")
    return parser.parse_args()


def _factor_file(scheme: str) -> Path:
    candidate = PROCESSED_DATA_DIR / f"factors_monthly_{scheme}.parquet"
    if candidate.exists():
        return candidate
    return FACTOR_FILE_BASE.with_suffix(".parquet")


def _result_path(model: str, scheme: str, start: str | None, end: str | None) -> Path:
    suffix = _window_suffix(start, end)
    return REG_RESULTS_BASE.with_name(f"{REG_RESULTS_BASE.stem}_{model}_{scheme}{suffix}.csv")


def load_datasets(scheme: str, start: str | None = None, end: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    factors = pd.read_parquet(_factor_file(scheme))
    factors["trade_month"] = pd.to_datetime(factors["trade_month"])
    factors = factors.set_index("trade_month").sort_index()

    portfolios = pd.read_parquet(PORTFOLIOS_FILE)
    portfolios["trade_month"] = pd.to_datetime(portfolios["trade_month"])
    portfolios = portfolios.set_index("trade_month").sort_index()

    index = factors.index.intersection(portfolios.index)
    factors = factors.loc[index]
    portfolios = portfolios.loc[index]
    if start:
        cutoff = pd.to_datetime(start) + pd.offsets.MonthEnd(0)
        factors = factors[factors.index >= cutoff]
        portfolios = portfolios[portfolios.index >= cutoff]
    if end:
        cutoff = pd.to_datetime(end) + pd.offsets.MonthEnd(0)
        factors = factors[factors.index <= cutoff]
        portfolios = portfolios[portfolios.index <= cutoff]
    return factors, portfolios


def _merge_momentum(factors: pd.DataFrame) -> pd.DataFrame:
    if not MOMENTUM_FILE.exists():
        raise FileNotFoundError("Momentum factor file missing; please run factors.compute_momentum")
    mom = pd.read_parquet(MOMENTUM_FILE)
    mom["trade_month"] = pd.to_datetime(mom["trade_month"])
    mom = mom.set_index("trade_month")[ ["MOM"] ]
    return factors.join(mom, how="left")


def _ensure_columns(factors: pd.DataFrame, columns: list[str]) -> None:
    missing = [col for col in columns if col not in factors.columns]
    if missing:
        raise ValueError(f"Missing factor columns: {missing}. Please recompute factors or adjust model choice.")


def run_regressions(factors: pd.DataFrame, portfolios: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rf = factors["Rf"]
    factor_data = factors[columns]
    X = sm.add_constant(factor_data)

    results = []
    for column in portfolios.columns:
        y = portfolios[column] - rf
        model = sm.OLS(y, X, missing="drop").fit()
        row = {
            "portfolio": column,
            "alpha": model.params.get("const", float("nan")),
            "alpha_t": model.tvalues.get("const", float("nan")),
            "adj_r2": model.rsquared_adj,
        }
        for factor in columns:
            row[f"beta_{factor}"] = model.params.get(factor, float("nan"))
            row[f"t_{factor}"] = model.tvalues.get(factor, float("nan"))
        results.append(row)
    return pd.DataFrame(results).sort_values("portfolio")


def main() -> None:
    args = _parse_args()
    model_cfg = FACTOR_SETS[args.model]
    scheme = args.scheme
    factors, portfolios = load_datasets(scheme, args.start, args.end)
    if "MOM" in model_cfg["columns"] and "MOM" not in factors.columns:
        factors = _merge_momentum(factors)
    _ensure_columns(factors, model_cfg["columns"])
    regression_results = run_regressions(factors, portfolios, model_cfg["columns"])
    output_path = _result_path(args.model, scheme, args.start, args.end)
    write_csv(regression_results, output_path, index=False)
    LOGGER.info(
        "Saved %s regression results for %d portfolios (%s scheme)",
        args.model,
        len(regression_results),
        f"{scheme}{_window_suffix(args.start, args.end)}",
    )


if __name__ == "__main__":
    main()
