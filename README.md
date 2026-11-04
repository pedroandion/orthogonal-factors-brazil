# Orthogonal Factors in Brazil

Decomposition of the systematic risk of Brazilian equity portfolios into seven local factors, with the orthogonalization of Klein and Chow (2013), from January 2010 to July 2026.

Equity factors are correlated, so the systematic variance of a portfolio has cross terms and cannot be split by factor. Klein and Chow transform the factors into uncorrelated versions that stay as close as possible to the originals, and then the variance splits exactly into one share per factor. This repository first replicates the paper with US data, then applies the method to the seven local factors, the multi-factor strategy and the 32 screening factors of the companion repository, [brazil-equity-factors](https://github.com/pedroandion/brazil-equity-factors), and to each stock of its universe.

**Paper:** Klein, R. F. and Chow, V. K. (2013), *Orthogonalized factors and systematic risk decomposition*, The Quarterly Review of Economics and Finance 53, 175–187, [doi:10.1016/j.qref.2013.02.003](https://doi.org/10.1016/j.qref.2013.02.003).

![Share of the variance of the multi-factor strategy explained by each orthogonal factor, in 252-day windows](docs/combination_rolling_decomposition.png)

## Results

All results are before transaction costs.

### Replication of the paper (`01_paper_replication.ipynb`)

The replication uses the same factors (market, size, value, momentum and long-term reversal), sample (1931 to 2008) and portfolios as the paper, with the current Ken French data.

- **Decomposition.** The decomposed R² of the 36 style portfolios of Table 6 is within 1.4 points of the published values in every cell, and within 0.5 point on average. The averages are the paper's: for small caps, 53% of the variance comes from the market and 24% from size; for large caps, 78% from the market.
- **Resemblance.** The orthogonal factors keep correlations of 0.91 to 0.97 with the originals, as in the paper. In the pairwise comparison of Table 1 the lowest correlation is 0.938 for SW/L, against 0.434 for PCA and 0.764 for Gram-Schmidt (0.945, 0.450 and 0.787 in the paper).
- **Differences.** The library has revised its data since 2012. The largest gap is the value-weighted Coal industry; without it, every component of the 30 industries is within 3 points of the paper.

### The local factors and BAB (`02_brazil_factors.ipynb`)

- **BAB.** The companion's BAB is long the 30% lowest-beta stocks and short the 30% highest-beta ones, one real each. Since the two legs have betas of 0.60 and 1.45 on the market, that factor has a market beta of −0.86, and the market explains 57% of its variance. This repository scales each leg by the inverse of its ex-ante beta, as Frazzini and Pedersen (2014) do, which cuts the market beta to −0.37 and the R² to 21%.
- **Multicollinearity.** With the companion's BAB, BAB had the largest variance inflation factor of the seven factors, 4.1, which led an earlier six-factor model to drop it. With the beta-neutral BAB it falls to 1.8. The most connected factor is now value, with correlations of −0.69 with momentum and −0.62 with BAB.
- **Resemblance.** The orthogonal factors keep correlations of 0.81 (HML) to 0.95 (the market) with the originals, lower than in the US because the Brazilian factors overlap more.

### The multi-factor strategy (`03_strategy_decomposition.ipynb`)

The Combination holds up to 40 stocks: 20 from the Magic Formula and 10 each from LowVol Momentum and Quality. Share of the monthly variance of the returns in excess of the SELIC rate explained by each orthogonal factor, February 2010 to June 2026:

| Strategy | Market | SMB | HML | RMW | CMA | WML | BAB | Idiosyncratic |
|---|---|---|---|---|---|---|---|---|
| **Combination** | **70.0%** | **12.9%** | **0.3%** | **1.8%** | **0.2%** | **0.3%** | **0.6%** | **13.9%** |
| Magic Formula | 63.1% | 14.2% | 0.0% | 1.6% | 0.5% | 0.8% | 1.1% | 18.7% |
| LowVol Momentum | 63.0% | 6.6% | 0.3% | 1.2% | 0.0% | 4.6% | 1.7% | 22.6% |
| Quality | 56.2% | 10.2% | 2.3% | 1.7% | 0.0% | 2.2% | 0.1% | 27.3% |

- **Sources.** The market explains most of the variance of every strategy, and size comes second. The other five factors together explain 3% to 8%, with momentum the largest of them for LowVol Momentum.
- **Why orthogonalize.** Adding up the factor terms without the transformation overstates the systematic variance of the Combination by 27%, because the strategies have positive betas on factors that move against each other, such as the market and BAB. Gram-Schmidt, the usual alternative, depends on the order of the factors: across the 5,040 orders, the market explains anywhere from 47% to 75% of the Combination, and size from 2% to 25%.
- **BAB construction.** With the dollar-neutral BAB of the companion, BAB seemed to be the third source of risk, with up to 10% of the variance of Quality. Most of that was market risk: with the beta-neutral BAB, its share is at most 1.7%, and the market's is 5 to 8 points higher.
- **Alpha.** The alpha is the same with the original and the orthogonal factors: 0.23% a month for the Combination, with a Newey-West t-statistic of 1.5.

### Over time (`04_time_varying.ipynb`)

- In 60-month windows, the market explains 61% to 78% of the variance of the Combination. The second source moved from BAB, with 10% in 2010–2015, to size, with 16% in 2021–2026.
- In 252-day windows, size explained 21% in 2024, when the share of the market fell to 57%. The lowest idiosyncratic share, 3.5%, is in the window that ends during the COVID-19 crash.

### The screening factors (`05_screening_factors.ipynb`)

- The seven factors explain 96% of the companion's dollar-neutral BAB, but 29% of it goes to the orthogonal market: that is the market exposure of the construction. Low volatility splits among size, BAB and the market, and investment (CMA) explains 42% of accruals.
- The leverage factors are the least explained group: 79% of their variance is idiosyncratic. Low debt to assets has the largest alpha on the seven factors, 7.5% a year with a t-statistic of 3.3, and it is the only one of 30 alphas that passes a Bonferroni correction at 5%.

### The stocks (`06_stock_cross_section.ipynb`)

- For the average stock, the seven factors explain about a third of the daily variance: 24% from the market, 4% from size, 3% from momentum and 2% from BAB, with 63% idiosyncratic. In 2020 the share of the market rose to 50%.
- The large banks are the most explained stocks, and exporters such as Suzano, Minerva, SLC Agrícola and Embraer the least, with 77% to 85% of their variance idiosyncratic.

## Method

- **Transformation.** With $\Sigma$ the sample covariance matrix of the factors and $\sigma$ their standard deviations, the orthogonal factors are $F^\perp = F S$ with $S = \Sigma^{-1/2}\,\mathrm{diag}(\sigma)$. They are uncorrelated, keep the variances of the original factors and do not depend on the order of the factors. The betas become $\beta^\perp = \Psi\beta$ with $\Psi = S^{-1}$, and the intercept, the residuals and the R² do not change.
- **Decomposition.** The share of factor $k$ in the variance of asset $j$ is $DR^2_{j,k} = (\beta^\perp_{k,j}\,\sigma_k / \sigma_j)^2$, and the shares add up to the R².
- **Samples.** The factors are orthogonalized on exactly the observations of each regression: the full sample, each rolling window and each stock-year. So the shares always add up to the R².
- **Brazilian factors.** Six of the seven factors and the strategies come from the companion repository as they are. BAB uses the companion's two legs, the 30% lowest-beta and the 30% highest-beta stocks by the shrunk Frazzini-Pedersen beta, each scaled by the inverse of its average beta when it is formed: $BAB = (r_L - r_f)/\beta_L - (r_H - r_f)/\beta_H$.
- **Returns.** Returns are in excess of the SELIC rate, the risk-free rate of the market factor. Monthly returns compound the daily ones, as the companion does. The daily sample starts on 2010-01-05, when BAB starts, and the monthly sample runs from February 2010 to June 2026.
- **Standard errors.** Newey-West, with 4 lags in monthly data and 5 in daily data. The replication uses OLS errors, as the paper does.

## Notebooks

| Notebook | What it does | Run time |
|---|---|---|
| `01_paper_replication` | Tables 1, 3, 4, 5, 6 and 7 and Figure 1 of the paper, next to the published values | 13 s |
| `02_brazil_factors` | The two versions of BAB, how the seven local factors overlap, and what the orthogonal factors are made of | 9 s |
| `03_strategy_decomposition` | Betas, alpha and variance decomposition of the multi-factor strategy and its sleeves | 46 s |
| `04_time_varying` | The decomposition in 60-month and 252-day windows | 44 s |
| `05_screening_factors` | The 32 screening factors of the companion as test assets | 10 s |
| `06_stock_cross_section` | Each stock of the investable universe, year by year | 15 s |

The functions are in the `orthofactors` package: the transformation in `orthogonalization.py`, the regressions and decompositions in `decomposition.py`, the loaders in `data.py` and the chart settings in `plotting.py`. The tests in `tests/` check the properties shown in the paper on simulated data.

## Limitations

- **Data vintage.** The Ken French files were built from the CRSP database of September 2026, and the library has revised its data since the paper, so the replication is close but not exact.
- **Scale.** SW/L works on the covariance matrix, so rescaling a single factor changes the result. The correlation version, which does not, moves the shares of the strategies by at most 1.5 points.
- **Premia.** Each orthogonal factor mixes several original factors, so its mean return mixes their premia. The decomposition is of variance, not of returns.
- **Local factors.** They come from single sorts with equal weights, and RMW uses gross profit over assets. BAB is beta-neutral only ex ante: ex post its beta on the market is −0.37, because the shrunk betas understate the spread between its legs. Results with other factor definitions may differ.
- **Backtests.** The strategies are in-sample and before costs, as in the companion repository.
- **Daily returns of small stocks.** Stocks that trade less often move with the factors with a lag, which inflates their idiosyncratic share in daily data.
- **Multiple tests.** The 30 screening alphas are not adjusted for the number of tests, except where noted. Size and Momentum in the screening are the same series as SMB and WML and are left out of those tests.
- **Not replicated.** The Monte Carlo of Table 2 and the GMM tests of Table 8 of the paper.

## Data

| Location | Content | Source |
|---|---|---|
| `data/brazil_factors.csv.gz` | Daily returns of the seven local factors, with the companion's BAB, and the SELIC rate | brazil-equity-factors, `03_historical_betas` |
| `data/brazil_bab_legs.csv.gz` | Daily returns of the two legs of BAB and their ex-ante betas | brazil-equity-factors, `03_historical_betas` |
| `data/brazil_strategies.csv.gz` | Daily returns of the multi-factor strategy and its sleeves | brazil-equity-factors, `05_multi_factor_strategy` |
| `data/brazil_screening_factors.csv.gz` | Daily long-short returns of the 32 screening factors | brazil-equity-factors, `04_factor_screening` |
| `data/brazil_stock_returns.csv.gz` | Daily returns of each stock on the days it is in the investable universe | brazil-equity-factors, `03_historical_betas` |
| `data/brazil_stock_weights.csv.gz` | Relative market value of each stock on the first trading day of each year | brazil-equity-factors |
| `data/external/` | Factors and portfolios of the paper, downloaded by `01_` and not versioned | [Ken French data library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) |

The companion repository builds the strategy and screening returns and the legs of BAB in memory only. `scripts/export_companion_data.py` runs its notebooks up to the cells that build them and saves them here, without changing the companion. `data/manifest.json` records the companion commit used, 2e92006. The prices behind these series come from [Comdinheiro](https://www.comdinheiro.com.br/) through the companion; no raw financial statements or market values in R$ are in this repository.

## Running the notebooks

The notebooks were run with Python 3.13.

```bash
git clone https://github.com/pedroandion/orthogonal-factors-brazil.git
cd orthogonal-factors-brazil
python -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests
python -m nbconvert --to notebook --execute --inplace 03_strategy_decomposition.ipynb
```

The notebooks read only the files in this repository, except `01_`, which downloads the Ken French data. The workflow in `.github/workflows/run-notebooks.yml` runs the tests and the six notebooks on a clean Linux machine. To rebuild the Brazilian data, clone the companion next to this repository, install its requirements and run `python scripts/export_companion_data.py ../brazil-equity-factors`.

## License

The code is under the [MIT License](LICENSE). The data files are not covered by it: they are included only so that the results can be reproduced, and they remain subject to the terms of their sources.

## Author

Pedro Andion de Oliveira Freitas
