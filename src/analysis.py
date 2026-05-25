from __future__ import annotations

import logging
from dataclasses import asdict

import numpy as np
import pandas as pd
from scipy.optimize import linprog

from src.config import AssetConfig

LOGGER = logging.getLogger(__name__)


class OptimizationError(RuntimeError):
    pass


def _var_indices(n: int) -> dict[str, slice]:
    names = ["p_import", "p_export", "p_gen", "p_charge", "p_discharge", "p_curtail", "p_pev", "soc"]
    return {name: slice(i * n, (i + 1) * n) for i, name in enumerate(names)}


def optimize_dispatch(df: pd.DataFrame, asset: AssetConfig, fuel_cost_eur_kwh: float, initial_soc_pct: float | None = None) -> pd.DataFrame:
    required = ["timestamp", "office_load_kwh", "renewable_kw", "import_price_eur_kwh", "export_price_eur_kwh"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Input table missing required columns: {missing}")

    n = len(df)
    ix = _var_indices(n)
    total_vars = 8 * n
    dt = asset.timestep_hours

    c = np.zeros(total_vars)
    c[ix["p_import"]] = df["import_price_eur_kwh"].to_numpy() * dt
    c[ix["p_export"]] = -df["export_price_eur_kwh"].to_numpy() * dt
    c[ix["p_gen"]] = fuel_cost_eur_kwh * dt
    c[ix["p_curtail"]] = 1e-4

    bounds: list[tuple[float, float]] = []
    bounds.extend([(0, asset.grid_import_max_kw)] * n)
    bounds.extend([(0, asset.grid_export_max_kw)] * n)
    bounds.extend([(0, asset.generator_power_max_kw)] * n)
    bounds.extend([(0, asset.battery_power_kw)] * n)
    bounds.extend([(0, asset.battery_power_kw)] * n)
    bounds.extend([(0, float(r)) for r in df["renewable_kw"].to_numpy()])
    bounds.extend([(0, asset.pev_power_kw)] * n)
    bounds.extend([(asset.soc_min * asset.battery_capacity_kwh, asset.soc_max * asset.battery_capacity_kwh)] * n)

    a_eq: list[np.ndarray] = []
    b_eq: list[float] = []

    load = df["office_load_kwh"].to_numpy()
    res = df["renewable_kw"].to_numpy()

    for t in range(n):
        row = np.zeros(total_vars)
        row[ix["p_import"].start + t] = 1
        row[ix["p_discharge"].start + t] = 1
        row[ix["p_gen"].start + t] = 1
        row[ix["p_export"].start + t] = -1
        row[ix["p_charge"].start + t] = -1
        row[ix["p_pev"].start + t] = -1
        row[ix["p_curtail"].start + t] = -1
        a_eq.append(row)
        b_eq.append(load[t] - res[t])

    for t in range(n):
        row = np.zeros(total_vars)
        row[ix["soc"].start + t] = 1
        row[ix["p_charge"].start + t] = -asset.battery_eta_charge * dt
        row[ix["p_discharge"].start + t] = dt / asset.battery_eta_discharge
        if t == 0:
            b_eq.append((asset.soc_initial if initial_soc_pct is None else initial_soc_pct) * asset.battery_capacity_kwh)
        else:
            row[ix["soc"].start + t - 1] = -1
            b_eq.append(0.0)
        a_eq.append(row)

    a_ub: list[np.ndarray] = []
    b_ub: list[float] = []

    for start in range(0, n, 24):
        end = min(start + 24, n)
        row = np.zeros(total_vars)
        row[ix["p_pev"].start + start : ix["p_pev"].start + end] = -asset.pev_eta * dt
        a_ub.append(row)
        b_ub.append(-asset.pev_daily_energy_kwh * (end - start) / 24.0)

    LOGGER.info("Solving LP dispatch: hours=%s, variables=%s, fuel_cost=%s", n, total_vars, fuel_cost_eur_kwh)
    result = linprog(
        c,
        A_ub=np.vstack(a_ub) if a_ub else None,
        b_ub=np.array(b_ub) if b_ub else None,
        A_eq=np.vstack(a_eq),
        b_eq=np.array(b_eq),
        bounds=bounds,
        method="highs",
    )

    if not result.success:
        raise OptimizationError(f"Optimization failed: {result.message}")

    out = df.copy()
    solution = result.x
    for name, sl in ix.items():
        out[name + ("_kwh" if name == "soc" else "_kw")] = solution[sl]

    out["soc_pct"] = out["soc_kwh"] / asset.battery_capacity_kwh
    out["net_cost_eur"] = (
        out["p_import_kw"] * out["import_price_eur_kwh"]
        - out["p_export_kw"] * out["export_price_eur_kwh"]
        + out["p_gen_kw"] * fuel_cost_eur_kwh
    ) * dt
    out["fuel_cost_eur_kwh"] = fuel_cost_eur_kwh
    return out


def summarize_dispatch(dispatch: pd.DataFrame, asset: AssetConfig) -> pd.DataFrame:
    summary = {
        "hours": len(dispatch),
        "total_load_kwh": dispatch["office_load_kwh"].sum(),
        "total_renewable_kwh": dispatch["renewable_kw"].sum(),
        "total_import_kwh": dispatch["p_import_kw"].sum(),
        "total_export_kwh": dispatch["p_export_kw"].sum(),
        "total_generator_kwh": dispatch["p_gen_kw"].sum(),
        "total_curtailment_kwh": dispatch["p_curtail_kw"].sum(),
        "total_pev_charge_grid_side_kwh": dispatch["p_pev_kw"].sum(),
        "total_pev_delivered_kwh": dispatch["p_pev_kw"].sum() * asset.pev_eta,
        "net_cost_eur": dispatch["net_cost_eur"].sum(),
        "soc_min_pct": dispatch["soc_pct"].min(),
        "soc_max_pct": dispatch["soc_pct"].max(),
        "soc_final_pct": dispatch["soc_pct"].iloc[-1],
    }
    return pd.DataFrame([summary | {"asset_config": str(asdict(asset))}])
