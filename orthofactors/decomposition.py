"""
decomposition.py — OLS regressions, Decomposed R², and rolling-window analysis
following Klein & Chow (2013).
"""

from itertools import permutations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .orthogonalization import orthogonalize_gs, orthogonalize_swl


# ---------------------------------------------------------------------------
# OLS regression helpers
# ---------------------------------------------------------------------------

def run_ols(
    asset_returns: pd.Series,
    factors: pd.DataFrame,
    hac_lags: int = None,
) -> object:
    """
    Run OLS regression of asset_returns on factors (with intercept).

    Parameters
    ----------
    asset_returns : pd.Series
        Excess returns of one asset (or raw returns).
    factors : pd.DataFrame
        Factor returns (T × K).  An intercept is added automatically.
    hac_lags : int, optional
        If given, Newey-West (HAC) standard errors with this many lags.

    Returns
    -------
    statsmodels RegressionResultsWrapper
    """
    common = asset_returns.index.intersection(factors.index)
    y = asset_returns.loc[common]
    X = sm.add_constant(factors.loc[common], has_constant="add")
    model = sm.OLS(y, X, missing="drop")
    if hac_lags is None:
        return model.fit()
    return model.fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})


def run_all_regressions(
    asset_returns: pd.DataFrame,
    factors_dict: dict,
) -> dict:
    """
    Run OLS for every (asset, method) combination.

    Parameters
    ----------
    asset_returns : pd.DataFrame
        T × N DataFrame of asset returns.
    factors_dict : dict
        {'original': df, 'swl': df, 'pca': df, 'gs': df}

    Returns
    -------
    dict of dicts: {asset_ticker: {method_name: RegressionResultsWrapper}}
    """
    results = {}
    for ticker in asset_returns.columns:
        results[ticker] = {}
        for method, factors in factors_dict.items():
            results[ticker][method] = run_ols(asset_returns[ticker], factors)
    return results


def extract_betas_table(results: dict) -> pd.DataFrame:
    """
    Build a MultiIndex DataFrame of betas (coefficient estimates).

    Index   : (ticker, method)
    Columns : factor names
    """
    rows = []
    for ticker, method_results in results.items():
        for method, res in method_results.items():
            params = res.params.drop("const", errors="ignore")
            row = params.to_dict()
            row["ticker"] = ticker
            row["method"] = method
            rows.append(row)

    df = pd.DataFrame(rows).set_index(["ticker", "method"])
    return df


def extract_r2_table(results: dict) -> pd.DataFrame:
    """
    Build a DataFrame of R² values.

    Index   : ticker
    Columns : method names
    """
    tickers = list(results.keys())
    methods = list(next(iter(results.values())).keys())
    data = {
        method: [results[t][method].rsquared for t in tickers]
        for method in methods
    }
    return pd.DataFrame(data, index=tickers)


