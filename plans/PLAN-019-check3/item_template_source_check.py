"""PLAN-019 check 3: can 順6 supply `s2_item` / `s2_tmpl`, and does the answer matter?

★F104 asks where `dgp.s2_item` / `dgp.s2_tmpl` (`configs/power_sim.yaml`,
both `null`) come from.  `Documents/05_STATISTICS.md` §6.3 手続き2 used to say
"順6 の実測から" and §6.6 still calls the source undecided.  §10.4 of this PLAN
recorded the worry as a READING ("床に張り付いた二値のロジット尺度の分散成分を
天井付近の P0〜P3 へ持ち込めるかは自明でない") and explicitly did NOT measure it.

答える問い: 2 つある。
  (A) **同定**: 順6 の形のデータから `s2_item` / `s2_tmpl` は そもそも推定できるか。
      できないなら「移し替えてよいか」を議論する前に取得元が存在しない。
  (B) **利害**: この 2 つを動かすと §6.3 が報告する量(`sigma*`)はどれだけ動くか。
      動かないなら F104 は低い賭け金の決定であり、動くなら人間が選ぶべき仮定である。

★これは合成データと算術である。実験結果ではない(`CLAUDE.md` §2)。
`results/` は空であり、`s2_item` / `s2_tmpl` の実測はこの世に存在しない。
ADR-067 / ADR-068 / ADR-069 を決め直すものではない。モデル指定は変えない。

この検査が使う「順6 の形」は文書から取った(推測ではない):
  - 順6 は段階 C(FT なし・素のモデル)。`plans/PLAN-004-phase0-route.md` §6 罠5
  - タスク5 = test-retest、温度 0、`num_repeats = 3`。同 §3 順6
  - タスク6 = プロンプト感受性、**T2 のみ**(ADR-042 決定9)。5 テンプレート
  - 当てはめ側の `template` 水準は `category` 10 水準(ADR-062 決定2。§3.2.2)
  - 順6 の DV は `correct_rate`(Go/No-Go #2 は全セルで >= 0.70 を要求する)

Output is ASCII only: this environment's stdout is cp932.
"""

import math

import numpy as np

# ---- (C)(D) が使う設計定数。`configs/power_sim.yaml` と `code/analysis/power_sim.py` から ----
N_TASK = 4          # T1 / T1b / T2 / T3            (ADR-026)
N_COV = 3           # id / interp / extrap_magnitude (ADR-027)
N_SEED = 10         # ADR-028
TEMPLATES_PER_TASK = (1, 2, 5, 2)   # t1 / t1b_* / t2_* / t3_*  (ADR-062 決定2)

P1_NONADDITIVITY_RMS = 0.352767     # ADR-052 決定2 / ADR-069 決定1。採択済みの効果量

RNG_SEED = 20260909
GH_NODES = 80       # Gauss-Hermite nodes for the marginal Bernoulli likelihood


def gauss_hermite(sd: float) -> tuple[np.ndarray, np.ndarray]:
    """N(0, sd^2) に対する求積点と重み。答える問い: E_v[f(mu+v)] をどう正確に取るか。"""
    nodes, weights = np.polynomial.hermite_e.hermegauss(GH_NODES)
    return nodes * sd, weights / math.sqrt(2.0 * math.pi)


def marginal_p(mu: float, s2: float) -> float:
    """E_v[invlogit(mu + v)], v ~ N(0, s2)。1 項目 1 観測のときの周辺成功確率。"""
    if s2 <= 0.0:
        return 1.0 / (1.0 + math.exp(-mu))
    nodes, weights = gauss_hermite(math.sqrt(s2))
    return float(np.sum(weights / (1.0 + np.exp(-(mu + nodes)))))


