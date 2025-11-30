from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import statsmodels.api as sm

from paths import OUTPUT_TABLE_DIR, PROCESSED_DATA_DIR
from utils.io import write_csv
from utils.logging import get_logger

LOGGER = get_logger("analysis.factor_diagnostics")

FACTOR_FILE_BASE = PROCESSED_DATA_DIR / "factors_monthly.parquet"
MOMENTUM_FILE = PROCESSED_DATA_DIR / "momentum_factor.parquet"

STYLE_TARGETS = ["RMW", "CMA", "MOM"]
STYLE_FACTORS = ["MKT", "SMB", "HML"]
REDUNDANCY_CANDIDATES = ["HML", "RMW", "CMA", "MOM"]


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
    parser = argparse.ArgumentParser(description="Factor diagnostics: style regressions and redundancy tests")
    parser.add_argument(
        "--scheme",
        choices=["2x3", "2x2", "2x2x2x2"],
        default="2x3",
        help="Factor construction scheme",
    )
    parser.add_argument("--start", type=str, default=None, help="Optional YYYY-MM start date")
    parser.add_argument("--end", type=str, default=None, help="Optional YYYY-MM end date")
    return parser.parse_args()


def _factor_file(scheme: str) -> Path:
    candidate = PROCESSED_DATA_DIR / f"factors_monthly_{scheme}.parquet"
    return candidate if candidate.exists() else FACTOR_FILE_BASE


def _load_factors(scheme: str) -> pd.DataFrame:
    df = pd.read_parquet(_factor_file(scheme))
    if "trade_month" in df.columns:
        df["trade_month"] = pd.to_datetime(df["trade_month"])
        df = df.set_index("trade_month")
    df = df.sort_index()
    if MOMENTUM_FILE.exists() and "MOM" not in df.columns:
        mom = pd.read_parquet(MOMENTUM_FILE)
        mom["trade_month"] = pd.to_datetime(mom["trade_month"])
        mom = mom.set_index("trade_month")[["MOM"]]
        df = df.join(mom, how="left")
    return df


def _slice(df: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    if start:
        df = df[df.index >= pd.to_datetime(start) + pd.offsets.MonthEnd(0)]
    if end:
        df = df[df.index <= pd.to_datetime(end) + pd.offsets.MonthEnd(0)]
    return df


def _run_regression(y: pd.Series, X: pd.DataFrame) -> sm.regression.linear_model.RegressionResultsWrapper:
    X_const = sm.add_constant(X)
    return sm.OLS(y, X_const, missing="drop").fit()


def style_regressions(factors: pd.DataFrame) -> pd.DataFrame:
    available_targets = [f for f in STYLE_TARGETS if f in factors.columns]
    rows = []
    X = factors[STYLE_FACTORS]
    for target in available_targets:
        y = factors[target]
        model = _run_regression(y, X)
        row = {
            "target": target,
            "alpha": model.params.get("const", float("nan")),
            "alpha_t": model.tvalues.get("const", float("nan")),
            "adj_r2": model.rsquared_adj,
        }
        for factor in STYLE_FACTORS:
            row[f"beta_{factor}"] = model.params.get(factor, float("nan"))
            row[f"t_{factor}"] = model.tvalues.get(factor, float("nan"))
        rows.append(row)
    return pd.DataFrame(rows)


def redundancy_tests(factors: pd.DataFrame) -> pd.DataFrame:
    rows = []
    base_cols = [col for col in ["MKT", "SMB", "HML", "RMW", "CMA", "MOM"] if col in factors.columns]
    for target in REDUNDANCY_CANDIDATES:
        if target not in factors.columns:
            continue
        regressors = [col for col in base_cols if col != target]
        if not regressors:
            continue
        model = _run_regression(factors[target], factors[regressors])
        row = {
            "target": target,
            "alpha": model.params.get("const", float("nan")),
            "alpha_t": model.tvalues.get("const", float("nan")),
            "adj_r2": model.rsquared_adj,
        }
        for factor in regressors:
            row[f"beta_{factor}"] = model.params.get(factor, float("nan"))
            row[f"t_{factor}"] = model.tvalues.get(factor, float("nan"))
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    args = _parse_args()
    factors = _load_factors(args.scheme)
    factors = _slice(factors, args.start, args.end)
    if factors.empty:
        raise ValueError("No factor observations available for the specified scheme/sample window")

    style = style_regressions(factors)
    redundancy = redundancy_tests(factors)

    suffix = _window_suffix(args.start, args.end)
    style_output = OUTPUT_TABLE_DIR / f"factor_style_tests_{args.scheme}{suffix}.csv"
    redundancy_output = OUTPUT_TABLE_DIR / f"factor_redundancy_tests_{args.scheme}{suffix}.csv"
    write_csv(style, style_output, index=False)
    write_csv(redundancy, redundancy_output, index=False)
    LOGGER.info(
        "Saved style regressions (%d rows) and redundancy tests (%d rows) for scheme %s",
        len(style),
        len(redundancy),
        args.scheme,
    )


if __name__ == "__main__":
    main()
