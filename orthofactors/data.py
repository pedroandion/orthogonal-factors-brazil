"""
data.py — loaders of the Ken French data library and of the Brazilian series
in data/.
"""

import re
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

KEN_FRENCH_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{}_CSV.zip"
VALUE_WEIGHTED = "Average Value Weighted Returns -- Monthly"
EQUAL_WEIGHTED = "Average Equal Weighted Returns -- Monthly"

# The seven local factors of brazil-equity-factors. The data start on 2010-01-05,
# when BAB starts. Quality, and so the full multi-factor strategy, holds stocks
# only from February 2011, so the analyses start in January 2012. The earlier
# data serve only estimates that need a past, such as the betas of the hedges.
BRAZIL_FACTORS = ["Mkt_RF", "SMB", "HML", "RMW", "CMA", "WML", "BAB"]
BRAZIL_STRATEGIES = ["Combination", "Magic Formula", "LowVol Momentum", "Quality"]
DATA_START = "2010-01-05"
DAILY_START = "2012-01-02"
MONTHLY_SAMPLE = slice("2012-01", "2026-06")


# ---------------------------------------------------------------------------
# Ken French data library
# ---------------------------------------------------------------------------

def download_ken_french(name: str, folder: str = "data/external") -> Path:
    """Download a zipped CSV of the Ken French data library once and keep it in folder."""
    path = Path(folder) / f"{name}_CSV.zip"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(KEN_FRENCH_URL.format(name), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            path.write_bytes(response.read())
    return path


def read_ken_french(name: str, title: str = None, folder: str = "data/external") -> pd.DataFrame:
    """
    One monthly table of a file of the Ken French data library.

    Parameters
    ----------
    name : str
        File name without the '_CSV.zip' suffix, such as '6_Portfolios_2x3'.
    title : str, optional
        Part of the title of the table, such as VALUE_WEIGHTED. Without it,
        the first monthly table of the file.

    Returns
    -------
    pd.DataFrame
        Decimal returns indexed by month end. The missing values of the
        library (-99.99 and -999) are NaN.
    """
    with zipfile.ZipFile(download_ken_french(name, folder)) as z:
        lines = z.read(z.namelist()[0]).decode("latin-1").splitlines()

    monthly_row = re.compile(r"\s*\d{6}\s*,")
    previous = ""
    for i, line in enumerate(lines):
        is_header = line.startswith(",") and i + 1 < len(lines) and monthly_row.match(lines[i + 1])
        if is_header and (title is None or title in previous):
            columns = [column.strip() for column in line.split(",")[1:] if column.strip()]
            rows = []
            for row in lines[i + 1:]:
                if not monthly_row.match(row):
                    break
                rows.append([value.strip() for value in row.split(",")])
            table = pd.DataFrame([row[1:len(columns) + 1] for row in rows], columns=columns,
                                 index=[row[0] for row in rows]).astype(float)
            table.index = pd.to_datetime(table.index, format="%Y%m") + pd.offsets.MonthEnd(0)
            table.index.name = "Date"
            return table.replace([-99.99, -999.0], np.nan) / 100
        if line.strip():
            previous = line.strip()
    raise ValueError(f"No monthly table with {title!r} in its title in {name}")


# ---------------------------------------------------------------------------
# Brazilian series exported from brazil-equity-factors
# ---------------------------------------------------------------------------

def load_brazil_factors(folder: str = "data", bab: str = "beta_neutral", start: str = DAILY_START) -> pd.DataFrame:
    """
    Daily returns of the seven local factors and the Risk_Free (SELIC), from start.

    The BAB of the companion is dollar-neutral: long the 30% lowest-beta stocks and short
    the 30% highest-beta ones, with a market beta of about -0.9. With bab='beta_neutral',
    the default, each leg is scaled by the inverse of its ex-ante beta, as in Frazzini and
    Pedersen (2014): BAB = (r_L - rf) / beta_L - (r_H - rf) / beta_H. With
    bab='dollar_neutral', BAB is the series of the companion.
    """
    factors = pd.read_csv(Path(folder) / "brazil_factors.csv.gz", index_col="Date", parse_dates=True)
    factors = factors.loc[start:]
    if bab == "beta_neutral":
        legs = pd.read_csv(Path(folder) / "brazil_bab_legs.csv.gz", index_col="Date", parse_dates=True)
        legs = legs.reindex(factors.index)
        risk_free = factors["Risk_Free"]
        factors["BAB"] = ((legs["Low_Beta"] - risk_free) / legs["Low_Beta_Beta"]
                          - (legs["High_Beta"] - risk_free) / legs["High_Beta_Beta"])
    elif bab != "dollar_neutral":
        raise ValueError("bab must be 'beta_neutral' or 'dollar_neutral'")
    return factors


def load_brazil_strategies(folder: str = "data", start: str = DAILY_START) -> pd.DataFrame:
    """
    Daily returns of the multi-factor strategy and its three sleeves in excess of the Risk_Free, from start.

    A strategy holds no stocks until its signals have enough history (Quality starts in
    February 2011), and its return file holds zeros until then; those days are missing here.
    """
    strategies = pd.read_csv(Path(folder) / "brazil_strategies.csv.gz", index_col="Date", parse_dates=True)
    strategies = strategies[BRAZIL_STRATEGIES]
    strategies = strategies.where(strategies.ne(0).cummax())
    risk_free = load_brazil_factors(folder, start=start)["Risk_Free"]
    return strategies.sub(risk_free, axis=0).loc[risk_free.index]


def load_brazil_holdings(folder: str = "data", start: str = DAILY_START) -> tuple:
    """
    Holdings of each strategy at each rebalance, with their weights, and the daily returns of
    every held stock in excess of the Risk_Free, from start. The weights of a rebalance
    date earn returns from the next trading day.
    """
    holdings = pd.read_csv(Path(folder) / "brazil_strategy_holdings.csv.gz", parse_dates=["Date"])
    returns = pd.read_csv(Path(folder) / "brazil_held_stock_returns.csv.gz", index_col="Date", parse_dates=True)
    risk_free = load_brazil_factors(folder, start=start)["Risk_Free"]
    return holdings, returns.sub(risk_free, axis=0).loc[risk_free.index]


def load_brazil_screening(folder: str = "data", start: str = DAILY_START) -> pd.DataFrame:
    """Daily long-short returns of the 32 screening factors, top 30% minus bottom 30%, from start."""
    screening = pd.read_csv(Path(folder) / "brazil_screening_factors.csv.gz", index_col="Date", parse_dates=True)
    return screening.loc[start:]


def load_brazil_stocks(folder: str = "data", start: str = DAILY_START) -> tuple:
    """
    Daily returns of the stocks in excess of the Risk_Free, on the days they
    are in the investable universe, and their relative market value on the
    first trading day of each year, from start.
    """
    returns = pd.read_csv(Path(folder) / "brazil_stock_returns.csv.gz", index_col="Date", parse_dates=True)
    weights = pd.read_csv(Path(folder) / "brazil_stock_weights.csv.gz", index_col="Date", parse_dates=True)
    risk_free = load_brazil_factors(folder, start=start)["Risk_Free"]
    returns = returns.loc[start:]
    return returns.sub(risk_free.reindex(returns.index), axis=0), weights.loc[start:]


def to_monthly(daily: pd.DataFrame) -> pd.DataFrame:
    """
    Compound daily returns into monthly returns, as in 05_multi_factor_strategy of the
    companion. A month without any return is missing.
    """
    return daily.resample("ME").apply(lambda x: (x + 1).prod(min_count=1) - 1)
