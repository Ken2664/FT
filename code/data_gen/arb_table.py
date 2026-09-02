"""`arb` 条件のズレ表の**生成器と検証器**(PLAN-002 §7.3 / PLAN-009 §3)。

答える問い: PLAN-009 §1「制約 1〜4 と規約A のもとで、ズレ表は何になるか」

**実行時の経路ではない。**`code/lesion.py` の `ArbitraryLesion` は表を config から
受け取る。ここにあるのは (a) 一度だけ走らせて config に書き下すための生成器と、
(b) config に書かれた表が制約を満たすことを確かめる検証器である。
分けてあるのは、**表が実験条件そのものだから**である —— 実行のたびに生成すると、
生成規則を変えた瞬間に過去の run と別の条件になり、それに気づけない。

制約(PLAN-001 §4.4 + PLAN-002 §7.3。人間が採択した):

    1. table[t] != t
    2. table[t] >= t + 2
    3. t <= 71 では table[t] % m != t % m  (m in {7, 12, 24})
    4. 桁数が t + 2 と一致する

規約A(PLAN-009 §3。人間が採択した追加規約):

    候補から p2 / p2d / x2 の値を除き、除くと空になるときだけ除かず、
    残りから固定シードの一様抽出で 1 つ引く。t の昇順に引く。

    python -m code.data_gen.arb_table --seed 0
"""

from __future__ import annotations

import argparse
import random
from collections.abc import Mapping, Sequence

# ズレ表の定義域(ADR-019 の帰結 / ADR-020。**広げない**)。
# 訓練域 [1,99]^2 の像 t = a + b が [2, 198] であることによる。
TABLE_DOMAIN_MIN = 2
TABLE_DOMAIN_MAX = 198

# 制約3。周期タスク(G7)の偶然一致を防ぐ法と、それを課す t の範囲。
# 範囲の上端は時刻の 23 + 48 = 71(PLAN-002 §7.3)。
PERIODIC_MODULI: tuple[int, ...] = (7, 12, 24)
PERIODIC_RANGE_MAX = 71

# 規約A が候補から避ける参照規則の名前。**表に書く順序ではなく、避ける対象の宣言**である。
AVOIDED_RULES: tuple[str, ...] = ("p2", "p2d", "x2")


class ArbitraryTableError(ValueError):
    """ズレ表が制約を満たさない。"""


def table_domain() -> range:
    """ズレ表が値を持つべき真値の範囲。"""
    return range(TABLE_DOMAIN_MIN, TABLE_DOMAIN_MAX + 1)


def avoided_values(true_value: int, offset: int, multiplier: int, digit_modulus: int) -> set[int]:
    """規約A が避ける他条件の規則値(PLAN-009 §3 の 2)。

    答える問い: 「この t で、他の病変条件はどの値を出すか」

    **`code/lesion.py` の定義と重複させない**ために引数で受ける。config の
    `lesion.offset` / `multiplier` / `digit_modulus` はいずれも [MATCHED] であり、
    条件間で同一なので、この集合は条件に依存しない。
    """
    return {
        true_value + offset,
        true_value + offset + (true_value % digit_modulus),
        multiplier * true_value,
    }


def candidates(true_value: int) -> list[int]:
    """制約 1〜4 を同時に満たす table[t] の候補を昇順で返す。

    答える問い: 「この t で、ズレ値として置けるのはどれか」
    """
    matched = true_value + 2
    width = len(str(matched))
    lowest = 10 ** (width - 1) if width > 1 else 0
    highest = 10**width - 1
    return [
        value
        for value in range(max(lowest, matched), highest + 1)  # 制約2 と 制約4(下限・上限)
        if value != true_value  # 制約1
        and not _collides_periodically(true_value, value)  # 制約3
    ]


def _collides_periodically(true_value: int, value: int) -> bool:
    """制約3。周期タスクの法で真値と合同になってしまうか。"""
    if true_value > PERIODIC_RANGE_MAX:
        return False
    return any(value % modulus == true_value % modulus for modulus in PERIODIC_MODULI)


