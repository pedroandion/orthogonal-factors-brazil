"""Exports the Brazilian return series used by this repository from the companion repository.

The companion repository, brazil-equity-factors, keeps the returns of its strategies and of its
screening factors only in memory. This script runs its notebooks in memory, up to the cell that
creates each series, and saves the series in data/. It does not change any file of the companion
repository, and it stops if the companion has uncommitted changes before or after the run.

Run it from the root of this repository, with the requirements of the companion installed:

    python scripts/export_companion_data.py ../brazil-equity-factors
"""
import argparse
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import nbformat
import pandas as pd
from nbclient import NotebookClient

DATA = Path(__file__).resolve().parents[1] / "data"


def git(companion, *args):
    return subprocess.run(["git", "-C", str(companion), *args], capture_output=True, text=True, check=True).stdout.strip()


def run_cells(companion, notebook, cells, checks, export_code):
    # Runs the given cells of a companion notebook in one kernel, then the export code
    nb = nbformat.read(companion / notebook, as_version=4)
    for i, text in checks.items():
        if text not in nb.cells[i].source:
            raise RuntimeError(f"{notebook} cell {i} no longer contains {text!r}; update the cell numbers")
    nb.cells = [nb.cells[i] for i in cells] + [nbformat.v4.new_code_cell(export_code)]
    print(f"Running {notebook}, cells {cells[0]} to {cells[-1]}")
    NotebookClient(nb, timeout=None, kernel_name="python3", resources={"metadata": {"path": str(companion)}}).execute()


def describe(path):
    df = pd.read_csv(path, index_col=0)
    return {"rows": len(df), "columns": df.shape[1], "first_date": df.index[0], "last_date": df.index[-1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("companion", type=Path, help="local clone of brazil-equity-factors")
    companion = parser.parse_args().companion.resolve()

    if git(companion, "status", "--porcelain"):
        raise RuntimeError("The companion repository has uncommitted changes")
    commit = git(companion, "rev-parse", "HEAD")
    DATA.mkdir(exist_ok=True)
    out = DATA.as_posix()

    # Local factor returns, already published by the companion
    shutil.copyfile(companion / "data" / "ff_factors.csv.gz", DATA / "brazil_factors.csv.gz")

    # Daily returns of the stocks on the days they are in the investable universe, and their
    # relative market value on the first trading day of each year. The mask is the one of 03 cell 10;
    # the run stops before cell 11, which rewrites data/ff_factors.csv.gz.
    run_cells(companion, "03_historical_betas.ipynb", list(range(0, 7)),
              {6: "volume_filter =", 10: "mask = investable * has_price * volume_filter"},
              f"""
mask = investable * has_price * volume_filter
stock_returns = (prices_df.pct_change(fill_method = None).loc[mask.index] * mask).dropna(how = 'all', axis = 1)
stock_returns = stock_returns.loc['2010-01-05':]
stock_returns.index.name = 'Date'
stock_returns.to_csv('{out}/brazil_stock_returns.csv.gz', float_format = '%.8g')
year_starts = stock_returns.groupby(stock_returns.index.year).head(1).index
stock_weights = (market_value * mask).loc[year_starts, stock_returns.columns].dropna(how = 'all', axis = 1)
stock_weights.index.name = 'Date'
stock_weights.to_csv('{out}/brazil_stock_weights.csv.gz', float_format = '%.8g')
""")

    # Long-short returns of the 32 screening factors, top 30% minus bottom 30%. Cells 17 and 19
    # (quintiles and single legs) are skipped, because cell 20 does not use them.
    run_cells(companion, "04_factor_screening.ipynb", list(range(0, 16)) + [20],
              {14: "factors_dict.update(magic_formula)", 20: "factors_ls_returns = dict()"},
              f"""
screening_returns = pd.DataFrame({{name: returns['30%'] for name, returns in factors_ls_returns.items()}})
screening_returns.index.name = 'Date'
screening_returns.to_csv('{out}/brazil_screening_factors.csv.gz')
""")

    # Daily returns of the multi-factor strategy and its three sleeves
    run_cells(companion, "05_multi_factor_strategy.ipynb", list(range(0, 17)),
              {15: "ret_comb = backtest_quintiles", 16: "consolidated_returns = pd.concat"},
              f"""
strategy_returns = consolidated_returns[['Magic Formula', 'LowVol Momentum', 'Quality', 'Combination']]
strategy_returns.index.name = 'Date'
strategy_returns.to_csv('{out}/brazil_strategies.csv.gz')
""")

    if git(companion, "status", "--porcelain"):
        raise RuntimeError("The run changed files of the companion repository")

    files = ["brazil_factors.csv.gz", "brazil_strategies.csv.gz", "brazil_screening_factors.csv.gz",
             "brazil_stock_returns.csv.gz", "brazil_stock_weights.csv.gz"]
    manifest = {"companion": "https://github.com/pedroandion/brazil-equity-factors",
                "companion_commit": commit,
                "exported_on": date.today().isoformat(),
                "files": {name: describe(DATA / name) for name in files}}
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
