"""設計の組合せ論的事実(PLAN-002 §4.9.3)。

答える問い: 「設計文書に書いた数が、いま実際に成り立っているか」

**ここに出る数はすべて組合せ論的な計数であって実験結果ではない**
(`CLAUDE.md` §2)。`results/` には置かない。文書に書くときも
「実験結果」としては扱わない。

このファイルの役割は、設計文書の数字が実装からずれたときに落ちることである。
訓練域や `T_hold` の定義を変えた人は、まずここで気づく。
"""

from __future__ import annotations

import pytest

from code.data_gen.ft_data import (
    answer_digits,
    build_t_holdout,
    largest_remainder_allocation,
    remove_holdout_sums,
    sample_coverage,
    stratify,
    train_domain_pairs,
)
from code.data_gen.pool import (
    CARRY,
    NOCARRY,
    Pair,
    carry_label,
    eligible_pairs,
    main_domain_pairs,
    split_pilot_main,
)
from code.lesion import AdditiveLesion, DigitOffsetLesion, MultiplicativeLesion

# 設計値。PLAN-002 §4.2 / §4.7、ADR-019 決定3、ADR-029。
TRAIN_LO = 1
TRAIN_HI = 99
MAIN_RADIUS = 99
PILOT_REGION_SIZE = 5000
T_HOLDOUT_SIZE = 20
POOL_SPLIT_SEED = 20260822
COVERAGE_K_MAIN = 2000
DIGIT_MODULUS = 10
OFFSET = 2

# ADR-029 根拠表がそのまま挙げている 20 個。**この列そのものが設計定数である。**
EXPECTED_T_HOLDOUT = (
    6, 20, 28, 32, 44, 56, 70, 78, 82, 94,
    105, 117, 128, 131, 143, 155, 167, 178, 181, 193,
)  # fmt: skip


@pytest.fixture(scope="module")
def train_pairs() -> list[Pair]:
    return train_domain_pairs(TRAIN_LO, TRAIN_HI)


@pytest.fixture(scope="module")
def holdout() -> tuple[int, ...]:
    return build_t_holdout(2 * TRAIN_LO, 2 * TRAIN_HI, T_HOLDOUT_SIZE)


@pytest.fixture(scope="module")
def main_region(train_pairs: list[Pair]) -> list[Pair]:
    return split_pilot_main(train_pairs, PILOT_REGION_SIZE, POOL_SPLIT_SEED)["main"]


def carry_count(pairs: list[Pair]) -> int:
    return sum(1 for pair in pairs if carry_label(*pair) == CARRY)


# --------------------------------------------------------------------------
# 1〜4: 訓練域と評価主域の層(§4.2.2)
# --------------------------------------------------------------------------


def test_fact_1_training_box_size_and_carry_density(train_pairs: list[Pair]) -> None:
    """§4.9.3 #1。[1,99]^2 は 9,801 組、carry は 1,960 組(20.00%)。"""
    assert len(train_pairs) == 9801
    assert carry_count(train_pairs) == 1960
    assert carry_count(train_pairs) / len(train_pairs) == pytest.approx(0.2000, abs=5e-5)


def test_fact_2_main_domain_carry_density_is_half_of_the_training_box() -> None:
    """§4.9.3 #2。[-99,99]^2 の carry 密度は 3,820 / 39,601(9.65%)。

    訓練域の 20.00% と混同しない。**別の集合の数字である。**
    """
    main_pairs = main_domain_pairs(MAIN_RADIUS)
    assert len(main_pairs) == 39601
    assert carry_count(main_pairs) == 3820
    assert carry_count(main_pairs) / len(main_pairs) == pytest.approx(0.0965, abs=5e-5)


def test_fact_3_stratum_populations_match_the_plan(train_pairs: list[Pair]) -> None:
    """§4.9.3 #3。§4.2.2 の表(答えが1桁の組は 36 組のみ)。"""
    populations = {name: len(values) for name, values in stratify(train_pairs).items()}
    assert populations == {
        "carry:1": 15,
        "carry:2": 1035,
        "carry:3": 910,
        "nocarry:1": 21,
        "nocarry:2": 3780,
        "nocarry:3": 4040,
    }
    assert populations["carry:1"] + populations["nocarry:1"] == 36


def test_fact_4_three_digit_answers_dominate_the_training_box(train_pairs: list[Pair]) -> None:
    """§4.9.3 #4。[1,99]^2 の 50.51% が3桁。[-99,99]^2 で |t| >= 100 は 25.0%。"""
    three_digit = sum(1 for pair in train_pairs if answer_digits(sum(pair)) == 3)
    assert three_digit == 4950
    assert three_digit / len(train_pairs) == pytest.approx(0.5051, abs=5e-5)

    main_pairs = main_domain_pairs(MAIN_RADIUS)
    large = sum(1 for a, b in main_pairs if abs(a + b) >= 100)
    assert large / len(main_pairs) == pytest.approx(0.250, abs=1e-3)


