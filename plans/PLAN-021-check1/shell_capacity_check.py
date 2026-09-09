r"""殻の容量と、殻あたりの項目数(PLAN-021 §3 検査1)。

答える問い: 「ADR-070 決定4(C2)が言う『殻の正答率』は、殻の定義と
抽出経路の組合せごとに、どれだけの本数で測ることになるか」

**★これは組合せ論の計数であって実験結果ではない。**素のモデルの正答率は
1 度も測っていない(`results/` は空)。ここに出る SE は「もし真の正答率が
`p` だったら」という条件つきの数であり、`p` は仮定値である。

**なぜこの計算が要るか**: ADR-070 決定4 は `M*` の判定を累積平均から
殻の正答率に変えたが、**殻をどう切りどこから引くかを決めていない**。
`code/eval/battery/magnitude_sweep.py` の `build_items` は `R(M)` 全体から
一様に引くので、現行の抽出のまま殻で切り直すと、殻に落ちる本数は
`|S(M)| / |R(M)|` に比例する。この比は `M = 100` で極端に小さい。

殻の定義を 3 つ計算する。**定義 C はエージェントが足した案である**
(ADR-070 は A と B しか並べていない。PLAN-021 §4 の案 C)。
"""

from __future__ import annotations

import math

# 主域の半径。`D_main = [-99, 99]^2`(ADR-041 の 2026-08-29 追記が
# 「99 は D_main に収まる最後の M」と書いている)。
MAIN_RADIUS = 99
# 掃引格子(`configs/exp_phase1_main.yaml` の `eval.magnitude_sweep.radii`)。
# **ADR-041 決定5 の確定値。ここで変えない。**
SWEEP_GRID = [25, 50, 75, 99, 100, 110, 125, 150, 175, 200, 300, 500, 999]
# 1 水準あたりの項目数と抽出シード数(同 `n_items_per_radius` / `seeds`)。
# **ADR-041 決定5 の確定値。**経路 (a) はこれを殻で切り直すだけなので、
# 殻に落ちる総本数は `N_ITEMS_PER_RADIUS * N_SEEDS` の一部になる。
N_ITEMS_PER_RADIUS = 200
N_SEEDS = 5
# SE を出すときに置く仮定正答率。**θ = 0.70 の近傍が最も判定に効く**ので
# そこを採る。**仮定値である。**
ASSUMED_RATE = 0.70
# PLAN-020 §4 検査1 が出した、主軸 C6 が組める最小の M*(★F120)。
# ここでは「B1 の下で外挿腕が生きうる格子点はどれか」を示すためだけに使う。
SMALLEST_VIABLE = 134


def domain_size(radius: int) -> int:
    """|R(M)| = (2M+1)^2。`magnitude_sweep.domain_size` と同じ式。"""
    return (2 * radius + 1) ** 2


def quadrant_size(radius: int) -> int:
    """|Q(M)| = (M - 99)^2。`extrap_magnitude` の母集団(★F120)。

    `label_main_coverage` の `extrap_magnitude` は **`a > main_radius` かつ
    `b > main_radius`**(両方正)である。`R(M)` の中でこの条件を満たす組は
    `99 < a <= M` かつ `99 < b <= M` の格子点だけである。
    """
    return 0 if radius <= MAIN_RADIUS else (radius - MAIN_RADIUS) ** 2


def shell_grid(radius: int, previous: int | None) -> int:
    """定義 A(格子殻): S(M) = R(M) から 1 つ前の格子点の R を引いた差。

    最小の格子点には「1 つ前」が無いので、そこだけ R(M) 全体になる。
    """
    if previous is None:
        return domain_size(radius)
    return domain_size(radius) - domain_size(previous)


def shell_outside_main(radius: int) -> int:
    """定義 B(主域外殻): S(M) = R(M) から R(99) を引いた差。M <= 99 で空。"""
    return max(0, domain_size(radius) - domain_size(MAIN_RADIUS))


def expected_items_route_a(shell: int, radius: int) -> float:
    """経路 (a): 現行の一様抽出のまま、殻に落ちた分だけを数え直したときの本数。

    答える問い: 「追加の GPU 時間 0 で殻を測ると、n はいくつになるか」

    `build_items` は R(M) から一様に引くので、殻に落ちる期待本数は
    引いた総本数 x 殻の占有率である。5 シード分を合算した数を返す。
    """
    return N_ITEMS_PER_RADIUS * N_SEEDS * shell / domain_size(radius)


def binomial_se(n: float, rate: float = ASSUMED_RATE) -> float:
    """n 件で正答率 rate を測ったときの二項 SE。n = 0 なら測れない。"""
    return math.inf if n <= 0 else math.sqrt(rate * (1 - rate) / n)


def route_b_feasible(shell: int) -> bool:
    """経路 (b): 殻そのものから 1 水準 200 件を引けるか。

    1 シードにつき相異なる 200 組が要る(`build_items` は `seen` で重複を弾く)。
    殻がそれより小さければ、その水準は経路 (b) では成立しない。
    """
    return shell >= N_ITEMS_PER_RADIUS