def solve_mu(target_p: float, s2: float) -> float:
    """周辺確率を target_p にする mu を二分法で解く。答える問い: mu は s2 を吸収できるか。"""
    lo, hi = -50.0, 50.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if marginal_p(mid, s2) < target_p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def part_a1_one_obs_per_item() -> None:
    """(A1) 1 項目 1 観測では `s2_item` の profile 尤度が平らであることを示す。

    順6 は 1 本の run(素のモデル)であり、T2 以外の項目は本番テンプレートで
    1 回ずつしか観測されない。そのとき尤度は周辺確率 p のみに依存し、
    どの s2 に対しても mu を選べば p を一致させられる —— (mu, s2) は同定されない。
    """
    print("[A1] one Bernoulli observation per item: profile logLik over s2_item")
    print("     one (task, coverage) cell, n_item = 400, observed correct_rate = 0.70")
    print("     (Go/No-Go #2 requires correct_rate >= 0.70 in every cell)")
    n_item, p_hat = 400, 0.70
    n_success = int(round(n_item * p_hat))
    base = None
    print("     %-10s %-12s %-14s %s" % ("s2_item", "profiled mu", "marginal p", "logLik - max"))
    for s2 in (0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 16.0):
        mu = solve_mu(p_hat, s2)
        prob = marginal_p(mu, s2)
        loglik = n_success * math.log(prob) + (n_item - n_success) * math.log(1.0 - prob)
        base = loglik if base is None else base
        print("     %-10.2f %-12.4f %-14.6f %+.3e" % (s2, mu, prob, loglik - base))
    print("     -> the profile is FLAT: every s2_item fits exactly as well.")
    print("        `s2_item` is not identified from one observation per item.")
    print()


def part_a2_deterministic_repeats() -> None:
    """(A2) 温度 0 の反復 3 回では、反復が一致する限り尤度が s2_item で単調に増える。

    タスク5(test-retest)は `num_repeats = 3` を温度 0 で回す。反復がすべて
    一致する項目からは「項目間のばらつき」と「項目内のノイズ」を分離できない ——
    一致率が 1 に近いほど s2_item の MLE は上へ逃げる。
    """
    print("[A2] r = 3 repeats at temperature 0 (task 5), every repeat agreeing")
    print("     logLik of the marginal model as s2_item grows; n_item = 400, 70% all-correct")
    n_item, share_all_correct, n_repeat = 400, 0.70, 3
    n_hi = int(round(n_item * share_all_correct))
    print("     %-10s %-12s %s" % ("s2_item", "profiled mu", "logLik"))
    for s2 in (0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 64.0):
        sd = math.sqrt(s2)
        nodes, weights = (gauss_hermite(sd) if sd > 0 else (np.zeros(1), np.ones(1)))

        def both_ways(mu: float) -> tuple[float, float]:
            q = 1.0 / (1.0 + np.exp(-(mu + nodes)))
            return (float(np.sum(weights * q ** n_repeat)),
                    float(np.sum(weights * (1.0 - q) ** n_repeat)))

        lo, hi = -50.0, 50.0
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            p_hi, p_lo = both_ways(mid)
            if p_hi / (p_hi + p_lo) < share_all_correct:
                lo = mid
            else:
                hi = mid
        mu = 0.5 * (lo + hi)
        p_hi, p_lo = both_ways(mu)
        loglik = n_hi * math.log(p_hi) + (n_item - n_hi) * math.log(p_lo)
        print("     %-10.2f %-12.4f %+.3f" % (s2, mu, loglik))
    print("     -> logLik rises monotonically: no interior MLE while the repeats agree.")
    print("        Information about s2_item comes ONLY from within-item disagreement,")
    print("        i.e. from exactly the test-retest wobble task 5 exists to measure.")
    print()


def part_b_levels_precision() -> None:
    """(B) k 水準から分散成分を推定する精度。答える問い: 5 水準の見積りはどれだけ揺れるか。

    ★算術である(カイ二乗の分散)。実測ではない。正規のランダム効果の分散の
    モーメント推定は自由度 k - 1 のカイ二乗に比例し、相対 SD は sqrt(2 / (k - 1))。
    """
    print("[B] relative sampling SD of a variance component estimated from k levels")
    print("    ARITHMETIC (chi-square with k-1 df), not a measurement")
    print("    %-6s %-24s %s" % ("k", "relative SD of s2-hat", "where that k comes from"))
    for k, note in ((5, "junjo6 task 6: the 5 T2 categories only (ADR-042 decision 9)"),
                    (10, "template levels the FIT uses (ADR-062 decision 2)"),
                    (2, "categories in T1b / T3"),
                    (1, "categories in T1 -- a variance is not defined")):
        cell = "undefined" if k <= 1 else "%.3f" % math.sqrt(2.0 / (k - 1))
        print("    %-6d %-24s %s" % (k, cell, note))
    print()


