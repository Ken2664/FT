"""PLAN-019 check 2: does the SHAPE of Sigma_seed move the inverse problem?

ADR-067 (案 B) pre-registers an inverse problem: "how large may s2_seed be
before 10 seeds stop reaching power 0.8".  That needs ONE horizontal axis.
But ADR-064 decision 4 made the pre-registered seed term a 3x3 covariance
(`(0 + coverage | seed)`, 6 parameters), so ★F103-2 must first say how the 6
parameters collapse to a sweepable scalar.

答える問い: ★F103-2 の縮約の選び方は、逆問題の答え(「限界はどこか」)を動かすか。
動かさないなら縮約は書式の問題にすぎない。動かすなら人間が選ぶべき仮定である。

Check 1 (`plans/PLAN-019-check1/`) swept sigma_u with the three cell means
drawn INDEPENDENTLY -- that is one particular reduction (equal SDs,
correlation 0), not a neutral default.  It found the logit DiD SD grows
+20% from sigma_u 0 -> 1 (F99).  It never varied the correlation, so it
cannot say whether that growth comes from the common (intercept-like) part
of u or from the differential (gradient) part.  ★F103-1 案 (b) -- keep the
simulator at `(1 | seed)` -- is exactly the correlation = 1 corner, and it
was never measured.

This check sweeps compound symmetry: per-cell SD `sigma` x correlation
`rho`, with

    Sigma = sigma^2 * [(1 - rho) I + rho J]

whose square root is  sqrt(1 + 2 rho) P1 + sqrt(1 - rho) (I - P1),
P1 = J / 3.  Valid for rho in [-1/2, 1].  Two corners are named:

    rho = 1  ==  `(1 | seed)`      (all three cell means move together;
                                    F103-1 案 (b) の DGP)
    rho = 0  ==  check 1's DGP     (F103-2 案 (a): SD 等値・相関 0)

これは何ではないか:
  - パイプラインのコードではない。`code/` に置かないのは意図的である
  - `pytest code/tests` の対象ではない。一度きりの測定である
  - 実データを読まない。GPU を使わない。すべて合成データである
  - **glmer の当てはめではない。**セルごとの経験ロジットから差分の差を作っている。
    したがって「df = 6 の LRT の検出力」そのものは測っていない。
    測っているのは 1 本の対比の SD であり、検出力への写像は確立していない
  - ADR-064 / ADR-066 / ADR-067 を決め直すものではない。モデル指定は変えない

Output is ASCII only: this environment's stdout is cp932.
"""

import math

import numpy as np

N_TASK = 4          # T1 / T1b / T2 / T3   (ADR-026)
N_COV = 3           # id / interp / extrap_magnitude   (ADR-027)
N_SEED = 10         # 主軸の seed 水準数 (ADR-028)

N_ITEM = 100        # items per (seed, task, coverage) cell
N_REP = 4000        # Monte Carlo draws per (sigma, rho)
RNG_SEED = 20260909
HALDANE = 0.5       # empirical-logit correction; keeps the contrast finite

SIGMA_SWEEP = (0.0, 0.25, 0.5, 1.0, 1.5)
RHO_SWEEP = (-0.4, 0.0, 0.5, 1.0)

# Fixed effects on the logit scale.  Same shape as check 1 (base cell near
# the ceiling by design; 05_STATISTICS.md §2 / Go/No-Go #4), but the coverage
# main effect is taken from the ADOPTED effect-size profile P1's common part
# (05_STATISTICS.md §6.5: b = {id: 0, interp: -1.0, extrap: -2.2}).
BASE_LOGIT = 2.2
TASK_MAIN = np.array([0.6, 0.2, -0.4, 0.0])     # T1 / T1b / T2 / T3
COV_MAIN = np.array([0.0, -1.0, -2.2])          # id / interp / extrap_mag
GAMMA_TRUE = 0.0    # H_null: the DiD's target is 0, so its SD is the whole story


def compound_symmetry_sqrt(rho: float) -> np.ndarray:
    """交換可能な 3x3 相関行列の平方根。答える問い: rho を 1 まで含めて引けるか。

    Eigen-decomposition, not Cholesky: Cholesky fails at rho = 1, and rho = 1
    is the corner this check exists to measure (`(1 | seed)`).
    """
    projector_ones = np.full((N_COV, N_COV), 1.0 / N_COV)
    return (np.sqrt(1.0 + (N_COV - 1) * rho) * projector_ones
            + np.sqrt(1.0 - rho) * (np.eye(N_COV) - projector_ones))


def variance_split(sigma: float, rho: float) -> tuple[float, float]:
    """u を「共通成分」と「差分成分」に分けたときの SD。答える問い: sigma のどれだけが勾配か。

    共通成分 = 3 つのセル平均の平均(切片方向)。`(1 | seed)` はここだけを持つ。
    差分成分 = それと直交する 2 方向(被覆ごとの勾配のばらつき)。
    """
    return (sigma * np.sqrt((1.0 + (N_COV - 1) * rho) / N_COV),
            sigma * np.sqrt(1.0 - rho))


def linear_predictor(u: np.ndarray) -> np.ndarray:
    """eta[rep, seed, task, coverage]。u は (rep, seed, coverage) で task に依存しない。"""
    return (BASE_LOGIT
            + TASK_MAIN[None, None, :, None]
            + COV_MAIN[None, None, None, :]
            + u[:, :, None, :]
            + GAMMA_TRUE)