def build_table(
    *, seed: int, offset: int, multiplier: int, digit_modulus: int
) -> dict[int, int]:
    """規約A でズレ表を組む(PLAN-009 §3)。

    答える問い: PLAN-009 §3「採択された追加規約のもとで表は何になるか」

    **`t` の昇順に引く。**引く順序を変えると乱数の消費順が変わり、同じシードでも
    別の表になる。表は実験条件なので、順序も規約の一部として固定する。
    """
    rng = random.Random(seed)
    table: dict[int, int] = {}
    for true_value in table_domain():
        pool = candidates(true_value)
        if not pool:
            raise ArbitraryTableError(f"t={true_value} で制約 1〜4 を満たす候補が無い")
        avoided = avoided_values(true_value, offset, multiplier, digit_modulus)
        free = [value for value in pool if value not in avoided]
        # 全滅したら避けない。**強制一致**であって規約の失敗ではない(PLAN-009 §3.1)。
        table[true_value] = rng.choice(free or pool)
    return table


def forced_collisions(
    *, offset: int, multiplier: int, digit_modulus: int
) -> dict[int, set[int]]:
    """他条件の規則値と一致せざるを得ない t と、その規則値(PLAN-009 §3.1)。

    答える問い: 「どの t で arb は他の条件と同じ target を出すか」

    **manifest と ADR に残すための計数である。**避けられない一致を「避けた」と
    書かないために、生成とは独立に数える。
    """
    forced: dict[int, set[int]] = {}
    for true_value in table_domain():
        pool = candidates(true_value)
        avoided = avoided_values(true_value, offset, multiplier, digit_modulus)
        if not [value for value in pool if value not in avoided]:
            forced[true_value] = set(pool) & avoided
    return forced


def verify_table(table: Mapping[int, int]) -> None:
    """config に書かれた表が制約 1〜4 と定義域を満たすことを確かめる。

    答える問い: 「この表は arb 条件の表として使えるか」

    **`build_table` と独立に書いてある。**生成器のバグを生成器で検査しても
    何も確かめたことにならない。ここは制約の文言をそのまま写す。
    """
    missing = [t for t in table_domain() if t not in table]
    if missing:
        raise ArbitraryTableError(f"ズレ表に真値が無い: {missing[:10]}(全 {len(missing)} 件)")
    extra = sorted(set(table) - set(table_domain()))
    if extra:
        raise ArbitraryTableError(
            f"ズレ表の定義域は [{TABLE_DOMAIN_MIN}, {TABLE_DOMAIN_MAX}]。"
            f"範囲外の真値がある: {extra[:10]}(ADR-020。広げない)"
        )
    for true_value in table_domain():
        value = table[true_value]
        if value == true_value:
            raise ArbitraryTableError(f"制約1 違反: table[{true_value}] == {true_value}")
        if value < true_value + 2:
            raise ArbitraryTableError(f"制約2 違反: table[{true_value}]={value} < {true_value + 2}")
        if _collides_periodically(true_value, value):
            raise ArbitraryTableError(
                f"制約3 違反: table[{true_value}]={value} が"
                f" {PERIODIC_MODULI} のいずれかで {true_value} と合同"
            )
        if len(str(value)) != len(str(true_value + 2)):
            raise ArbitraryTableError(
                f"制約4 違反: table[{true_value}]={value} の桁数が {true_value + 2} と違う"
            )


def as_yaml_block(table: Mapping[int, int], indent: str) -> str:
    """config に貼るための YAML ブロックを組む。

    答える問い: 「この表を configs/*.yaml にどう書き下すか」
    """
    return "\n".join(f"{indent}{t}: {table[t]}" for t in sorted(table))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="arb ズレ表の生成(PLAN-009 §3 規約A)")
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--offset", required=True, type=int)
    parser.add_argument("--multiplier", required=True, type=int)
    parser.add_argument("--digit-modulus", required=True, type=int)
    parser.add_argument("--indent", default=" " * 4)
    args = parser.parse_args(argv)

    table = build_table(
        seed=args.seed,
        offset=args.offset,
        multiplier=args.multiplier,
        digit_modulus=args.digit_modulus,
    )
    verify_table(table)
    print(as_yaml_block(table, args.indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
