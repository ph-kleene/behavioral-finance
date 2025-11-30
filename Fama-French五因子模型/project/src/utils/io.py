from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path, **kwargs) -> pd.DataFrame:
    if "dtype" not in kwargs:
        kwargs["dtype"] = {"Stkcd": str}
    return pd.read_csv(path, **kwargs)


def write_parquet(df: pd.DataFrame, path: Path, *, index: bool = False) -> None:
    ensure_parent(path)
    df.to_parquet(path, index=index)


def write_csv(df: pd.DataFrame, path: Path, *, index: bool = False) -> None:
    ensure_parent(path)
    df.to_csv(path, index=index)


def coerce_numeric(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    for col in columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