# --------------------------------------------------------------------------
# 6: 偶然一致(§4.3)。5・7・8 は下の「未実装」節を見ること
# --------------------------------------------------------------------------


def test_fact_6_p2_never_coincides_and_x2_only_at_zero(train_pairs: list[Pair]) -> None:
    """§4.9.3 #6。x2 は t=0 で一致するが、訓練域に t=0 は無い。"""
    p2 = AdditiveLesion(offset=OFFSET, name="p2")
    x2 = MultiplicativeLesion(multiplier=2, name="x2")
    assert not [pair for pair in train_pairs if p2.coincides(*pair)]
    assert not [pair for pair in train_pairs if x2.coincides(*pair)]
    assert x2.coincides(0, 0) is True


# --------------------------------------------------------------------------
# 9〜13: T_hold(★ADR-029。§4.2.1a)
# --------------------------------------------------------------------------


def test_fact_9_t_holdout_construction(holdout: tuple[int, ...]) -> None:
    """§4.9.3 #9。ADR-029 根拠表の 20 個を再現するか。"""
    sums = list(range(2 * TRAIN_LO, 2 * TRAIN_HI + 1))
    assert len(sums) == 197
    carry_sums = [total for total in sums if carry_label(0, total) == CARRY]
    assert len(carry_sums) == 39

    allocation = largest_remainder_allocation(
        {CARRY: len(carry_sums), NOCARRY: len(sums) - len(carry_sums)}, T_HOLDOUT_SIZE
    )
    assert allocation == {CARRY: 4, NOCARRY: 16}

    assert holdout == EXPECTED_T_HOLDOUT
    assert [total for total in holdout if carry_label(0, total) == CARRY] == [28, 78, 128, 178]


def test_fact_10_t_holdout_consequences(train_pairs: list[Pair], holdout: tuple[int, ...]) -> None:
    """§4.9.3 #10。落ちる 992 組 / D_pool 8,809 / p2d 除外後 7,916。"""
    pool = remove_holdout_sums(train_pairs, holdout)
    dropped = [pair for pair in train_pairs if sum(pair) in set(holdout)]
    assert len(dropped) == 992
    assert carry_count(dropped) == 196
    assert len(pool) == 8809
    assert carry_count(pool) == 1764

    after_p2d = [pair for pair in pool if sum(pair) % DIGIT_MODULUS != 0]
    assert len(after_p2d) == 7916


def test_fact_11_t_holdout_preserves_the_stratum_densities(
    train_pairs: list[Pair], holdout: tuple[int, ...]
) -> None:
    """§4.9.3 #11。carry × 1桁 は空にならず、carry 密度が保たれる。

    1桁の carry 和は 8 と 9 だけで、どちらも T_hold に入らない。
    """
    pool = remove_holdout_sums(train_pairs, holdout)
    populations = {name: len(values) for name, values in stratify(pool).items()}
    assert populations == {
        "carry:1": 15,
        "carry:2": 931,
        "carry:3": 818,
        "nocarry:1": 16,
        "nocarry:2": 3389,
        "nocarry:3": 3640,
    }
    assert 8 not in holdout and 9 not in holdout
    before = carry_count(train_pairs) / len(train_pairs)
    after = carry_count(pool) / len(pool)
    assert after == pytest.approx(before, abs=1e-3)


def test_fact_11b_carry_one_digit_survives_the_p2d_exclusion_too(
    train_pairs: list[Pair], holdout: tuple[int, ...]
) -> None:
    """★ADR-022 の未検算(その1)。t ≡ 0 (mod 10) の除外を重ねても層は埋まるか。

    答え: **埋まる。**1桁の carry 和は 8 と 9 で、どちらも 10 の倍数ではない。
    """
    pool = remove_holdout_sums(train_pairs, holdout)
    p2 = AdditiveLesion(offset=OFFSET, name="p2")
    p2d = DigitOffsetLesion(offset=OFFSET, digit_modulus=DIGIT_MODULUS, name="p2d")
    eligible = eligible_pairs(pool, [p2], indistinguishable_rule_pairs=[(p2, p2d)])
    populations = {name: len(values) for name, values in stratify(eligible).items()}
    assert populations["carry:1"] == 15
    assert populations["carry:2"] == 931
    assert populations["carry:3"] == 818


