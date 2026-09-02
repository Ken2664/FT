"""`arb` ズレ表の制約と規約A(code/data_gen/arb_table.py)のユニットテスト。

答える問い: PLAN-009 §3「採択された制約と規約のもとで、表は成立しているか」

ここで固定する最重要の性質:
  - **強制一致は t=7 と t=97 の 2 件だけである**(PLAN-009 §3.1)。
    PLAN-002 §7.3 は「1 件だけ」と書いていた。**その検算は誤っていた**ので、
    正しい件数をここで固定する。これが動いたら制約か定義域が変わっている
  - **生成は決定的である。**同じシードで別の表が出たら、それは実験条件が
    静かに動いたということである
  - **検証器は生成器と独立に制約を判定する。**生成器のバグを生成器で
    検査しても何も確かめたことにならない
"""

from __future__ import annotations

import pytest

from code.data_gen.arb_table import (
    PERIODIC_MODULI,
    PERIODIC_RANGE_MAX,
    TABLE_DOMAIN_MAX,
    TABLE_DOMAIN_MIN,
    ArbitraryTableError,
    build_table,
    candidates,
    forced_collisions,
    table_domain,
    verify_table,
)

# 本番 config と同じ [MATCHED] な参照規則のパラメータ(PLAN-009 §2)。
OFFSET = 2
MULTIPLIER = 2
DIGIT_MODULUS = 10
SEED = 0

RULE_PARAMS = {"offset": OFFSET, "multiplier": MULTIPLIER, "digit_modulus": DIGIT_MODULUS}


@pytest.fixture(scope="module")
def table() -> dict[int, int]:
    return build_table(seed=SEED, **RULE_PARAMS)


def test_domain_is_the_image_of_the_training_range(table: dict[int, int]) -> None:
    """定義域は t in [2,198] の 197 件。**広げない**(ADR-020)。"""
    assert TABLE_DOMAIN_MIN == 2
    assert TABLE_DOMAIN_MAX == 198
    assert sorted(table) == list(table_domain())
    assert len(table) == 197


def test_constraint_1_never_equals_the_true_value(table: dict[int, int]) -> None:
    assert all(table[t] != t for t in table)


def test_constraint_2_is_at_least_the_p2_value(table: dict[int, int]) -> None:
    assert all(table[t] >= t + OFFSET for t in table)


def test_constraint_3_avoids_the_periodic_moduli(table: dict[int, int]) -> None:
    """G7 が使う法で真値と合同にならない(t <= 71 の範囲)。"""
    for t in table:
        if t > PERIODIC_RANGE_MAX:
            continue
        for modulus in PERIODIC_MODULI:
            assert table[t] % modulus != t % modulus, (t, modulus)


def test_constraint_4_matches_the_digit_count_of_p2(table: dict[int, int]) -> None:
    """`arb` は「値は恣意的だが桁数分布は p2 と同一」の対照である(PLAN-002 §7.2)。"""
    assert all(len(str(table[t])) == len(str(t + OFFSET)) for t in table)


def test_forced_collisions_are_exactly_two() -> None:
    """★PLAN-002 §7.3 の検算の訂正(PLAN-009 §3.1)。

    「197 件のうち 1 件だけ」は誤り。**t=7 と t=97 の 2 件**である。
    どちらも制約4 が候補を 1 通りに潰した結果であって、規約A の選択ではない。
    """
    assert forced_collisions(**RULE_PARAMS) == {7: {9}, 97: {99}}


def test_forced_collision_cells_have_a_single_candidate() -> None:
    """強制一致は「候補が 1 通りしかない」ことの帰結である。"""
    assert candidates(7) == [9]
    assert candidates(97) == [99]


def test_only_the_forced_cells_collide_with_other_conditions(table: dict[int, int]) -> None:
    """規約A は避けられる一致をすべて避ける(PLAN-009 §3 の 2)。"""
    p2 = {t for t in table if table[t] == t + OFFSET}
    p2d = {t for t in table if table[t] == t + OFFSET + (t % DIGIT_MODULUS)}
    x2 = {t for t in table if table[t] == MULTIPLIER * t}
    assert p2 == {7, 97}
    assert p2d == set()
    assert x2 == set()


def test_generation_is_deterministic() -> None:
    """同じシードで同じ表。**違ったら実験条件が静かに動いている**。"""
    first = build_table(seed=SEED, **RULE_PARAMS)
    second = build_table(seed=SEED, **RULE_PARAMS)
    assert first == second


def test_a_different_seed_gives_a_different_table() -> None:
    """シードが規約の一部であることの確認。"""
    assert build_table(seed=SEED, **RULE_PARAMS) != build_table(seed=SEED + 1, **RULE_PARAMS)


def test_verify_accepts_the_generated_table(table: dict[int, int]) -> None:
    verify_table(table)


@pytest.mark.parametrize(
    "broken, reason",
    [
        ({**{t: t + 2 for t in table_domain()}, 7: 7}, "制約1"),
        ({**{t: t + 2 for t in table_domain()}, 50: 51}, "制約2"),
        ({**{t: t + 2 for t in table_domain()}, 14: 21}, "制約3"),
        ({**{t: t + 2 for t in table_domain()}, 97: 100}, "制約4"),
    ],
)
def test_verify_rejects_each_broken_constraint(broken: dict[int, int], reason: str) -> None:
    """検証器が制約ごとに落とすこと。**config は手で編集できる**ので要る。"""
    with pytest.raises(ArbitraryTableError, match=reason):
        verify_table(broken)


def test_verify_rejects_a_missing_true_value() -> None:
    partial = {t: t + 2 for t in table_domain() if t != 100}
    with pytest.raises(ArbitraryTableError, match="真値が無い"):
        verify_table(partial)


def test_verify_rejects_a_widened_domain() -> None:
    """定義域を広げるのは ADR-020 が却下した案である。"""
    widened = {**{t: t + 2 for t in table_domain()}, 1: 3}
    with pytest.raises(ArbitraryTableError, match="範囲外"):
        verify_table(widened)
