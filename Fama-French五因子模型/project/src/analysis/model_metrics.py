from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from paths import OUTPUT_TABLE_DIR
from utils.io import write_csv
from utils.logging import get_logger

LOGGER = get_logger("analysis.model_metrics")

REG_DIR = OUTPUT_TABLE_DIR
SUMMARY_BASENAME = "model_metrics_{scheme}{suffix}.csv"


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
    parser = argparse.ArgumentParser(description="Compute GRS and alpha-based metrics from regression outputs")
    parser.add_argument(
        "--scheme",
        choices=["2x3", "2x2", "2x2x2x2"],
        default="2x3",
        help="Factor construction scheme",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["ff5", "ff5_mom", "ff5_cmao", "ff5_cmao_mom"],
        help="Model names matching regression_results_<model>_<scheme>.csv",
    )
    parser.add_argument(
        "--sample-length",
        type=int,
        default=150,
        help="Number of time-series observations used in regressions (T in GRS formula)",
    )
    parser.add_argument("--start", type=str, default=None, help="Optional YYYY-MM start date of sample window")
    parser.add_argument("--end", type=str, default=None, help="Optional YYYY-MM end date of sample window")
    return parser.parse_args()


def _regression_path(model: str, scheme: str, start: str | None, end: str | None) -> Path:
    suffix = _window_suffix(start, end)
    return REG_DIR / f"regression_results_{model}_{scheme}{suffix}.csv"


def _load_table(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "portfolio" not in df.columns or "alpha" not in df.columns:
        raise ValueError(f"Invalid regression result format: {path}")
    return df


def _mean_abs_alpha(df: pd.DataFrame) -> float:
    return float(df["alpha"].abs().mean())


def _abs_alpha_ratio(df: pd.DataFrame) -> float:
    beta_cols = df.filter(like="beta_")
    denom = float(beta_cols.abs().mean().mean())
    num = _mean_abs_alpha(df)
    return num / denom if denom else float("nan")


def _alpha_squared_ratio(df: pd.DataFrame) -> float:
    num = float((df["alpha"] ** 2).mean())
    beta_cols = df.filter(like="beta_")
    denom = float((beta_cols ** 2).mean().mean())
    return num / denom if denom else float("nan")


def _grs_stat(df: pd.DataFrame, T: int) -> float:
    alphas = df["alpha"].to_numpy()
    se = np.divide(
        df["alpha"].to_numpy(),
        df["alpha_t"].replace(0, np.nan).to_numpy(),
        out=np.zeros_like(alphas),
        where=df["alpha_t"].to_numpy() != 0,
    )
    var_eps = np.where(np.isnan(se), 0.0, se ** 2)
    sigma = np.diag(var_eps + 1e-8)
    try:
        inv_sigma = np.linalg.inv(sigma)
    except np.linalg.LinAlgError:
        inv_sigma = np.linalg.pinv(sigma)
    temp = alphas @ inv_sigma @ alphas
    N = len(alphas)
    return float((T / N) * temp)


def compute_metrics(path: Path, sample_length: int) -> dict[str, float]:
    df = _load_table(path)
    metrics = {
        "model": path.stem.replace("regression_results_", ""),
        "mean_abs_alpha": _mean_abs_alpha(df),
        "abs_alpha_ratio": _abs_alpha_ratio(df),
        "alpha_sq_ratio": _alpha_squared_ratio(df),
    }
    if sample_length > 0:
        metrics["grs_stat"] = _grs_stat(df, sample_length)
    else:
        metrics["grs_stat"] = float("nan")
    return metrics


def main() -> None:
    args = _parse_args()
    rows = []
    for model in args.models:
        path = _regression_path(model, args.scheme, args.start, args.end)
        if not path.exists():
            LOGGER.warning(
                "Regression result missing for %s (%s)",
                model,
                f"{args.scheme}{_window_suffix(args.start, args.end)}",
            )
            continue
        rows.append(compute_metrics(path, args.sample_length))
    if not rows:
        raise ValueError("No regression results available for requested models")
    summary = pd.DataFrame(rows)
    suffix = _window_suffix(args.start, args.end)
    output_path = OUTPUT_TABLE_DIR / SUMMARY_BASENAME.format(scheme=args.scheme, suffix=suffix)
    write_csv(summary, output_path, index=False)
    LOGGER.info("Saved model metrics for %d models (%s)", len(summary), f"{args.scheme}{suffix}")


if __name__ == "__main__":
    main()