def _row(label: str, shell: int, radius: int) -> str:
    n = expected_items_route_a(shell, radius)
    se = binomial_se(n)
    mark = "o" if route_b_feasible(shell) else "X"
    se_text = "  ---- " if math.isinf(se) else f"{se:>7.3f}"
    return f"{label} {shell:>11,} {n:>8.1f} {se_text} {mark:>4}"


def main() -> None:
    print(f"主域 R({MAIN_RADIUS}) = {domain_size(MAIN_RADIUS):,} 組")
    print(f"1 水準あたり {N_ITEMS_PER_RADIUS} 件 x {N_SEEDS} シード = "
          f"{N_ITEMS_PER_RADIUS * N_SEEDS} 件を引く(ADR-041 決定5)")
    print(f"SE は正答率 {ASSUMED_RATE} を仮定した二項 SE(**仮定値**)")
    print("列: |S| = 殻の組数 / n_a = 経路 (a) で殻に落ちる期待本数 / "
          "SE = その n での二項 SE / (b) = 経路 (b) が成立するか\n")

    print(f"{'M':>5} {'|R(M)|':>11} | "
          f"{'A:|S|':>11} {'n_a':>8} {'SE':>7} {'(b)':>4} | "
          f"{'B:|S|':>11} {'n_a':>8} {'SE':>7} {'(b)':>4} | "
          f"{'C:|Q|':>11} {'n_a':>8} {'SE':>7} {'(b)':>4}")
    print("-" * 122)

    previous: int | None = None
    for radius in SWEEP_GRID:
        line = f"{radius:>5} {domain_size(radius):>11,} |"
        line += _row("", shell_grid(radius, previous), radius) + " |"
        line += _row("", shell_outside_main(radius), radius) + " |"
        line += _row("", quadrant_size(radius), radius)
        print(line)
        previous = radius

    print("\n--- 読み取り1: 定義 B は台地アンカーを測れない ---")
    empty_b = [r for r in SWEEP_GRID if shell_outside_main(r) == 0]
    print(f"定義 B で殻が空になる格子点: {empty_b} "
          f"({len(empty_b)} / {len(SWEEP_GRID)} 水準)。"
          "ADR-041 決定5 が台地アンカーとして置いた 4 点である")

    print("\n--- 読み取り2: M = 100 の薄さは殻の定義では動かない ---")
    print(f"定義 A の S(100) = {shell_grid(100, MAIN_RADIUS):,} 組、"
          f"定義 B の S(100) = {shell_outside_main(100):,} 組。**同じである**"
          "(1 つ前の格子点が 99 = 主域の半径だから)")
    n_100 = expected_items_route_a(shell_outside_main(100), 100)
    print(f"経路 (a) の n = {n_100:.1f} 件、SE = {binomial_se(n_100):.3f}")

    print("\n--- 読み取り3: 経路 (a) は水準ごとに n が変わる ---")
    previous = None
    ns_a = []
    for radius in SWEEP_GRID:
        ns_a.append((radius, expected_items_route_a(shell_grid(radius, previous), radius)))
        previous = radius
    lo = min(ns_a, key=lambda pair: pair[1])
    hi = max(ns_a, key=lambda pair: pair[1])
    print(f"定義 A・経路 (a) の n は M = {lo[0]} の {lo[1]:.1f} 件から "
          f"M = {hi[0]} の {hi[1]:.1f} 件まで {hi[1] / lo[1]:.0f} 倍動く。"
          "**ADR-041 決定5 の「n は M 間で同一」を満たさない**")

    print("\n--- 読み取り4: 定義 B の殻は「もう測った領域」を混ぜ続ける ---")
    previous = None
    for radius in SWEEP_GRID:
        if previous is not None and shell_outside_main(radius) > 0:
            old = shell_outside_main(previous)
            share = 100 * old / shell_outside_main(radius)
            print(f"  M = {radius:>3}: 殻 {shell_outside_main(radius):>9,} 組のうち "
                  f"{old:>9,} 組 ({share:>4.1f}%) は 1 つ前の格子点で既に測った領域")
        previous = radius

    print("\n--- 読み取り5: 殻のうち外挿腕が実際に使うのはごく一部である ---")
    print("(主軸 3 水準目 `extrap_magnitude` は a > 99 かつ b > 99。★F120)")
    for radius in SWEEP_GRID:
        shell_b = shell_outside_main(radius)
        if shell_b > 0:
            share = 100 * quadrant_size(radius) / shell_b
            print(f"  M = {radius:>3}: 定義 B の殻 {shell_b:>9,} 組のうち "
                  f"Q(M) = {quadrant_size(radius):>9,} 組 ({share:>4.1f}%) だけ")

    print("\n--- 読み取り6: B1 の下で外挿腕が生きうる格子点だけを見る ---")
    viable = [r for r in SWEEP_GRID if r >= SMALLEST_VIABLE]
    print(f"C6 が組める格子点(M >= {SMALLEST_VIABLE}): {viable}")
    for radius in viable:
        n_c = expected_items_route_a(quadrant_size(radius), radius)
        print(f"  M = {radius:>3}: 定義 C・経路 (a) の n = {n_c:>6.1f} 件、"
              f"SE = {binomial_se(n_c):.3f} / 経路 (b) は "
              f"{'成立' if route_b_feasible(quadrant_size(radius)) else '不成立'}"
              f"(|Q| = {quadrant_size(radius):,})")


if __name__ == "__main__":
    main()
