from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd
from scipy.io import loadmat

from src.utils import ensure_dir, normalize_columns

LOGGER = logging.getLogger(__name__)
SUPPORTED_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls", ".json", ".mat"}
PROCESSED_EXTENSION = ".csv"


def infer_format(path: Path) -> str:
    """
    Infer the file format from the extension. Supported formats: csv, tsv, xlsx, xls, json, mat.
    Raises ValueError if the format is unsupported.
    """
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file format for {path.name}. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )
    return suffix.lstrip(".")


def _safe_dataset_name(name: str) -> str:
    """Return a stable filesystem-safe dataset name."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_").lower()
    return cleaned or "dataset"


def _read_csv_like(path: Path) -> pd.DataFrame:
    """
    Read a CSV-like file with multiple encoding and separator fallbacks.
    Tries common encodings and separators until one works, or raises the last error if all fail.
    """
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    separators = [None, ",", ";", "\t", "|"]
    last_error: Exception | None = None

    for encoding in encodings:
        for sep in separators:
            try:
                return pd.read_csv(path, sep=sep, engine="python", encoding=encoding)
            except Exception as exc:  # noqa: BLE001
                last_error = exc

    raise RuntimeError(f"Unable to read {path}: {last_error}")


def _read_excel(path: Path) -> dict[str, pd.DataFrame]:
    """
    Read an Excel file and return a dictionary of DataFrames, one per sheet. 
    The keys are normalized as {filename}__{sheetname}.
    """
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    return {
        _safe_dataset_name(f"{path.stem}__{sheet}"): normalize_columns(df)
        for sheet, df in sheets.items()
    }


def _read_json(path: Path) -> pd.DataFrame:
    try:
        return pd.read_json(path)
    except ValueError:
        return pd.read_json(path, lines=True)


def _read_mat(path: Path) -> dict[str, pd.DataFrame]:
    """
    Read a MATLAB .mat file and return a dictionary of DataFrames for each variable.
    Variables with 1D or 2D numeric arrays are converted to DataFrames.
    """
    raw: dict[str, Any] = loadmat(path)
    frames: dict[str, pd.DataFrame] = {}

    for variable, value in raw.items():
        if variable.startswith("__"):
            continue

        ndim = getattr(value, "ndim", 0)
        if ndim == 1:
            df = pd.DataFrame({variable: value.ravel()})
        elif ndim == 2:
            df = pd.DataFrame(value)
        else:
            LOGGER.warning(
                "Skipping variable %s in %s: unsupported ndim=%s",
                variable,
                path.name,
                ndim,
            )
            continue

        dataset_name = _safe_dataset_name(f"{path.stem}__{variable}")
        frames[dataset_name] = normalize_columns(df)

    if not frames:
        raise ValueError(f"No tabular variables found in {path}")

    return frames


def read_file(path: Path) -> dict[str, pd.DataFrame]:
    """
    Read a single file and return a dictionary of DataFrames. 
    The key is a normalized name based on the filename and sheet/variable name.
    """
    fmt = infer_format(path)
    LOGGER.info("Reading %s as %s", path.name, fmt)

    if fmt in {"csv", "tsv"}:
        df = _read_csv_like(path) if fmt == "csv" else pd.read_csv(path, sep="\t")
        return {_safe_dataset_name(path.stem): normalize_columns(df)}

    if fmt in {"xlsx", "xls"}:
        return _read_excel(path)

    if fmt == "json":
        return {_safe_dataset_name(path.stem): normalize_columns(_read_json(path))}

    if fmt == "mat":
        return _read_mat(path)

    raise ValueError(f"Unsupported format: {fmt}")


def _list_supported_files(path: Path) -> list[Path]:
    """Return a list of supported files in the given path. If path is a file, return it if supported."""
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS)


def save_processed_dataset(
    datasets: dict[str, pd.DataFrame],
    processed_dir: Path,
    overwrite: bool = True,
) -> list[Path]:
    """Save all loaded datasets as normalized CSV files.

    The CSV files are stored in data/processed or in the folder supplied by
    --processed. Each key in the dataset dictionary becomes one CSV file.
    """
    ensure_dir(processed_dir)
    saved_paths: list[Path] = []

    for name, df in datasets.items():
        safe_name = _safe_dataset_name(name)
        output_path = processed_dir / f"{safe_name}{PROCESSED_EXTENSION}"

        if output_path.exists() and not overwrite:
            LOGGER.info("Processed file already exists, skipping: %s", output_path)
            saved_paths.append(output_path)
            continue

        df.to_csv(output_path, index=False, encoding="utf-8")
        saved_paths.append(output_path)
        LOGGER.info("Saved processed dataset: %s", output_path)

    return saved_paths


def load_processed_dataset(processed_dir: Path) -> dict[str, pd.DataFrame]:
    """Load already converted CSV datasets from the processed folder."""
    processed_dir = Path(processed_dir)
    if not processed_dir.exists():
        raise FileNotFoundError(f"Processed folder not found: {processed_dir}")

    csv_files = sorted(processed_dir.glob(f"*{PROCESSED_EXTENSION}"))
    if not csv_files:
        raise FileNotFoundError(f"No processed CSV files found in {processed_dir}")

    datasets: dict[str, pd.DataFrame] = {}
    for csv_file in csv_files:
        LOGGER.info("Loading processed CSV: %s", csv_file)
        datasets[_safe_dataset_name(csv_file.stem)] = normalize_columns(_read_csv_like(csv_file))

    return datasets


def processed_dataset_exists(processed_dir: Path) -> bool:
    """Return True when at least one processed CSV is already available."""
    return Path(processed_dir).exists() and any(Path(processed_dir).glob(f"*{PROCESSED_EXTENSION}"))


def load_raw_dataset(path: Path) -> dict[str, pd.DataFrame]:
    """Load all supported raw files from a file or directory."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input path not found: {path}")

    files = _list_supported_files(path)
    if not files:
        raise FileNotFoundError(f"No supported dataset files found in {path}")

    datasets: dict[str, pd.DataFrame] = {}
    for file_path in files:
        try:
            datasets.update(read_file(file_path))
        except Exception:
            LOGGER.exception("Failed to load %s", file_path)
            raise

    return datasets


