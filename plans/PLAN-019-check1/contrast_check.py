"""PLAN-019 check 1: does u_{s,k} drop out of the task:coverage interaction?

ADR-066 decision 4 (d) rests on one claim: the random term
`(0 + coverage | seed)` gives each FT run three values u_{s,k} that do NOT
depend on the task type, so the interaction contrast (which differences task
types WITHIN a coverage level) cannot see them.  The ADR's own risk column
says this is exact for a balanced linear model and only a first-order
argument under the logit link, and that it must be checked before the claim
is written into `Documents/05_STATISTICS.md`.

答える問い: `Documents/05_STATISTICS.md` §3.2 の ★G の根拠欄は
「外れた仮定は被覆の主効果の勾配であって task:coverage ではない」と書いてよいか。

Two parts:

  [A] Algebra.  Project out intercept + task main effect + coverage main
      effect from the 12 cell means; what is left is the interaction space
      (rank 6).  Multiply it by the loading matrix of u_{s,k}.  If every
      interaction contrast is orthogonal to that loading, the cancellation is
      exact ON THE LINEAR PREDICTOR, for any link function.

  [B] Monte Carlo.  The algebra says nothing about the SAMPLING VARIANCE of
      an estimator, because under a non-identity link the per-cell
      information depends on u.  So estimate the same difference-in-
      differences twice per draw -- once through empirical cell logits, once
      through an identity-link balanced analogue -- and sweep sigma_u.

This is NOT pipeline code and NOT a pytest target (same footing as the
PLAN-016 checks).  No real data is read; no GPU is used.
Output is ASCII only: this environment's stdout is cp932.
"""

import numpy as np

N_TASK = 4          # T1 / T1b / T2 / T3   (ADR-026)
N_COV = 3           # id / interp / extrap_magnitude   (ADR-027)
N_SEED = 10         # 主軸の seed 水準数 (ADR-028)
N_CELL = N_TASK * N_COV

N_ITEM = 100        # items per (seed, task, coverage) cell
N_REP = 4000        # Monte Carlo draws per sigma_u
SIGMA_U_SWEEP = (0.0, 0.25, 0.5, 1.0)
RNG_SEED = 20260908

# Fixed effects on the logit scale.  The base cell is deliberately near the
# ceiling because Go/No-Go #4 pushes it there by design (05_STATISTICS.md §2).
BASE_LOGIT = 2.0
TASK_MAIN = np.array([0.0, -0.3, -0.6, -0.2])
COV_MAIN = np.array([0.0, -1.0, -2.0])
GAMMA_TRUE = 0.0    # H_null: no interaction, so the contrast's target is 0
HALDANE = 0.5       # empirical-logit correction; keeps the contrast finite


def loading_matrix() -> np.ndarray:
    """u_{s,k} がセルに載る係数。答える問い: この負荷は task に依存するか。

    L[(t, k), k'] = 1 iff k == k'.  The row index runs over the 12 cells but
    the value never looks at t -- that is the whole content of decision 4 (d).
    """
    loading = np.zeros((N_CELL, N_COV))
    for task in range(N_TASK):
        for cov in range(N_COV):
            loading[task * N_COV + cov, cov] = 1.0
    return loading


def interaction_projector() -> np.ndarray:
    """交互作用の対比が張る空間への射影(セル水準、df = 6)。"""
    columns = [np.ones(N_CELL)]
    for task in range(1, N_TASK):
        col = np.zeros(N_CELL)
        col[task * N_COV:(task + 1) * N_COV] = 1.0
        columns.append(col)
    for cov in range(1, N_COV):
        col = np.zeros(N_CELL)
        col[cov::N_COV] = 1.0
        columns.append(col)
    additive = np.column_stack(columns)
    return np.eye(N_CELL) - additive @ np.linalg.pinv(additive)


def coverage_main_contrast() -> np.ndarray:
    """対照: 被覆の主効果の対比。これは u_{s,k} を拾うはずである。"""
    contrast = np.zeros(N_CELL)
    contrast[0::N_COV] = 1.0 / N_TASK
    contrast[1::N_COV] = -1.0 / N_TASK
    return contrast


def did(cells: np.ndarray) -> float:
    """(T1 - T1b) x (id - interp) の差分の差。cells[seed, task, coverage]。

    seed ごとに作ってから平均する。u_{s,k} は seed 内・被覆内で共通なので、
    もし消えるならこの引き算の時点で消える。
    """
    per_seed = ((cells[:, 0, 0] - cells[:, 1, 0])
                - (cells[:, 0, 1] - cells[:, 1, 1]))
    return float(per_seed.mean())


def linear_predictor(u: np.ndarray) -> np.ndarray:
    """eta[seed, task, coverage]。u は (seed, coverage) で task に依存しない。"""
    return (BASE_LOGIT
            + TASK_MAIN[None, :, None]
            + COV_MAIN[None, None, :]
            + u[:, None, :]
            + GAMMA_TRUE)


def sweep_sigma_u(sigma_u: float, rng: np.random.Generator) -> tuple[float, float, float, float]:
    """一つの sigma_u で差分の差を N_REP 回作る。返り値は logit と linear の平均と SD。"""
    logit_est = np.empty(N_REP)
    linear_est = np.empty(N_REP)
    for rep in range(N_REP):
        u = rng.normal(0.0, sigma_u, size=(N_SEED, N_COV))
        eta = linear_predictor(u)
        successes = rng.binomial(N_ITEM, 1.0 / (1.0 + np.exp(-eta)))
        prop = (successes + HALDANE) / (N_ITEM + 2.0 * HALDANE)
        logit_est[rep] = did(np.log(prop / (1.0 - prop)))
        # Identity-link balanced analogue driven by the SAME structure.  Its
        # per-cell noise does not depend on u, which is exactly the property
        # the logit link loses.
        noise = rng.normal(0.0, 1.0, size=eta.shape) / np.sqrt(N_ITEM)
        linear_est[rep] = did(eta + noise)
    return (float(logit_est.mean()), float(logit_est.std()),
            float(linear_est.mean()), float(linear_est.std()))


def main() -> None:
    loading = loading_matrix()
    projector = interaction_projector()
    rank = int(np.linalg.matrix_rank(projector))
    worst = float(np.abs(projector @ loading).max())
    print("[A] algebra on the cell-mean design (%d cells, %d seeds)" % (N_CELL, N_SEED))
    print("    rank of the interaction space      = %d   (expected 6)" % rank)
    print("    max |c' L| over that whole space   = %.3e   (expected 0)" % worst)
    print("    control: coverage main effect c'L  = %s   (not zero)"
          % np.array2string(coverage_main_contrast() @ loading, precision=3))

    rng = np.random.default_rng(RNG_SEED)
    print("")
    print("[B] difference-in-differences, %d draws per row, true value 0" % N_REP)
    print("    %-8s | %12s %10s | %12s %10s"
          % ("sigma_u", "logit mean", "logit SD", "linear mean", "linear SD"))
    for sigma_u in SIGMA_U_SWEEP:
        lg_mean, lg_sd, ln_mean, ln_sd = sweep_sigma_u(sigma_u, rng)
        print("    %-8.2f | %12.5f %10.5f | %12.5f %10.5f"
              % (sigma_u, lg_mean, lg_sd, ln_mean, ln_sd))


if __name__ == "__main__":
    main()
