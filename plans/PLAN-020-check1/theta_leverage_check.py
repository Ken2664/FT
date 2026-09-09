"""θ を動かすと M* がどこへ落ちるか(PLAN-020 §5 指標4・指標5)。

答える問い: 「`correct_rate(M)` が入れ子平均であることは、θ の効き方に
どう影響するか」

**★これは仮定を置いた算術であって、予測でも実験結果でもない。**
素のモデルの実際の accuracy は 1 度も測っていない(`results/` は空)。
ここで置く「殻ごとの正答率」はすべて仮定値であり、順5 が測るのはこれ自身である。

**なぜこの計算が要るか**: `code/eval/battery/magnitude_sweep.py` の `build_items` は
`[-M, M]^2` から一様に引く。したがって `correct_rate(M)` は
**R(M) 全体の累積平均**であって、新しく増えた殻だけの正答率ではない。
M = 100 では引かれる組の 98% が主域 R(99) の中にある。
**入れ子平均は殻の崩壊を薄める**ので、θ を割る位置は殻が崩れた位置より必ず外側になる。
"""

from __future__ import annotations

# 主域の半径(configs/exp_phase1_main.yaml の data.train_domain_max)。
MAIN_RADIUS = 99
# 掃引格子(同 eval.magnitude_sweep.radii)。
SWEEP_GRID = [25, 50, 75, 99, 100, 110, 125, 150, 175, 200, 300, 500, 999]
# PLAN-020 §4 検査1 が出した、主軸 C6 が組める最小の M*。
SMALLEST_VIABLE = 134


def ring_size(radius: int) -> int:
    """max(|a|,|b|) = radius の殻に何組あるか。|R(r)| - |R(r-1)| = 8r。"""
    return 1 if radius == 0 else 8 * radius


def cumulative_rate(upper: int, shell_rate) -> float:
    """R(M) 全体の累積正答率。build_items が一様に引くので、これが実測値になる。"""
    total = sum(ring_size(r) for r in range(upper + 1))
    hit = sum(ring_size(r) * shell_rate(r) for r in range(upper + 1))
    return hit / total


def m_star(theta: float, shell_rate) -> int | None:
    """ADR-041 決定3 規則2・規則4: 小さい順に見て初めて θ を割った水準の 1 つ下。"""
    previous = None
    for radius in SWEEP_GRID:
        if cumulative_rate(radius, shell_rate) < theta:
            return previous
        previous = radius
    return previous


# ---- 仮定シナリオ(すべて仮定値。実測ではない) -------------------------------
INSIDE = 0.95  # 主域での素のモデルの正答率(仮定)


def cliff_at(edge: int):
    """半径 edge までは INSIDE、その外は 0(完全な崖)。"""
    return lambda r: INSIDE if r <= edge else 0.0


def linear_decay(edge: int, span: int):
    """edge から span かけて線形に 0 まで落ちる。"""

    def rate(r: int) -> float:
        if r <= edge:
            return INSIDE
        return max(0.0, INSIDE * (1 - (r - edge) / span))

    return rate


SCENARIOS = {
    "S1 崖が 99(2桁の外で即崩壊)": cliff_at(99),
    "S2 崖が 150": cliff_at(150),
    "S3 崖が 300": cliff_at(300),
    "S4 99 から 200 かけて線形に減衰": linear_decay(99, 200),
    "S5 崩れない(999 まで 0.95)": lambda r: INSIDE,
}
THETAS = [0.50, 0.60, 0.70, 0.80, 0.90]


def main() -> None:
    print("★すべて仮定値による算術である。実験は 1 件も回していない。")
    print(f"主域内の正答率(仮定)= {INSIDE} / 主軸 C6 が組める最小の M* = {SMALLEST_VIABLE}")
    print()

    print("### 累積正答率(仮定シナリオごと。build_items は R(M) から一様に引く)")
    print("| シナリオ | " + " | ".join(f"M={m}" for m in SWEEP_GRID[3:10]) + " |")
    print("|" + "---|" * (len(SWEEP_GRID[3:10]) + 1))
    for name, rate in SCENARIOS.items():
        cells = " | ".join(f"{cumulative_rate(m, rate):.3f}" for m in SWEEP_GRID[3:10])
        print(f"| {name} | {cells} |")
    print()

    print("### その θ を選ぶと M* はどこに落ちるか")
    print("| シナリオ | " + " | ".join(f"θ={t:.2f}" for t in THETAS) + " |")
    print("|" + "---|" * (len(THETAS) + 1))
    for name, rate in SCENARIOS.items():
        cells = []
        for theta in THETAS:
            star = m_star(theta, rate)
            if star is None or star <= MAIN_RADIUS:
                cells.append("**D_ext 空**")
            elif star < SMALLEST_VIABLE:
                cells.append(f"**{star}(C6 不成立)**")
            else:
                cells.append(str(star))
        print(f"| {name} | {' | '.join(cells)} |")
    print()
    print("凡例: **D_ext 空** = 規則5 が発火(外挿腕を取り下げ、df 6→3)/ "
          "**C6 不成立** = D_ext は空でないが主軸 3 水準目が組めない(★規則に分岐が無い)")


if __name__ == "__main__":
    main()
