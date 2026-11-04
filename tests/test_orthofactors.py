"""Checks the properties of the orthogonalization and the decomposition in Klein and Chow (2013)."""
from math import factorial

import numpy as np
import pandas as pd
import pytest

from orthofactors.decomposition import (decompose, gs_order_range, rolling_window_regression, run_ols,
                                        variance_levels)
from orthofactors.orthogonalization import (orthogonalize_gs, orthogonalize_pca, orthogonalize_swl,
                                            orthogonalize_swl_correlation)


@pytest.fixture
def data():
    # Correlated factors and an asset built like the Monte Carlo of the paper (eq. 16)
    rng = np.random.default_rng(2013)
    T, K = 400, 5
    A = rng.normal(size=(K, K))
    cov = (A @ A.T / K + 0.2 * np.eye(K)) * 1e-3
    index = pd.date_range("1990-01-31", periods=T, freq="ME")
    F = pd.DataFrame(rng.multivariate_normal(np.linspace(0.002, 0.01, K), cov, size=T),
                     index=index, columns=[f"f{k + 1}" for k in range(K)])
    y = pd.Series(0.002 + F.values @ np.array([1.2, 0.1, 0.3, -0.2, 0.7]) + rng.normal(scale=0.02, size=T),
                  index=index, name="asset")
    return F, y


def test_swl_factors_are_uncorrelated_and_keep_their_variances(data):
    F, _ = data
    F_ortho = orthogonalize_swl(F)
    np.testing.assert_allclose(F_ortho.corr().values, np.eye(F.shape[1]), atol=1e-10)
    np.testing.assert_allclose(F_ortho.std().values, F.std().values, rtol=1e-10)


def test_swl_means_are_the_original_means_times_s(data):
    F, _ = data
    F_ortho, S, _ = orthogonalize_swl(F, return_matrices=True)
    np.testing.assert_allclose(F_ortho.mean().values, F.mean().values @ S.values, rtol=1e-10)


def test_swl_keeps_alpha_residuals_and_r2_and_maps_the_betas_with_psi(data):
    F, y = data
    F_ortho, _, Psi = orthogonalize_swl(F, return_matrices=True)
    res, res_ortho = run_ols(y, F), run_ols(y, F_ortho)
    assert res_ortho.params["const"] == pytest.approx(res.params["const"], rel=1e-9)
    np.testing.assert_allclose(res_ortho.resid.values, res.resid.values, atol=1e-12)
    assert res_ortho.rsquared == pytest.approx(res.rsquared, rel=1e-12)
    np.testing.assert_allclose(res_ortho.params[F.columns].values, Psi.values @ res.params[F.columns].values,
                               rtol=1e-9)


def test_resemblance_is_the_diagonal_of_psi(data):
    F, _ = data
    F_ortho, _, Psi = orthogonalize_swl(F, return_matrices=True)
    np.testing.assert_allclose(np.diag(Psi), [F[c].corr(F_ortho[c]) for c in F.columns], rtol=1e-10)


def test_decomposed_r2_adds_up_to_r2_with_missing_values(data):
    F, y = data
    y = y.copy()
    y.iloc[::7] = np.nan
    for orthogonalize in [orthogonalize_swl, orthogonalize_swl_correlation, orthogonalize_pca]:
        res, dr2 = decompose(y, F, orthogonalize, hac_lags=4)
        assert dr2.sum() == pytest.approx(res.rsquared, abs=1e-12)


def test_swl_and_pca_do_not_depend_on_the_order_of_the_factors(data):
    F, _ = data
    reverse = F.columns[::-1]
    for orthogonalize in [orthogonalize_swl, orthogonalize_pca]:
        np.testing.assert_allclose(orthogonalize(F[reverse])[F.columns].values, orthogonalize(F).values,
                                   atol=1e-12)


def test_gram_schmidt_depends_on_the_order_of_the_factors(data):
    F, y = data
    first = decompose(y, F, lambda f: orthogonalize_gs(f, list(f.columns)))[1]
    last = decompose(y, F, lambda f: orthogonalize_gs(f, list(f.columns[::-1])))[1]
    assert first.sum() == pytest.approx(last.sum(), abs=1e-12)
    assert np.abs(first - last).max() > 0.01


def test_gs_order_range_covers_every_order(data):
    F, y = data
    orders = gs_order_range(y, F)
    assert len(orders) == factorial(F.shape[1])
    np.testing.assert_allclose(orders.sum(axis=1).values, run_ols(y, F).rsquared, atol=1e-12)


def test_rolling_decomposed_r2_adds_up_to_r2_in_each_window(data):
    F, y = data
    rolling = rolling_window_regression(y.to_frame(), F, window_days=60, orthogonalize=orthogonalize_swl)["asset"]
    np.testing.assert_allclose(rolling[F.columns].sum(axis=1).values, rolling["R2"].values, atol=1e-12)


def test_only_the_correlation_variant_ignores_the_scale_of_one_factor(data):
    F, y = data
    scaled = F.assign(f3=3 * F["f3"])
    correlation = decompose(y, F, orthogonalize_swl_correlation)[1]
    np.testing.assert_allclose(decompose(y, scaled, orthogonalize_swl_correlation)[1].values,
                               correlation.values, atol=1e-12)
    covariance = decompose(y, F)[1]
    assert np.abs(decompose(y, scaled)[1] - covariance).max() > 1e-3


def test_variance_levels(data):
    F, y = data
    table = variance_levels(y, F)
    assert table.loc["sum", "orthogonal"] == pytest.approx(table.loc["systematic", "orthogonal"], rel=1e-10)
    assert table.loc["sum", "original"] != pytest.approx(table.loc["systematic", "original"], rel=1e-3)
    assert (table.loc["systematic"] + table.loc["idiosyncratic"]).values == pytest.approx(
        table.loc["total"].values, rel=1e-10)


def test_monthly_returns_keep_missing_months_missing():
    from orthofactors.data import to_monthly
    days = pd.bdate_range("2020-01-01", "2020-03-31")
    daily = pd.DataFrame({"a": 0.01, "b": np.nan}, index=days)
    daily.loc["2020-02", "b"] = 0.01
    monthly = to_monthly(daily)
    assert monthly["b"].isna().tolist() == [True, False, True]
    assert monthly.loc["2020-01", "a"].iloc[0] == pytest.approx(1.01 ** len(days[days.month == 1]) - 1)
