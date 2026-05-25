from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from src.analysis import optimize_dispatch, summarize_dispatch
from src.cleaning import build_project_timeseries
from src.config import AssetConfig
from src.plotting import save_plots
from src.reader import load_dataset, validate_schema
from src.utils import dataframe_quality_report, ensure_dir, setup_logging

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project 6 - Energy management optimization pipeline")
    parser.add_argument("--data", type=Path, default=Path("data/raw"), help="Input raw dataset folder or file")
    parser.add_argument("--processed", type=Path, default=Path("data/processed"), help="Folder where normalized CSV files are saved/read")
    parser.add_argument("--refresh-processed", action="store_true", help="Force raw reload and overwrite processed CSV files")
    parser.add_argument("--no-processed-cache", action="store_true", help="Disable processed CSV cache and always read raw input")
    parser.add_argument("--out", type=Path, default=Path("outputs"), help="Output folder")
    parser.add_argument("--plots", type=Path, default=None, help="Plots folder. Default: <out>/plots")
    parser.add_argument("--fuel-cost", type=float, nargs="+", default=[0.45, 0.60], help="DG fuel cost scenarios [EUR/kWh]")
    parser.add_argument("--use-forecast", action="store_true", help="Use forecasted columns instead of actual columns")
    parser.add_argument("--run-all", action="store_true", help="Run complete pipeline")
    parser.add_argument("--chunk-hours", type=int, default=168, help="Optimization chunk size. Weekly chunks keep annual runs fast.")
    return parser.parse_args()


def run_pipeline(
    data_path: Path,
    processed_dir: Path | None,
    out_dir: Path,
    plots_dir: Path,
    fuel_costs: list[float],
    use_forecast: bool,
    chunk_hours: int = 168,
    use_processed_cache: bool = True,
    refresh_processed: bool = False,
) -> None:
    ensure_dir(out_dir)
    ensure_dir(plots_dir)
    setup_logging(out_dir / "pipeline.log")

    LOGGER.info("Starting pipeline")
    datasets = load_dataset(
        data_path,
        processed_dir=processed_dir,
        use_processed=use_processed_cache,
        refresh_processed=refresh_processed,
    )
    validate_schema(datasets)

    quality = pd.DataFrame([dataframe_quality_report(name, df) for name, df in datasets.items()])
    quality.to_csv(out_dir / "data_quality_report.csv", index=False)
    LOGGER.info("Loaded datasets: %s", list(datasets))

    asset = AssetConfig()
    timeseries = build_project_timeseries(datasets, asset=asset, use_forecast=use_forecast)
    timeseries.to_csv(out_dir / "normalized_timeseries.csv", index=False)

    summaries: list[pd.DataFrame] = []
    for fuel_cost in fuel_costs:
        chunks: list[pd.DataFrame] = []
        initial_soc = asset.soc_initial
        for start in range(0, len(timeseries), chunk_hours):
            chunk = timeseries.iloc[start : start + chunk_hours].reset_index(drop=True)
            solved = optimize_dispatch(chunk, asset=asset, fuel_cost_eur_kwh=fuel_cost, initial_soc_pct=initial_soc)
            initial_soc = float(solved["soc_pct"].iloc[-1])
            chunks.append(solved)
        dispatch = pd.concat(chunks, ignore_index=True)
        tag = str(fuel_cost).replace(".", "_")
        dispatch_path = out_dir / f"dispatch_fuel_{tag}.csv"
        dispatch.to_csv(dispatch_path, index=False)
        summary = summarize_dispatch(dispatch, asset=asset)
        summary.insert(0, "scenario", f"fuel_{fuel_cost:.2f}_eur_kwh")
        summaries.append(summary)
        save_plots(dispatch, plots_dir / f"fuel_{tag}")
        LOGGER.info("Scenario %.3f saved to %s", fuel_cost, dispatch_path)

    pd.concat(summaries, ignore_index=True).to_csv(out_dir / "summary.csv", index=False)
    LOGGER.info("Pipeline completed. Output folder: %s", out_dir)


def main() -> None:
    args = parse_args()
    plots_dir = args.plots if args.plots is not None else args.out / "plots"
    processed_dir = None if args.no_processed_cache else args.processed
    run_pipeline(
        data_path=args.data,
        processed_dir=processed_dir,
        out_dir=args.out,
        plots_dir=plots_dir,
        fuel_costs=args.fuel_cost,
        use_forecast=args.use_forecast,
        chunk_hours=args.chunk_hours,
        use_processed_cache=not args.no_processed_cache,
        refresh_processed=args.refresh_processed,
    )


if __name__ == "__main__":
    main()