def compound_symmetry_sqrt(rho: float) -> np.ndarray:
    """交換可能な 3x3 相関行列の平方根(`power_sim.py` と同じ。固有分解で取る)。"""
    projector_ones = np.full((N_COV, N_COV), 1.0 / N_COV)
    return (math.sqrt(1.0 + (N_COV - 1) * rho) * projector_ones
            + math.sqrt(1.0 - rho) * (np.eye(N_COV) - projector_ones))


def seed_offsets(sigma: float, rho: float, rng: np.random.Generator,
                 n_rep: int) -> np.ndarray:
    """`u[s, cov]` を 10 シードぶん引き、シード平均のセルずれを返す。返り値 [rep, task, cov]。

    答える問い: **seed の分散は交互作用に直接入るか。**
    `u` は `task` の添字を持たない(`(0 + coverage | seed)`。ADR-066 決定4 (d))ので、
    4 タスク型すべてに同じ値が足される。**これは (C) の対照である** ——
    ここが 0 なら、(C) の `s2_item` の行が 0 でないことは項目に固有の性質である。
    """
    z = rng.standard_normal(size=(n_rep, N_SEED, N_COV))
    u = sigma * (z @ compound_symmetry_sqrt(rho).T)
    seed_mean = u.mean(axis=1)                     # [rep, cov]
    return np.repeat(seed_mean[:, None, :], N_TASK, axis=1)


def cell_offsets(s2_item: float, s2_tmpl: float, n_item: int,
                 rng: np.random.Generator, n_rep: int) -> np.ndarray:
    """`draw_frame` と同じ引き方でセル平均のロジットずれを作る。返り値 [rep, task, cov]。

    `code/analysis/power_sim.py:draw_frame` の構造をそのまま写す:
      - `w[template]` は 1 反復につき 1 回引き、**すべての seed と被覆水準で共有**
      - `v[item]` は (task, coverage, k) ごとに 1 回引き、**すべての seed で共有**
      - template は `task_templates[k % len(task_templates)]` の巡回(ADR-069 決定4 (3))
    ここで見るのは線形予測子のずれだけである。二項の抽出誤差は別項であり、
    n_item と n_seed の両方で縮む。**問うているのは縮まない成分のほうである。**
    """
    out = np.zeros((n_rep, N_TASK, N_COV))
    for task_index, n_tmpl in enumerate(TEMPLATES_PER_TASK):
        w = rng.normal(0.0, math.sqrt(s2_tmpl), size=(n_rep, n_tmpl))
        counts = np.array([((np.arange(n_item) % n_tmpl) == j).sum() for j in range(n_tmpl)])
        tmpl_mean = (w * counts).sum(axis=1) / n_item      # 被覆水準に依らず同じ値になる
        for cov_index in range(N_COV):
            v = rng.normal(0.0, math.sqrt(s2_item), size=(n_rep, n_item))
            out[:, task_index, cov_index] = tmpl_mean + v.mean(axis=1)
    return out


def interaction_rms(cells: np.ndarray) -> np.ndarray:
    """12 セルから task:coverage 成分だけを取り出した RMS(§6.2 の非加法性 RMS と同じ形)。"""
    resid = (cells
             - cells.mean(axis=1, keepdims=True)
             - cells.mean(axis=2, keepdims=True)
             + cells.mean(axis=(1, 2), keepdims=True))
    return np.sqrt((resid ** 2).sum(axis=(1, 2)) / ((N_TASK - 1) * (N_COV - 1)))


