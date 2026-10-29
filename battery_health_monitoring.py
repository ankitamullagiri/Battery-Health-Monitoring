"""Battery Health Monitoring.

Exploratory analysis of Battery Management System (BMS) telemetry from five
lithium-ion packs. For each pack it:

1. parses the timestamped readings and resamples them to hourly means,
2. plots temperature, pack voltage, charge-discharge cycles, state of charge
   and current over time,
3. compares packs on average values and flags the extremes, and
4. computes cell-voltage imbalance (max minus min cell voltage), an early
   warning sign of cell degradation.

Usage:
    python battery_health_monitoring.py            # save figures to results/
    python battery_health_monitoring.py --show     # also open the plots
"""

import argparse
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
RESULTS_DIR = Path(__file__).parent / "results"

BATTERIES = {
    "Battery 2": "battery2.csv",
    "Battery 3": "battery3.csv",
    "Battery 4": "battery4.csv",
    "Battery 5": "battery5.csv",
    "Battery 6": "battery6.csv",
}

COLUMNS = {
    "battery temp": "Temperature (°C)",
    "battery voltage( V )": "Voltage (V)",
    "charge discharge_cycles": "Charge-discharge cycles",
    "soc( % )": "SOC (%)",
    "current( A )": "Current (A)",
}

PLACEHOLDER_YEAR = 2023  # the exports have day and month but no year


def load_battery(path: Path) -> pd.DataFrame:
    """Read one BMS export and index it by timestamp.

    Timestamps look like '05-Jul  00:00:12 ' (no year), so whitespace is
    normalised and a placeholder year added before parsing. Cell-voltage
    column names vary between exports ('cell voltage_7' vs '_07'), so cells
    are matched by prefix.
    """
    df = pd.read_csv(path)
    times = df["time"].str.split().str.join(" ") + f" {PLACEHOLDER_YEAR}"
    df.index = pd.to_datetime(times, format="%d-%b %H:%M:%S %Y")
    cell_cols = [c for c in df.columns if c.startswith("cell voltage")]
    df = df[list(COLUMNS) + cell_cols].apply(pd.to_numeric, errors="coerce")
    cells = df[cell_cols].dropna(axis=1, how="all")
    df = df[list(COLUMNS)].copy()
    df["cell_imbalance_mV"] = (cells.max(axis=1) - cells.min(axis=1)) * 1000
    df.attrs["n_cells"] = cells.shape[1]
    return df.sort_index()


def plot_battery(name: str, hourly: pd.DataFrame, show: bool) -> Path:
    """Plot each key signal over time for one pack and save the figure."""
    fig, axes = plt.subplots(3, 2, figsize=(12, 10))
    for ax, (col, label) in zip(axes.flat, COLUMNS.items()):
        ax.plot(hourly.index, hourly[col])
        ax.set_title(label)
        ax.set_xlabel("Time")
        ax.tick_params(axis="x", rotation=30)
    ax = axes.flat[-1]
    ax.plot(hourly.index, hourly["cell_imbalance_mV"], color="tab:red")
    ax.set_title("Cell voltage imbalance (mV)")
    ax.set_xlabel("Time")
    ax.tick_params(axis="x", rotation=30)
    for ax in axes.flat:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.suptitle(f"{name} – hourly averages ({hourly.index[0]:%d %b})")
    fig.tight_layout()
    out = RESULTS_DIR / f"{name.lower().replace(' ', '_')}.png"
    fig.savefig(out, dpi=120)
    if show:
        plt.show()
    plt.close(fig)
    return out


def summarise(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Average value of each signal per pack."""
    rows = {
        name: df[list(COLUMNS) + ["cell_imbalance_mV"]].mean()
        for name, df in data.items()
    }
    summary = pd.DataFrame(rows).T
    summary.columns = [*COLUMNS.values(), "Cell imbalance (mV)"]
    return summary.round(2)


def main(show: bool = False) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    data = {name: load_battery(DATA_DIR / file) for name, file in BATTERIES.items()}

    for name, df in data.items():
        hourly = df.resample("h").mean()
        out = plot_battery(name, hourly, show)
        print(f"{name}: {len(df):,} readings, {df.attrs['n_cells']} cells, "
              f"{df.index.min():%d %b %H:%M} to {df.index.max():%d %b %H:%M} -> {out.name}")

    summary = summarise(data)
    summary.to_csv(RESULTS_DIR / "summary.csv")
    print("\nAverage values per battery:")
    print(summary.to_string())

    print("\nHighest / lowest average per signal:")
    for col in summary.columns:
        print(f"- {col}: highest {summary[col].idxmax()}, lowest {summary[col].idxmin()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--show", action="store_true", help="display plots as well as saving them")
    main(parser.parse_args().show)
