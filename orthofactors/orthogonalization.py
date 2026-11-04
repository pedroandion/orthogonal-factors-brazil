"""
orthogonalization.py — SW/L, PCA, and Gram-Schmidt orthogonalization
of the Fama-French 5-factor set, following Klein & Chow (2013).
"""

import numpy as np
import pandas as pd
from numpy.linalg import eigh


# ---------------------------------------------------------------------------
# SW/L — Schweinler-Wigner / Löwdin symmetric orthogonalization
# ---------------------------------------------------------------------------

def orthogonalize_swl(F: pd.DataFrame) -> pd.DataFrame:
    """
    Symmetric (Löwdin / Schweinler-Wigner) orthogonalization.

    Steps (from Klein & Chow 2013, Section 2):
      1. Demean factors:  F̃ = F - mean(F)
      2. Compute second-moment matrix: M = (T-1) * Cov(F)  [= F̃.T @ F̃]
      3. Eigendecompose: M = O D O^T
      4. Symmetric whitening matrix: S = O D^{-1/2} O^T
      5. Orthogonalized demeaned factors: F̃⊥ = F̃ @ S
      6. Rescale S so each F⊥_k has the same std as F_k (eq. 11)
      7. Orthogonalized factors: F⊥ = F @ S (eq. 12), so the means become mean(F) @ S

    Parameters
    ----------
    F : pd.DataFrame
        T × K matrix of factor returns.

    Returns
    -------
    pd.DataFrame
        T × K orthogonalized factors with the original standard deviations.
        Their means are mean(F) @ S, which keeps the intercept of a regression
        on F unchanged (Appendix A).
    """
    cols = F.columns.tolist()
    F_arr = F.values.copy().astype(float)
    T, K = F_arr.shape

    # Step 1: demean
    mu = F_arr.mean(axis=0)
    F_tilde = F_arr - mu

    # Step 2: second-moment matrix M = F̃.T @ F̃  (= (T-1)*Cov)
    M = F_tilde.T @ F_tilde  # shape (K, K)

    # Step 3: eigen-decomposition (eigh for symmetric matrices)
    eigenvalues, O = eigh(M)  # eigenvalues ascending order

    # Step 4: symmetric whitening  S = O D^{-1/2} O^T
    D_inv_sqrt = np.diag(1.0 / np.sqrt(eigenvalues))
    S = O @ D_inv_sqrt @ O.T  # shape (K, K)

    # Step 5: orthogonalized demeaned factors
    F_tilde_ortho = F_tilde @ S  # shape (T, K)

    # Step 6: rescale S so var(F⊥_k) == var(F_k)  (eq. 11)
    orig_stds = F_arr.std(axis=0, ddof=1)
    ortho_stds = F_tilde_ortho.std(axis=0, ddof=1)
    S = S * (orig_stds / ortho_stds)

    # Step 7: F⊥ = F @ S  (eq. 12), so the means become mean(F) @ S
    F_ortho = F_arr @ S

    return pd.DataFrame(F_ortho, index=F.index, columns=cols)


# ---------------------------------------------------------------------------
# PCA orthogonalization
# ---------------------------------------------------------------------------

def orthogonalize_pca(F: pd.DataFrame) -> pd.DataFrame:
    """
    PCA-based orthogonalization.

    Projects factors onto their principal components, then rescales each
    PC to match the original factor's standard deviation.  The PC scores
    are ordered to maximize correspondence with the original factor order
    (each PC matched to the original factor it correlates most with).

    Parameters
    ----------
    F : pd.DataFrame

    Returns
    -------
    pd.DataFrame
        T × K orthogonalized factors.
    """
    cols = F.columns.tolist()
    F_arr = F.values.copy().astype(float)
    T, K = F_arr.shape

    # Standardize → PCA on correlation matrix equivalent
    mu = F_arr.mean(axis=0)
    F_tilde = F_arr - mu

    # SVD of demeaned factor matrix
    U, s, Vt = np.linalg.svd(F_tilde, full_matrices=False)
    # U: T×K, s: K, Vt: K×K
    # PC scores (unnormalized): U * s
    scores = U * s  # T × K, already orthogonal columns

    # Match each PC to original factor (by absolute correlation)
    orig_stds = F_arr.std(axis=0, ddof=1)
    score_stds = scores.std(axis=0, ddof=1)

    # Correlation matrix between scores and original demeaned factors
    corr = (F_tilde.T @ scores) / ((T - 1) * np.outer(orig_stds, score_stds))

    # Hungarian-style greedy matching
    used_pcs = set()
    order = []
    signs = []
    for k in range(K):
        abs_corr_k = np.abs(corr[k, :])
        # Mask already-used PCs
        for j in used_pcs:
            abs_corr_k[j] = -np.inf
        best_pc = int(np.argmax(abs_corr_k))
        used_pcs.add(best_pc)
        order.append(best_pc)
        signs.append(np.sign(corr[k, best_pc]))

    # Reorder and sign-flip PCs
    F_ortho = np.zeros_like(F_arr)
    for k, (pc_idx, sgn) in enumerate(zip(order, signs)):
        pc_col = scores[:, pc_idx] * sgn
        # Rescale to original std
        F_ortho[:, k] = pc_col * (orig_stds[k] / pc_col.std(ddof=1))

    # Restore original means
    F_ortho = F_ortho + mu

    return pd.DataFrame(F_ortho, index=F.index, columns=cols)


