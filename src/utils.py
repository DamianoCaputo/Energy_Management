from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd


def setup_logging(log_file: Path | None = None, level: int = logging.INFO) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=handlers,
        force=True,
    )


def normalize_column_name(name: object) -> str:
    text = str(name).strip().lower()
    text = re.sub(r"[^0-9a-zA-Z]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "column"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    cols = [normalize_column_name(c) for c in out.columns]
    seen: dict[str, int] = {}
    unique_cols: list[str] = []
    for col in cols:
        seen[col] = seen.get(col, 0) + 1
        unique_cols.append(col if seen[col] == 1 else f"{col}_{seen[col]}")
    out.columns = unique_cols
    return out


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def dataframe_quality_report(name: str, df: pd.DataFrame) -> dict[str, object]:
    return {
        "dataset": name,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "duplicated_rows": int(df.duplicated().sum()),
        "null_cells": int(df.isna().sum().sum()),
        "columns_list": ", ".join(map(str, df.columns)),
    }


def coerce_numeric(df: pd.DataFrame, exclude: Iterable[str] = ()) -> pd.DataFrame:
    out = df.copy()
    exclude_set = set(exclude)
    for col in out.columns:
        if col not in exclude_set:
            out[col] = pd.to_numeric(out[col], errors="ignore")
    return out
