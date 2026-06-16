from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.config import AssetConfig, TariffConfig

LOGGER = logging.getLogger(__name__)


def _pick_dataset(datasets: dict[str, pd.DataFrame], contains: str) -> pd.DataFrame:
    """Pick a dataset by case-insensitive substring match on the name. Raises KeyError if not found or multiple matches."""
    matches = [df for name, df in datasets.items() if contains.lower() in name.lower()]
    if not matches:
        raise KeyError(f"Dataset containing '{contains}' not found. Available: {list(datasets)}")
    return matches[0]


def _series_from_mat_3cols(df: pd.DataFrame, forecast_name: str, actual_name: str) -> pd.DataFrame:
    """Convert a matrix with 3 columns (hour, forecast, actual) to a DataFrame."""
    if df.shape[1] < 3:
        raise ValueError(f"Expected at least 3 columns for hour/forecast/actual, got {df.shape[1]}")
    return pd.DataFrame({forecast_name: df.iloc[:, 1].astype(float), actual_name: df.iloc[:, 2].astype(float)})


def _tariff_fascia(index: pd.DatetimeIndex, tariff: TariffConfig) -> pd.Series:
    """Return a Series of import prices based on the tariff fascia rules for the given timestamps."""
    values: list[float] = []
    for ts in index:
        if ts.weekday() >= 5:
            values.append(tariff.f3_eur_kwh)
        elif 8 <= ts.hour < 19:
            values.append(tariff.f1_eur_kwh)
        elif 7 <= ts.hour < 8 or 19 <= ts.hour < 23:
            values.append(tariff.f2_eur_kwh)
        else:
            values.append(tariff.f3_eur_kwh)
    return pd.Series(values, index=index, name="import_price_eur_kwh")


def build_project_timeseries(
    datasets: dict[str, pd.DataFrame],
    asset: AssetConfig = AssetConfig(),
    tariff: TariffConfig = TariffConfig(),
    use_forecast: bool = False,
) -> pd.DataFrame:
    """Create a normalized hourly table for Project 6.

    Uses actual columns by default; set use_forecast=True to run on forecasted data.
    """
    office_raw = _pick_dataset(datasets, "office_load")
    res_raw = _pick_dataset(datasets, "res_1_year_pu")
    pun_raw = _pick_dataset(datasets, "PUN")
    temp_raw = _pick_dataset(datasets, "T_ex")
    ir_raw = _pick_dataset(datasets, "Ir")

    office = _series_from_mat_3cols(office_raw, "office_load_forecast_kwh", "office_load_actual_kwh")
    temp = _series_from_mat_3cols(temp_raw, "temperature_forecast_c", "temperature_actual_c")
    ir = _series_from_mat_3cols(ir_raw, "irradiance_forecast", "irradiance_actual")

    if res_raw.shape[1] < 2:
        raise ValueError("Renewable profile dataset must contain forecast and actual columns")

    n = min(len(office), len(res_raw), len(pun_raw), len(temp), len(ir))
    if n < 24:
        raise ValueError("At least 24 hourly records are required")

    idx = pd.date_range("2022-01-01 00:00:00", periods=n, freq="h")
    mode_col = "forecast" if use_forecast else "actual"
    res_col = 0 if use_forecast else 1

    df = pd.DataFrame(index=idx)
    df.index.name = "timestamp"
    df["office_load_kwh"] = office[f"office_load_{mode_col}_kwh"].iloc[:n].to_numpy(dtype=float)
    df["pv_kw"] = res_raw.iloc[:n, res_col].to_numpy(dtype=float) * asset.pv_nom_kw
    # MAT file stores both P_pv and P_w as separate variables; reader returns both. Pick wind by exact key if available.
    wind_candidates = [name for name in datasets if "res_1_year_pu_p_w" in name.lower()]
    if wind_candidates:
        wind_raw = datasets[wind_candidates[0]]
        df["wind_kw"] = wind_raw.iloc[:n, res_col].to_numpy(dtype=float) * asset.wind_nom_kw
    else:
        LOGGER.warning("Wind profile P_w not found. Setting wind_kw=0.")
        df["wind_kw"] = 0.0
    df["renewable_kw"] = df["pv_kw"] + df["wind_kw"]
    df["export_price_eur_kwh"] = pun_raw.iloc[:n, 0].to_numpy(dtype=float) / 1000.0
    df["import_price_eur_kwh"] = _tariff_fascia(idx, tariff).to_numpy(dtype=float)
    df["temperature_c"] = temp[f"temperature_{mode_col}_c"].iloc[:n].to_numpy(dtype=float)
    df["irradiance"] = ir[f"irradiance_{mode_col}"].iloc[:n].to_numpy(dtype=float)

    numeric_cols = df.columns
    if df[numeric_cols].isna().any().any():
        LOGGER.warning("Null values found in normalized time series. Applying interpolation and ffill/bfill.")
        df[numeric_cols] = df[numeric_cols].interpolate(limit_direction="both").ffill().bfill()

    for col in ["office_load_kwh", "pv_kw", "wind_kw", "renewable_kw", "import_price_eur_kwh", "export_price_eur_kwh"]:
        df[col] = np.clip(df[col], 0, None)

    return df.reset_index()