# ---------------------------------------------------------------------------
# Gram-Schmidt orthogonalization
# ---------------------------------------------------------------------------

def orthogonalize_gs(F: pd.DataFrame, order: list) -> pd.DataFrame:
    """
    Sequential Gram-Schmidt orthogonalization.

    The first factor of `order` is kept unchanged; each later factor is
    residualized against all the factors before it in `order`. The result
    depends on that order, which is why the paper prefers SW/L.

    After GS, each factor is rescaled to its original standard deviation
    and the original mean is restored.

    Parameters
    ----------
    F : pd.DataFrame
    order : list
        All the columns of F, in the order of the Gram-Schmidt steps.

    Returns
    -------
    pd.DataFrame
        T × K orthogonalized factors, in the original column order.
    """
    original_cols = F.columns.tolist()

    if sorted(order) != sorted(original_cols):
        raise ValueError("order must list each column of F once")
    gs_order = list(order)

    F_arr = F[gs_order].values.copy().astype(float)
    T, K = F_arr.shape
    orig_stds = F[gs_order].std(axis=0, ddof=1).values
    orig_means = F[gs_order].mean(axis=0).values

    F_tilde = F_arr - orig_means  # demean

    # Gram-Schmidt on demeaned factors
    Q = np.zeros_like(F_tilde)
    for k in range(K):
        v = F_tilde[:, k].copy()
        for j in range(k):
            proj = (Q[:, j] @ v) / (Q[:, j] @ Q[:, j]) * Q[:, j]
            v = v - proj
        Q[:, k] = v

    # Rescale each GS factor to original std
    for k in range(K):
        q_std = Q[:, k].std(ddof=1)
        Q[:, k] = Q[:, k] * (orig_stds[k] / q_std)

    # Restore means
    F_ortho = Q + orig_means

    # Return in original column order
    result = pd.DataFrame(F_ortho, index=F.index, columns=gs_order)
    result = result[original_cols]
    return result


# ---------------------------------------------------------------------------
# Validation and comparison utilities
# ---------------------------------------------------------------------------

def validate_orthogonality(F_ortho: pd.DataFrame, tol: float = 1e-6) -> dict:
    """
    Validate that the orthogonalized factors satisfy key properties.

    Checks:
    1. Off-diagonal correlations ≈ 0
    2. Variances preserved relative to original (passed via F_ortho only,
       so we check internal consistency)

    Parameters
    ----------
    F_ortho : pd.DataFrame
    tol : float

    Returns
    -------
    dict with keys:
        'max_offdiag_corr'  : float
        'is_orthogonal'     : bool
        'corr_matrix'       : pd.DataFrame
    """
    corr = F_ortho.corr()
    K = len(corr)
    off_diag = [
        abs(corr.iloc[i, j])
        for i in range(K)
        for j in range(K)
        if i != j
    ]
    max_off = max(off_diag) if off_diag else 0.0

    return {
        "max_offdiag_corr": max_off,
        "is_orthogonal": max_off < tol,
        "corr_matrix": corr,
    }


def validate_variance_preservation(
    F_orig: pd.DataFrame,
    F_ortho: pd.DataFrame,
    tol: float = 1e-4,
) -> dict:
    """
    Check that variances of orthogonalized factors match original factors.

    Returns
    -------
    dict with keys:
        'variance_ratios'       : pd.Series  (ortho / orig)
        'max_relative_error'    : float
        'variances_preserved'   : bool
    """
    var_orig = F_orig.var(ddof=1)
    var_ortho = F_ortho.var(ddof=1)[F_orig.columns]
    ratios = var_ortho / var_orig
    rel_errors = (ratios - 1.0).abs()
    max_err = rel_errors.max()

    return {
        "variance_ratios": ratios,
        "max_relative_error": max_err,
        "variances_preserved": max_err < tol,
    }


def calculate_frobenius_norm(
    F_orig: pd.DataFrame,
    F_ortho: pd.DataFrame,
) -> float:
    """
    Compute the Frobenius norm of the difference: ||F_orig - F_ortho||_F.

    Only uses the columns present in F_orig.
    """
    diff = F_orig.values - F_ortho[F_orig.columns].values
    return float(np.sqrt(np.sum(diff ** 2)))


def compare_methods(F: pd.DataFrame) -> pd.DataFrame:
    """
    Apply SW/L, PCA, and GS orthogonalization to F and return a summary
    comparison table. GS follows the column order of F.

    Returns
    -------
    pd.DataFrame
        Index = method names, columns = ['frobenius_norm', 'max_offdiag_corr',
                                         'is_orthogonal', 'variances_preserved']
    """
    methods = {
        "SW/L": orthogonalize_swl(F),
        "PCA": orthogonalize_pca(F),
        "GS": orthogonalize_gs(F, F.columns.tolist()),
    }

    rows = []
    for name, F_ortho in methods.items():
        frob = calculate_frobenius_norm(F, F_ortho)
        orth = validate_orthogonality(F_ortho)
        var_check = validate_variance_preservation(F, F_ortho)
        rows.append({
            "method": name,
            "frobenius_norm": frob,
            "max_offdiag_corr": orth["max_offdiag_corr"],
            "is_orthogonal": orth["is_orthogonal"],
            "max_variance_error": var_check["max_relative_error"],
            "variances_preserved": var_check["variances_preserved"],
        })

    return pd.DataFrame(rows).set_index("method")