def load_dataset(
    path: Path,
    processed_dir: Path | None = None,
    use_processed: bool = True,
    refresh_processed: bool = False,
) -> dict[str, pd.DataFrame]:
    """Load datasets using a raw-to-processed CSV workflow.

    Behaviour:
    - if processed_dir exists and contains CSV files, load those CSV files;
    - otherwise load raw files (.mat/.csv/.xlsx/.json/.tsv), then save normalized CSV files;
    - if refresh_processed=True, force reload from raw and overwrite processed CSV files.
    """
    if processed_dir is not None and use_processed and not refresh_processed:
        if processed_dataset_exists(processed_dir):
            LOGGER.info("Processed CSV datasets found. Loading from: %s", processed_dir)
            return load_processed_dataset(processed_dir)
        LOGGER.info("No processed CSV found in %s. Loading raw files.", processed_dir)

    datasets = load_raw_dataset(path)

    if processed_dir is not None:
        save_processed_dataset(datasets, processed_dir=processed_dir, overwrite=True)

    return datasets


def validate_schema(
    datasets: dict[str, pd.DataFrame],
    required: dict[str, list[str]] | None = None,
) -> None:
    """
    Validate that the loaded datasets contain the required tables and columns.
    Raises ValueError if any required dataset or column is missing.
    """
    if not datasets:
        raise ValueError("No datasets loaded")

    for name, df in datasets.items():
        if df.empty:
            raise ValueError(f"Dataset {name} is empty")

    if required:
        for dataset_name, columns in required.items():
            if dataset_name not in datasets:
                raise ValueError(f"Required dataset missing: {dataset_name}")
            missing = [col for col in columns if col not in datasets[dataset_name].columns]
            if missing:
                raise ValueError(f"Dataset {dataset_name} missing required columns: {missing}")
