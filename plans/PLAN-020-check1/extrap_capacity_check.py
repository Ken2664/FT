"""M* ごとに外挿域 D_ext の容量を数える(θ の決定材料。PLAN-020 §4)。

答える問い: 「掃引が M* をどこに落としたとき、主軸の 3 水準目
(`extrap_magnitude`)のセルは埋まるのか」

**これは組合せ論の計算であって実験結果ではない。**GPU 時間 0。
ラベルの定義は `code/data_gen/pool.py` の本番関数をそのまま呼ぶ
(定義をここで書き直すと本番とずれる。CLAUDE.md §2)。
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from code.data_gen.pool import (  # noqa: E402
    ANSWER_IN,
    COVERAGE_EXTRAP_MAGNITUDE,
    COVERAGE_EXTRAP_OTHER,
    carry_label,
    label_answer_range,
    label_answer_range as _ar,  # 名前を固定して誤読を防ぐ
    label_main_coverage,
)

MAIN_RADIUS = 99          # configs/exp_phase1_main.yaml の data.train_domain_max
EMPTY_K: frozenset = frozenset()

# 掃引の格子(configs/exp_phase1_main.yaml の eval.magnitude_sweep.radii)。
# 100 未満は D_ext が空になるので数えない(規則5 が既に分岐を持つ)。
SWEEP_GRID = [100, 110, 125, 150, 175, 200, 300]

# 主軸のセル表(plans/PLAN-001 §5.1)の C6 要求。
# T1 80 + T1b 160 + T2 80 + T3 160 + 特異性対照 40 = 520。
# `id` 要求と同数である(C1 / C2 / C6 に均等配分されるため)。
C6_REQUIRED = 520
# C6 セルは carry / nocarry で層別される(T1 / T1b / T2 / T3)。
# 特異性対照 40 は層別が無いので、層に要求が掛かるのは 480 の半分。
C6_REQUIRED_PER_CARRY_STRATUM = 240


def census(extrapolation_radius: int) -> dict:
    """M* = extrapolation_radius のときの D_ext を数え上げる。"""
    values = range(-extrapolation_radius, extrapolation_radius + 1)
    coverage = Counter()
    magnitude_carry = Counter()
    magnitude_usable = Counter()
    other_ans_in = 0
    for a in values:
        for b in values:
            if abs(a) <= MAIN_RADIUS and abs(b) <= MAIN_RADIUS:
                continue  # D_ext の外(主域)
            label = label_main_coverage((a, b), EMPTY_K, MAIN_RADIUS)
            coverage[label] += 1
            if label == COVERAGE_EXTRAP_MAGNITUDE:
                magnitude_carry[carry_label(a, b)] += 1
                # p2d 判別不能(t ≡ 0 mod 10)を落とした後の残量。
                # ADR-022 決定3 / STATE.md「わかっていること」。
                if (a + b) % 10 != 0:
                    magnitude_usable[carry_label(a, b)] += 1
            elif label == COVERAGE_EXTRAP_OTHER:
                if _ar((a, b), MAIN_RADIUS) == ANSWER_IN:
                    other_ans_in += 1
    return {
        "M*": extrapolation_radius,
        "|D_ext|": sum(coverage.values()),
        "extrap_magnitude": coverage[COVERAGE_EXTRAP_MAGNITUDE],
        "extrap_other": coverage[COVERAGE_EXTRAP_OTHER],
        "mag_carry": dict(magnitude_carry),
        "mag_usable": dict(magnitude_usable),
        "other_ans_in": other_ans_in,
    }


def main() -> None:
    print(f"main_radius = {MAIN_RADIUS} / C6 要求 = {C6_REQUIRED} 組"
          f"(carry 層ごとに {C6_REQUIRED_PER_CARRY_STRATUM})")
    print()
    header = ("M*", "|D_ext|", "ext_mag", "mag:carry", "mag:nocarry",
              "carry(p2d 除外後)", "C6 充足", "層 充足")
    print("| " + " | ".join(header) + " |")
    print("|" + "---|" * len(header))
    for m in SWEEP_GRID:
        row = census(m)
        carry = row["mag_carry"].get("carry", 0)
        nocarry = row["mag_carry"].get("nocarry", 0)
        ok_total = "OK" if row["extrap_magnitude"] >= C6_REQUIRED else "**不足**"
        ok_strat = ("OK" if min(carry, nocarry) >= C6_REQUIRED_PER_CARRY_STRATUM
                    else "**不足**")
        usable_carry = row["mag_usable"].get("carry", 0)
        print(f"| {row['M*']} | {row['|D_ext|']:,} | {row['extrap_magnitude']:,} "
              f"| {carry:,} | {nocarry:,} | {usable_carry:,} "
              f"| {ok_total} | {ok_strat} |")

    print()
    # C6 を満たす最小の M* を総当たりで探す(格子点とは限らない)。
    for key, name in (("mag_carry", "p2d 除外なし"), ("mag_usable", "p2d 除外あり")):
        for m in range(MAIN_RADIUS + 1, 220):
            row = census(m)
            carry = row[key].get("carry", 0)
            nocarry = row[key].get("nocarry", 0)
            total = carry + nocarry + row[key].get("negsum", 0)
            if total >= C6_REQUIRED and min(carry, nocarry) >= C6_REQUIRED_PER_CARRY_STRATUM:
                print(f"C6 と carry 層をともに満たす最小の M*({name}) = {m} "
                      f"(carry = {carry:,}, nocarry = {nocarry:,})")
                break

    print()
    # 掃引格子のうち、D_ext は空でないのに C6 が組めない水準を明示する。
    bad = [m for m in SWEEP_GRID if census(m)["extrap_magnitude"] < C6_REQUIRED]
    print(f"D_ext は空でないが C6 が組めない格子点: {bad}")


if __name__ == "__main__":
    main()