def extract_betas_with_tstats(results: dict) -> pd.DataFrame:
    """
    Build a detailed table: beta, t-stat, and significance stars for each
    (ticker, method, factor) combination.
    """
    rows = []
    for ticker, method_results in results.items():
        for method, res in method_results.items():
            params = res.params.drop("const", errors="ignore")
            tvals = res.tvalues.drop("const", errors="ignore")
            pvals = res.pvalues.drop("const", errors="ignore")
            for factor in params.index:
                stars = (
                    "***" if pvals[factor] < 0.01 else
                    "**" if pvals[factor] < 0.05 else
                    "*" if pvals[factor] < 0.10 else ""
                )
                rows.append({
                    "ticker": ticker,
                    "method": method,
                    "factor": factor,
                    "beta": params[factor],
                    "t_stat": tvals[factor],
                    "p_value": pvals[factor],
                    "stars": stars,
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Decomposed R² (DR²)
# ---------------------------------------------------------------------------

def calculate_decomposed_r2(
    result,
    factor_stds: pd.Series,
    asset_std: float,
) -> pd.Series:
    """
    Compute Decomposed R² for each factor.

    DR²_k = (β̂⊥_k * σ̂_{fk} / σ̂_j)²

    where β̂⊥_k is the OLS coefficient on factor k (from the orthogonalized
    regression), σ̂_{fk} is the standard deviation of factor k, and σ̂_j is
    the standard deviation of the asset's returns.

    Parameters
    ----------
    result : RegressionResultsWrapper
        OLS result from an orthogonalized regression.
    factor_stds : pd.Series
        Standard deviations of each factor (indexed by factor name).
    asset_std : float
        Standard deviation of the asset's returns.

    Returns
    -------
    pd.Series
        DR²_k for each factor.
    """
    betas = result.params.drop("const", errors="ignore")
    # Align
    common = betas.index.intersection(factor_stds.index)
    betas = betas[common]
    fstds = factor_stds[common]

    dr2 = (betas * fstds / asset_std) ** 2
    return dr2


def validate_decomposition(
    dr2: pd.Series,
    r2: float,
    tol: float = 1e-4,
) -> dict:
    """
    Validate that DR² values sum to R² and that Σ DR²_k + (1-R²) = 1.

    Returns
    -------
    dict with keys: 'sum_dr2', 'r2', 'error', 'passes', 'total_check'
    """
    sum_dr2 = dr2.sum()
    error = abs(sum_dr2 - r2)
    total = sum_dr2 + (1.0 - r2)
    return {
        "sum_dr2": sum_dr2,
        "r2": r2,
        "error_vs_r2": error,
        "passes": error < tol,
        "total": total,
        "total_check": abs(total - 1.0) < tol,
    }


def decompose_all(
    results: dict,
    factors_dict: dict,
    asset_returns: pd.DataFrame,
) -> dict:
    """
    Compute DR² for all assets and orthogonalization methods.

    Parameters
    ----------
    results : dict
        Nested dict {ticker: {method: RegressionResultsWrapper}}.
    factors_dict : dict
        {'original': df, 'swl': df, 'pca': df, 'gs': df}
    asset_returns : pd.DataFrame

    Returns
    -------
    dict: {ticker: {method: pd.Series of DR²_k}}
    """
    ortho_methods = [m for m in factors_dict if m != "original"]
    decomposition = {}

    for ticker in asset_returns.columns:
        decomposition[ticker] = {}
        asset_std = asset_returns[ticker].std(ddof=1)
        for method in ortho_methods:
            factors = factors_dict[method]
            factor_stds = factors.std(ddof=1)
            res = results[ticker][method]
            dr2 = calculate_decomposed_r2(res, factor_stds, asset_std)
            decomposition[ticker][method] = dr2

    return decomposition


# ---------------------------------------------------------------------------
# Rolling window analysis
# ---------------------------------------------------------------------------

def rolling_window_regression(
    asset_returns: pd.DataFrame,
    factors: pd.DataFrame,
    window_days: int = 252,
    orthogonalize=None,
) -> pd.DataFrame:
    """
    Compute rolling OLS and Decomposed R² for each asset.

    For each window ending at date t, regress each asset's returns on the
    factors of the window, orthogonalized inside the window, and compute DR²_k.
    Factors orthogonalized over the full sample are correlated again inside a
    window, and then the DR²_k no longer add up to R².

    Parameters
    ----------
    asset_returns : pd.DataFrame
        T × N asset returns.
    factors : pd.DataFrame
        T × K original factor returns.
    window_days : int
        Rolling window size in trading days.
    orthogonalize : callable, optional
        Function applied to the factors of each window, such as
        orthogonalize_swl. If None, the factors are used as given.

    Returns
    -------
    pd.DataFrame
        MultiIndex columns: (ticker, factor_name)
        Index: dates (starting from window_days-th observation onward)
        Values: DR²_k (contribution of each factor to total R²)
    """
    # Align
    common = asset_returns.index.intersection(factors.index)
    Y = asset_returns.loc[common]
    F = factors.loc[common]

    T = len(common)
    tickers = Y.columns.tolist()
    factor_cols = F.columns.tolist()

    # Results storage: date → {(ticker, factor): dr2_value}
    records = {}

    for end_idx in range(window_days, T + 1):
        start_idx = end_idx - window_days
        window_dates = common[start_idx:end_idx]
        y_win = Y.iloc[start_idx:end_idx]
        f_win = F.iloc[start_idx:end_idx]
        if orthogonalize is not None:
            f_win = orthogonalize(f_win)  # uncorrelated inside the window
        date_label = common[end_idx - 1]

        row = {}
        for ticker in tickers:
            asset_std = y_win[ticker].std(ddof=1)
            try:
                res = run_ols(y_win[ticker], f_win)
                factor_stds = f_win.std(ddof=1)
                dr2 = calculate_decomposed_r2(res, factor_stds, asset_std)
                r2 = res.rsquared
                for fc in factor_cols:
                    row[(ticker, fc)] = dr2.get(fc, np.nan)
                row[(ticker, "R2")] = r2
                row[(ticker, "idiosyncratic")] = 1.0 - r2
            except Exception:
                for fc in factor_cols + ["R2", "idiosyncratic"]:
                    row[(ticker, fc)] = np.nan

        records[date_label] = row

    df = pd.DataFrame(records).T
    df.index.name = "Date"
    df.columns = pd.MultiIndex.from_tuples(df.columns, names=["ticker", "component"])
    return df


# ---------------------------------------------------------------------------
# Decomposition on the regression sample
# ---------------------------------------------------------------------------

def align(asset_returns: pd.Series, factors: pd.DataFrame) -> tuple:
    """Dates shared by one asset and the factors, without missing values."""
    data = pd.concat([asset_returns.rename("__asset__"), factors], axis=1, join="inner").dropna()
    return data["__asset__"].rename(asset_returns.name), data[factors.columns]


def decompose(
    asset_returns: pd.Series,
    factors: pd.DataFrame,
    orthogonalize=orthogonalize_swl,
    hac_lags: int = None,
) -> tuple:
    """
    Regress one asset on the orthogonalized factors and decompose its R² (eq. 17).

    The factors are orthogonalized on the dates the asset and the factors
    share, so they are uncorrelated on exactly the sample of the regression
    and the DR²_k add up to R².

    Parameters
    ----------
    asset_returns : pd.Series
        Excess returns of one asset.
    factors : pd.DataFrame
        T × K original factor returns.
    orthogonalize : callable
        orthogonalize_swl by default, or another function of the same kind.
    hac_lags : int, optional
        Newey-West lags of the standard errors; None for the OLS ones.

    Returns
    -------
    (RegressionResultsWrapper, pd.Series)
        The regression on the orthogonalized factors, and DR²_k.
    """
    y, F = align(asset_returns, factors)
    F_ortho = orthogonalize(F)
    res = run_ols(y, F_ortho, hac_lags)
    dr2 = calculate_decomposed_r2(res, F_ortho.std(ddof=1), y.std(ddof=1))
    return res, dr2


def variance_levels(asset_returns: pd.Series, factors: pd.DataFrame) -> pd.DataFrame:
    """
    Systematic variance of one asset by factor (Table 5).

    With the SW/L factors the terms (β⊥_k σ_k)² add up to the systematic
    variance, the total minus the idiosyncratic variance. With the original
    factors the terms (β_k σ_k)² leave out the covariances, so their sum does
    not.

    Returns
    -------
    pd.DataFrame
        Rows: one per factor, then 'sum', 'systematic', 'idiosyncratic' and
        'total'. Columns: 'original' and 'orthogonal'.
    """
    y, F = align(asset_returns, factors)
    F_ortho = orthogonalize_swl(F)
    res = run_ols(y, F)
    res_ortho = run_ols(y, F_ortho)
    table = pd.DataFrame({
        "original": (res.params.drop("const") * F.std(ddof=1)) ** 2,
        "orthogonal": (res_ortho.params.drop("const") * F_ortho.std(ddof=1)) ** 2,
    })
    table.loc["sum"] = table.sum()
    table.loc["systematic"] = y.var(ddof=1) - res.resid.var(ddof=1)
    table.loc["idiosyncratic"] = res.resid.var(ddof=1)
    table.loc["total"] = y.var(ddof=1)
    return table


def gs_order_range(asset_returns: pd.Series, factors: pd.DataFrame) -> pd.DataFrame:
    """
    DR²_k of one asset under every Gram-Schmidt order of the factors.

    Returns
    -------
    pd.DataFrame
        One row per order (K! rows), indexed by the order, with the DR²_k.
    """
    y, F = align(asset_returns, factors)
    rows = {}
    for order in permutations(F.columns):
        F_gs = orthogonalize_gs(F, list(order))
        # With uncorrelated factors, DR²_k is the squared correlation with factor k
        rows[" > ".join(order)] = F_gs.corrwith(y) ** 2
    return pd.DataFrame(rows).T