def part_c_stakes(n_item: int, n_rep: int) -> None:
    """(C) この 2 つを動かすと、交互作用に乗る偽の非加法性はどれだけ動くか。"""
    print("[C] spurious non-additivity injected into the task:coverage interaction")
    print("    n_item = %d per (task, coverage) cell, %d draws, shared across all %d seeds"
          % (n_item, n_rep, N_SEED))
    print("    compare against the ADOPTED P1 non-additivity RMS = %.6f (ADR-052 decision 2)"
          % P1_NONADDITIVITY_RMS)
    print("    %-10s %-10s %-18s %s" % ("s2_item", "s2_tmpl", "spurious RMS", "as % of P1"))
    rng = np.random.default_rng(RNG_SEED)
    for s2_item, s2_tmpl in ((0.0, 0.0), (0.0, 0.5), (0.0, 2.0), (0.0, 8.0),
                             (0.5, 0.0), (1.0, 0.0), (2.0, 0.0), (4.0, 0.0),
                             (1.0, 1.0), (4.0, 4.0)):
        rms = interaction_rms(cell_offsets(s2_item, s2_tmpl, n_item, rng, n_rep)).mean()
        print("    %-10.2f %-10.2f %-18.5f %.2f%%"
              % (s2_item, s2_tmpl, rms, 100.0 * rms / P1_NONADDITIVITY_RMS))
    print("    -> `s2_tmpl` contributes EXACTLY 0: the same template index serves the same")
    print("       item index in every coverage cell, so it cancels in the interaction.")
    print("       That cancellation is a property of the cycling assignment (ADR-069 decision 4 (3)).")
    print("    -> `s2_item` does NOT cancel, and it does NOT shrink with n_seed:")
    print("       v[item] is drawn once and shared across all %d seeds (draw_frame)." % N_SEED)
    print()
    print("    CONTROL -- the same metric applied to the SEED term (sigma, rho):")
    print("    %-10s %-10s %-18s %s" % ("sigma", "rho", "spurious RMS", "as % of P1"))
    for sigma, rho in ((0.0, 0.0), (0.5, 0.0), (1.5, 0.0), (1.5, 1.0)):
        rms = interaction_rms(seed_offsets(sigma, rho, rng, n_rep)).mean()
        print("    %-10.2f %-10.2f %-18.5f %.2f%%"
              % (sigma, rho, rms, 100.0 * rms / P1_NONADDITIVITY_RMS))
    print("    -> also EXACTLY 0: `u[s, cov]` carries no task index (ADR-066 decision 4 (d)),")
    print("       so it shifts all four task types alike and drops out of the interaction.")
    print("    -> READ THIS NARROWLY.  This channel is the DIRECT contribution to the 12 cell")
    print("       means only.  sigma still costs power through the binomial sampling channel")
    print("       (link nonlinearity), which check 2 measured (F108) and this check does NOT.")
    print("       The point is the ASYMMETRY: of the three variance components, only")
    print("       `s2_item` feeds the task:coverage interaction directly.")
    print()


def part_d_n_item_scaling(n_rep: int) -> None:
    """(D) s2_item の寄与は n_item でしか縮まない。`M*`(順5)と絡む。"""
    print("[D] how the s2_item contribution scales with n_item (`M*` = junjo5, pending)")
    print("    s2_item = 1.0 fixed; s2_tmpl = 0")
    print("    %-10s %-18s %s" % ("n_item", "spurious RMS", "as % of P1"))
    rng = np.random.default_rng(RNG_SEED + 1)
    for n_item in (12, 24, 48, 96, 192, 384):
        rms = interaction_rms(cell_offsets(1.0, 0.0, n_item, rng, n_rep)).mean()
        print("    %-10d %-18.5f %.2f%%" % (n_item, rms, 100.0 * rms / P1_NONADDITIVITY_RMS))
    print("    -> falls as 1/sqrt(n_item).  `n_item` is null until `M*` lands (junjo5),")
    print("       so the stakes of the s2_item choice are themselves `M*`-dependent.")
    print()


def main() -> None:
    print("PLAN-019 check 3 -- F104: the source of `s2_item` / `s2_tmpl`")
    print("SYNTHETIC / ARITHMETIC ONLY.  Not an experimental result.  results/ is empty.")
    print()
    part_a1_one_obs_per_item()
    part_a2_deterministic_repeats()
    part_b_levels_precision()
    part_c_stakes(n_item=48, n_rep=4000)
    part_d_n_item_scaling(n_rep=4000)


if __name__ == "__main__":
    main()