def did(cells: np.ndarray, cov_hi: int, cov_lo: int) -> np.ndarray:
    """(T1 - T1b) x (cov_hi - cov_lo) の差分の差。cells[rep, seed, task, coverage]。

    seed ごとに作ってから平均する。u_{s,k} は seed 内・被覆内で共通なので、
    もし消えるならこの引き算の時点で消える(検査1 の F97)。
    """
    per_seed = ((cells[:, :, 0, cov_hi] - cells[:, :, 1, cov_hi])
                - (cells[:, :, 0, cov_lo] - cells[:, :, 1, cov_lo]))
    return per_seed.mean(axis=1)


def sweep_cell(sigma: float, rho: float, rng: np.random.Generator) -> tuple[float, float, float]:
    """一つの (sigma, rho) で差分の差を N_REP 回作る。

    返り値: (id-interp の logit SD, id-extrap の logit SD, id-interp の恒等リンク SD)。
    恒等リンクは対照である —— そこが平らなら、動いた分はリンクの非線形性が原因である。
    """
    z = rng.standard_normal(size=(N_REP, N_SEED, N_COV))
    u = sigma * (z @ compound_symmetry_sqrt(rho).T)
    eta = linear_predictor(u)

    successes = rng.binomial(N_ITEM, 1.0 / (1.0 + np.exp(-eta)))
    prop = (successes + HALDANE) / (N_ITEM + 2.0 * HALDANE)
    emp_logit = np.log(prop / (1.0 - prop))

    noise = rng.standard_normal(size=eta.shape) / np.sqrt(N_ITEM)
    linear_cells = eta + noise

    return (float(did(emp_logit, 0, 1).std()),
            float(did(emp_logit, 0, 2).std()),
            float(did(linear_cells, 0, 1).std()))


def main() -> None:
    rng = np.random.default_rng(RNG_SEED)
    print("[A] compound symmetry: Sigma = sigma^2 [(1-rho) I + rho J], %d seeds, %d items/cell"
          % (N_SEED, N_ITEM))
    print("    rho = 1.0 is `(1 | seed)`  (F103-1 case (b) の DGP)")
    print("    rho = 0.0 is check 1's DGP (F103-2 case (a): SD equal, correlation 0)")
    print("    %d draws per row; the DiD's true value is 0 under H_null" % N_REP)
    print("")
    print("    %-6s %-6s | %8s %8s | %10s %10s | %10s"
          % ("sigma", "rho", "sd_com", "sd_dif",
             "logit(i-in)", "logit(i-ex)", "linear"))

    baseline: dict[str, float] = {}
    rows: list[tuple[float, float, float, float, float, float, float]] = []
    for rho in RHO_SWEEP:
        for sigma in SIGMA_SWEEP:
            sd_common, sd_diff = variance_split(sigma, rho)
            sd_interp, sd_extrap, sd_linear = sweep_cell(sigma, rho, rng)
            if sigma == 0.0:
                baseline.setdefault("interp", sd_interp)
                baseline.setdefault("extrap", sd_extrap)
            rows.append((sigma, rho, sd_common, sd_diff, sd_interp, sd_extrap, sd_linear))
            print("    %-6.2f %-6.2f | %8.3f %8.3f | %10.5f %10.5f | %10.5f"
                  % (sigma, rho, sd_common, sd_diff, sd_interp, sd_extrap, sd_linear))
        print("")

    print("[B] inflation of the logit DiD SD relative to sigma = 0")
    print("    power for a fixed effect goes as effect / SD, so a factor here is")
    print("    the whole channel by which s2_seed can move the inverse problem.")
    print("    NOTE: this is ONE contrast's SD, not the df = 6 LRT's power.")
    print("")
    for label, column, key in (("id - interp", 4, "interp"),
                               ("id - extrap_magnitude", 5, "extrap")):
        print("    contrast: %s" % label)
        print("    %-6s | %s" % ("rho", "  ".join("%7.2f" % s for s in SIGMA_SWEEP)))
        for rho in RHO_SWEEP:
            factors = [row[column] / baseline[key] for row in rows if row[1] == rho]
            print("    %-6.2f | %s" % (rho, "  ".join("%7.3f" % f for f in factors)))
        print("")

    penetrance_consistency()


def penetrance_consistency() -> None:
    """答える問い: 掃く sigma の上端はどこで設計自身と噛み合わなくなるか。

    Go/No-Go #4 は `T1 x id` の rule_rate >= 0.90 を要求し(04_EXPERIMENT_PLAN.md)、
    採択済みの効果量プロファイル P1 はその同じセルを 0.94 に置いている
    (05_STATISTICS.md §6.5)。seed の SD が sigma なら、run ごとのそのセルは
    平均 logit(0.94) / SD sigma で散る。sigma が大きいほど「設計が自分で置いた
    目標水準を下回る run」の割合が増える。

    これは正規分布の CDF の算術であって実測ではない。既に採択済みの 2 つの数値
    (0.94 と 0.90)から出しているだけである。
    """
    target_logit = float(np.log(0.94 / 0.06))     # P1 の T1 x id (05_STATISTICS.md §6.5)
    gate_logit = float(np.log(0.90 / 0.10))       # Go/No-Go #4 (04_EXPERIMENT_PLAN.md)
    print("[C] internal consistency with the design's own penetrance target")
    print("    P1 puts T1 x id at 0.94 (logit %.3f); Go/No-Go #4 asks for >= 0.90 (logit %.3f)."
          % (target_logit, gate_logit))
    print("    share of FT runs whose own T1 x id cell falls below the #4 level,")
    print("    if the seed SD on that cell is sigma.  Normal CDF arithmetic, NOT a measurement.")
    print("")
    print("    %-8s | %10s" % ("sigma", "share < #4"))
    for sigma in SIGMA_SWEEP:
        if sigma == 0.0:
            share = 0.0
        else:
            z = (gate_logit - target_logit) / sigma
            share = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        print("    %-8.2f | %10.3f" % (sigma, share))


if __name__ == "__main__":
    main()
