from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssetConfig:
    """
    Configuration for the asset and its constraints.
    Values are based on the specifications for Project 6, but can be overridden for experimentation.
    """
    pv_nom_kw: float = 40.0
    wind_nom_kw: float = 60.0
    office_nom_kw: float = 180.0
    battery_power_kw: float = 130.0
    battery_capacity_kwh: float = 130.0
    battery_eta_charge: float = 0.95
    battery_eta_discharge: float = 0.95
    soc_min: float = 0.10
    soc_max: float = 0.90
    soc_initial: float = 0.50
    pev_power_kw: float = 10.0
    pev_eta: float = 0.90
    pev_daily_energy_kwh: float = 30.0
    generator_power_max_kw: float = 70.0
    generator_power_min_kw: float = 20.0
    generator_eta: float = 0.60
    grid_import_max_kw: float = 200.0
    grid_export_max_kw: float = 100.0
    timestep_hours: float = 1.0


@dataclass(frozen=True)
class TariffConfig: 
    """Configuration for the tariff prices."""
    f1_eur_kwh: float = 0.53276
    f2_eur_kwh: float = 0.54858
    f3_eur_kwh: float = 0.46868


DEFAULT_RANDOM_SEED = 42