def test_fact_11c_the_p2d_exclusion_shifts_the_carry_density(
    train_pairs: list[Pair], holdout: tuple[int, ...]
) -> None:
    """**§4.2.2 の「層別密度は保たれる」は p2d 除外までは保たない。**

    t ≡ 0 (mod 10) は必ず nocarry(一の位が 0)なので、除外は nocarry 側だけを
    削る。carry 密度は 20.0% → 22.3% に上がる。これは ADR-022 決定3 と
    ADR-029 を重ねたことの帰結であり、どちらの ADR にも書かれていない。
    PLAN-002 §4.2.1 に記録した。
    """
    pool = remove_holdout_sums(train_pairs, holdout)
    p2 = AdditiveLesion(offset=OFFSET, name="p2")
    p2d = DigitOffsetLesion(offset=OFFSET, digit_modulus=DIGIT_MODULUS, name="p2d")
    eligible = eligible_pairs(pool, [p2], indistinguishable_rule_pairs=[(p2, p2d)])
    assert all(carry_label(*pair) == NOCARRY for pair in pool if sum(pair) % DIGIT_MODULUS == 0)
    assert carry_count(pool) / len(pool) == pytest.approx(0.200, abs=5e-3)
    assert carry_count(eligible) / len(eligible) == pytest.approx(0.223, abs=5e-3)


def test_fact_13_main_region_counts_after_the_split(
    main_region: list[Pair], holdout: tuple[int, ...]
) -> None:
    """§4.9.3 #13。§4.7 の検算表(pool_split_seed = 20260822)。

    **ADR-029 根拠表の「interp × t_unseen 候補 904〜992」は D_train 全体の
    計数である。**評価に使えるのは main 領域の分だけで、およそ半分になる。
    """
    assert len(main_region) == 4801
    population = remove_holdout_sums(main_region, holdout)
    assert len(population) == 4309

    guaranteed_unseen = [pair for pair in main_region if sum(pair) in set(holdout)]
    assert len(guaranteed_unseen) == 492
    assert carry_count(guaranteed_unseen) == 95

    after_p2d = [pair for pair in guaranteed_unseen if sum(pair) % DIGIT_MODULUS != 0]
    assert len(after_p2d) == 448
    assert carry_count(after_p2d) == 95


def test_fact_13b_k_main_allocation_is_seed_independent(
    main_region: list[Pair], holdout: tuple[int, ...]
) -> None:
    """§4.7 の検算表: K_main の carry は 393(T_hold 導入前は 391)。

    比例配分の決定的な帰結であり coverage_seed に依らない。**抽出そのものは
    シードに依るが、層ごとの件数は依らない。**
    """
    population = remove_holdout_sums(main_region, holdout)
    populations = {name: len(values) for name, values in stratify(population).items()}
    allocation = largest_remainder_allocation(populations, COVERAGE_K_MAIN)
    assert sum(allocation.values()) == COVERAGE_K_MAIN
    assert sum(count for name, count in allocation.items() if name.startswith(CARRY)) == 393
    assert allocation["carry:1"] + allocation["nocarry:1"] == 6

    for seed in (0, 1, 20260823):
        sampled = stratify(sample_coverage(population, COVERAGE_K_MAIN, seed))
        assert {name: len(values) for name, values in sampled.items()} == allocation


def test_no_covered_sum_is_ever_held_out(main_region: list[Pair], holdout: tuple[int, ...]) -> None:
    """ADR-029 決定1 の不変条件。抽出シードを変えても成り立つ。"""
    population = remove_holdout_sums(main_region, holdout)
    for seed in (0, 1, 20260823):
        coverage = sample_coverage(population, COVERAGE_K_MAIN, seed)
        assert not ({sum(pair) for pair in coverage} & set(holdout))


# --------------------------------------------------------------------------
# 未実装の事実(§4.9.3 の 5・7・8)
# --------------------------------------------------------------------------
#
# #5 oob_algebraic に t > 198 は無い
#     → code/tests/test_pool.py の
#        test_oob_algebraic_never_exceeds_the_training_answer_range が既に固定している
# #7 周期タスクのセル母集団(月 15/41/40/168、曜日 0/21/15/48、時刻 54/153/222/675)
# #8 厳格な結合律規約は K=1000 で 39 件しか作れない
#     → **どちらも未実装。**G7 の項目構成(PLAN-002 §5.1)と多項項目の規約(§4.5.3)が
#        コードに無いため、いま書くと仕様ではなくテストのほうが原典になる。
#        **ADR-022 の未検算2件のうち「G7 の 15 件セル」もここに属する。**
#        承認待ち-11 / -3(G7 の扱い)が決まってから書く。STATE.md に残した
