from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.utils import ensure_dir

LOGGER = logging.getLogger(__name__)


def save_plots(dispatch: pd.DataFrame, out_dir: Path, first_hours: int = 168) -> list[Path]:
    """
    Save plots of the dispatch results to the specified output directory. 
    Returns a list of saved file paths.
    Plots include:
    - Battery state of charge over the year
    - Power profiles for the first week
    - Daily net cost over the year
    """
    ensure_dir(out_dir)
    saved: list[Path] = []
    df = dispatch.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    week = df.head(first_hours)

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(df["timestamp"], df["soc_pct"])
    ax.set_title("Battery State of Charge")
    ax.set_xlabel("Time")
    ax.set_ylabel("SoC [-]")
    ax.grid(True, alpha=0.3)
    path = out_dir / "soc_year.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    saved.append(path)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(week["timestamp"], week["office_load_kwh"], label="Office load")
    ax.plot(week["timestamp"], week["renewable_kw"], label="Renewable generation")
    ax.plot(week["timestamp"], week["p_import_kw"], label="Grid import")
    ax.plot(week["timestamp"], week["p_export_kw"], label="Grid export")
    ax.plot(week["timestamp"], week["p_gen_kw"], label="DG")
    ax.set_title("Power profiles - first week")
    ax.set_xlabel("Time")
    ax.set_ylabel("kW / kWh per hour")
    ax.legend()
    ax.grid(True, alpha=0.3)
    path = out_dir / "power_profiles_first_week.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    saved.append(path)

    daily = df.set_index("timestamp").resample("D")["net_cost_eur"].sum().reset_index()
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(daily["timestamp"], daily["net_cost_eur"])
    ax.set_title("Daily net cost")
    ax.set_xlabel("Day")
    ax.set_ylabel("EUR")
    ax.grid(True, alpha=0.3)
    path = out_dir / "daily_net_cost.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    saved.append(path)

    LOGGER.info("Saved plots: %s", [str(p) for p in saved])
    return saved
