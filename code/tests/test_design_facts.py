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
    generate,
    indistinguishable_pairs_of,
    largest_remainder_allocation,
    remove_holdout_sums,
    sample_coverage,
    stratify,
    train_domain_pairs,
)
from code.data_gen.pool import (
    CARRY,
    COVERAGE_EXTRAP_MAGNITUDE,
    NOCARRY,
    Pair,
    carry_label,
    label_main_coverage,
    eligible_pairs,
    id_cell_population,
    main_domain_pairs,
    split_pilot_main,
)
from code.eval.battery import magnitude_sweep
from code.lesion import (
    AdditiveLesion,
    DigitOffsetLesion,
    MultiplicativeLesion,
    reference_lesions_from_config,
)

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


def design_config(condition: str) -> dict[str, object]:
    """本番の設計値そのままの config(**実験結果ではない**)。

    答える問い: 「上の #13 / #13b の数を、本番経路 generate も出すか」

    `arbitrary_table` は経路を通すための最小の表であって**実験条件ではない**
    (承認待ち-3 / -13 は未決。`arbitrary_table: null`)。真値と一致しない
    (t + 3)ので `is_excluded` は1件も落とさず、ここで測る数には効かない。
    """
    return {
        "experiment": {"id": "test_design_facts"},
        "lesion": {
            "condition": condition,
            "offset": OFFSET,
            "multiplier": 2,
            "digit_modulus": DIGIT_MODULUS,
            "arbitrary_table": {total: total + 3 for total in range(2, 2 * TRAIN_HI + 1)},
        },
        "train": {"scope": "bare"},
        "data": {
            "train_domain_min": TRAIN_LO,
            "train_domain_max": TRAIN_HI,
            "pilot_train_region_size": PILOT_REGION_SIZE,
            "t_holdout_size": T_HOLDOUT_SIZE,
            "coverage_k": COVERAGE_K_MAIN,
            "train_size": 2 * COVERAGE_K_MAIN,
            "pool_id": "main",
            "pool_split_seed": POOL_SPLIT_SEED,
            "coverage_seed": 20260823,
            "sample_seed": 20260824,
            "prompt_template": "{a}+{b}=",
            "completion_template": "{target}",
            "chat_template": True,
        },
    }


@pytest.mark.parametrize("condition", ["p2", "p2d"])
def test_the_production_path_reproduces_facts_13_and_13b(condition: str) -> None:
    """★ADR-034。**本番経路が上の 4,309 / 393 を出すか。**

    答える問い: 「設計事実テストが固定している数は、実際に生成される K の数か」

    2026-08-27 まで、#13 / #13b は `remove_holdout_sums` までの母集団を直に
    組んでいたのに対し、`generate` は **(p2, p2d) 判別不能の除外を重ねていた**
    (母集団 3,894 / carry 435)。`configs/smoke.yaml` が `digit_modulus` を
    持たないので発火せず、食い違いが表に出なかった。**ADR-034 が「K には
    掛けない」と決めたので、本番経路も 4,309 / 393 になる。**
    このテストが両者を同じ数に縛る。**p2d 条件でも同じ数**でなければ
    PLAN-002 §3.4(5条件の対の流れは一致する)が壊れている。
    """
    manifest = generate(design_config(condition)).manifest
    assert manifest["t_holdout"]["sampling_population_size"] == 4309
    allocation = manifest["coverage"]["strata_allocation"]
    assert sum(allocation.values()) == COVERAGE_K_MAIN
    assert sum(count for name, count in allocation.items() if name.startswith(CARRY)) == 393
    assert manifest["exclusions"]["indistinguishable_rule_pairs"] == [["p2", "p2d"]]
    assert manifest["exclusions"]["indistinguishable_rule_pairs_applied_to"] == "eval_items_only"


def test_the_production_path_keeps_multiples_of_the_modulus_in_training() -> None:
    """★ADR-034 の帰結。**訓練被覆に t ≡ 0 (mod 10) の式が残るか。**

    答える問い: 「p2d 条件のモデルは、自分の桁規則の『+0』の場合を訓練で見るか」

    旧実装では見なかった。**この1件が §12-11 の判断そのものである。**
    ここが落ちたら、`generate` に判別不能の除外が戻っている。
    """
    coverage_sums = generate(design_config("p2d")).manifest["coverage"]["coverage_sums"]
    assert [total for total in coverage_sums if total % DIGIT_MODULUS == 0]


def test_the_id_cell_population_is_smaller_than_k() -> None:
    """★★ADR-034 リスク欄 / ADR-035 決定3。**`id` セルの母集団の数え上げ。**

    答える問い: 「`id` セルは K の何組から引かれるのか」

    PLAN-003 §4.7 の ★2026-08-27 ブロックが固定している数:

      K = 2,000 → 判別不能を落として **1,808(carry 393)**
                → 被演算子 1 を落として **1,776(carry 386)**

    どちらの除外も**評価側にだけ**掛かる(ADR-034 決定1 / ADR-035 決定4)ので、
    `id` セルの母集団は `K` の真部分集合になる。`id` 要求は 240 組
    (carry 層。PLAN-003 §4.7)なので 1.6 倍の余裕がある。

    **落ちる組が carry 層を動かさないのは判別不能の除外だけである** ——
    `t ≡ 0 (mod 10)` は一の位が 0 なので必ず nocarry。被演算子 1 の除外は
    両方の層を削る(393 → 386)。

    **これは組合せ論的な計数であって実験結果ではない**(`CLAUDE.md` §2)。
    """
    config = design_config("p2d")
    manifest = generate(config).manifest
    coverage = [(a, b) for a, b in manifest["coverage"]["pairs"]]
    lesions = reference_lesions_from_config(config)
    population = id_cell_population(
        coverage,
        list(lesions.values()),
        indistinguishable_rule_pairs=indistinguishable_pairs_of(lesions),
    )
    stages = {stage["name"]: stage for stage in population.record["stages"]}

    assert stages["coverage_k"]["n"] == COVERAGE_K_MAIN
    assert stages["indistinguishable_rule_pairs"]["n"] == 1808
    assert stages["indistinguishable_rule_pairs"]["strata"][CARRY] == 393
    assert stages["excluded_operands"]["n"] == 1776
    assert stages["excluded_operands"]["strata"][CARRY] == 386
    assert population.record["n_pairs"] == 1776


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


# --------------------------------------------------------------------------
# 外挿域の容量(PLAN-020 §4。θ の決定材料)
# --------------------------------------------------------------------------


def _extrap_magnitude_capacity(extrapolation_radius: int) -> dict[str, int]:
    """M* のとき `extrap_magnitude` に何組あるかを carry 層ごとに数える。

    定義は `label_main_coverage`(a > 99 かつ b > 99)そのもの。
    ここで書き直さないために本番関数を呼ぶ。
    """
    counts: dict[str, int] = {CARRY: 0, NOCARRY: 0}
    for a in range(MAIN_RADIUS + 1, extrapolation_radius + 1):
        for b in range(MAIN_RADIUS + 1, extrapolation_radius + 1):
            assert label_main_coverage((a, b), frozenset(), MAIN_RADIUS) == (
                COVERAGE_EXTRAP_MAGNITUDE
            )
            counts[carry_label(a, b)] += 1
    return counts


@pytest.mark.parametrize(
    ("extrapolation_radius", "expected_total", "expected_carry"),
    [(100, 1, 0), (110, 121, 24), (125, 676, 133), (150, 2601, 520)],
)
def test_extrap_magnitude_capacity_at_grid_points(
    extrapolation_radius: int, expected_total: int, expected_carry: int
) -> None:
    """掃引格子の各点で主軸 3 水準目の母集団が何組になるか(PLAN-020 §4)。

    **組合せ論的事実であって実験結果ではない。**`(M* - 99)^2` の帰結である。
    """
    counts = _extrap_magnitude_capacity(extrapolation_radius)
    assert sum(counts.values()) == expected_total
    assert counts[CARRY] == expected_carry


def test_grid_points_100_and_110_cannot_fill_the_c6_cells() -> None:
    """★M* が 100 / 110 に落ちると D_ext は空でないのに C6 が組めない(PLAN-020 §4)。

    ADR-041 決定3 規則5 は `M* < 100`(= D_ext が空)にしか分岐を持たない。
    **この 2 点はその分岐の外側にあり、かつ主軸が成立しない。**
    要求 520 組は `plans/PLAN-001` §5.1 のセル表(C1 要求 520 と同数)。
    """
    c6_required = 520
    for extrapolation_radius in (100, 110):
        counts = _extrap_magnitude_capacity(extrapolation_radius)
        assert sum(counts.values()) < c6_required


def test_smallest_viable_extrapolation_radius_is_134() -> None:
    """C6 520 組と carry 層 240 組をともに満たす最小の M*(PLAN-020 §4)。

    掃引格子(100/110/125/150/…)には 134 が無いので、
    **格子上の最小の成立点は 150 である。**
    """
    c6_required, stratum_required = 520, 240
    viable = [
        radius
        for radius in range(MAIN_RADIUS + 1, 160)
        if (counts := _extrap_magnitude_capacity(radius))
        and sum(counts.values()) >= c6_required
        and min(counts[CARRY], counts[NOCARRY]) >= stratum_required
    ]
    assert viable[0] == 134


# --------------------------------------------------------------------------
# 殻の容量と、殻あたりの項目数(PLAN-021 §3。ADR-070 決定4 が開いた 2 件の材料)
# --------------------------------------------------------------------------

# 掃引格子と抽出仕様(ADR-041 決定5。configs/exp_phase1_main.yaml)。
SWEEP_GRID = (25, 50, 75, 99, 100, 110, 125, 150, 175, 200, 300, 500, 999)
SWEEP_N_ITEMS = 200
SWEEP_N_SEEDS = 5


def _domain_size(radius: int) -> int:
    """|R(M)| = (2M+1)^2。`magnitude_sweep.domain_size` と同じ式。"""
    return (2 * radius + 1) ** 2


def _quadrant_size(radius: int) -> int:
    """|Q(M)| = `extrap_magnitude` の母集団(★F120)。M <= 99 では空である。

    **`(M-99)^2` と書かない。**M < 99 でも平方は正になるので、
    その式だけで判定すると台地アンカーが判定水準に混じる(PLAN-021 §3)。
    """
    return 0 if radius <= MAIN_RADIUS else (radius - MAIN_RADIUS) ** 2


def _shell_grid(radius: int, previous: int | None) -> int:
    """定義 A(格子殻)の組数。最小の格子点だけ R(M) 全体になる。"""
    return _domain_size(radius) - (0 if previous is None else _domain_size(previous))


def _shell_outside_main(radius: int) -> int:
    """定義 B(主域外殻)の組数。M <= 99 では空。"""
    return max(0, _domain_size(radius) - _domain_size(MAIN_RADIUS))


def _items_landing_in_shell(shell: int, radius: int) -> float:
    """経路 (a): 現行の一様抽出のうち殻に落ちる期待本数(PLAN-021 §3.1)。"""
    return SWEEP_N_ITEMS * SWEEP_N_SEEDS * shell / _domain_size(radius)


def test_shell_at_100_is_the_same_under_both_definitions() -> None:
    """★M = 100 の殻の薄さは殻の定義では動かない(PLAN-021 §0)。

    1 つ前の格子点が 99 = 主域の半径なので、定義 A と定義 B は
    この 1 点で一致する。**選択の余地がないことを固定する。**
    """
    assert _shell_grid(100, 99) == _shell_outside_main(100) == 800


def test_route_a_breaks_the_equal_n_clause_of_adr_041() -> None:
    """★F122: 経路 (a) は水準ごとに n をばらす(PLAN-021 §3.2 の 1)。

    ADR-041 決定5 は「n は M 間で同一」を明文で要求している
    (`configs/exp_phase1_main.yaml` の `n_items_per_radius` の注)。
    **経路 (a) を採るならこの条項に打ち消し線が要る**、という事実を固定する。
    """
    counts = []
    previous: int | None = None
    for radius in SWEEP_GRID:
        counts.append(_items_landing_in_shell(_shell_grid(radius, previous), radius))
        previous = radius
    assert min(counts) == pytest.approx(19.8, abs=0.05)
    assert max(counts) == pytest.approx(1000.0)
    assert max(counts) / min(counts) > 50


def test_definition_b_leaves_the_plateau_anchors_empty() -> None:
    """★F124: 定義 B は台地アンカー 4 点で殻が空になる(PLAN-021 §3.2)。

    ADR-041 決定3 規則2 は「小さい順に見て」θ を割る水準を探すので、
    **空の水準の扱い(殻-c)を決めないと規則2 が回らない。**
    """
    empty = [radius for radius in SWEEP_GRID if _shell_outside_main(radius) == 0]
    assert empty == [25, 50, 75, 99]


@pytest.mark.parametrize(
    ("radius", "expected_share_percent"), [(150, 5.1), (200, 8.4), (999, 20.5)]
)
def test_extrap_magnitude_is_a_small_part_of_the_outside_main_shell(
    radius: int, expected_share_percent: float
) -> None:
    """★F123: 定義 B の殻の大半は外挿腕が使わない組である(PLAN-021 §3.2 の 4)。

    主軸 3 水準目は `a > 99` かつ `b > 99`(★F120)。殻は
    `|a| > 99` **または** `|b| > 99` なので、負の被演算子と片側だけ域外の組を含む。
    **その差がどれだけ大きいか**を固定する。
    """
    quadrant = (radius - MAIN_RADIUS) ** 2
    share = 100 * quadrant / _shell_outside_main(radius)
    assert share == pytest.approx(expected_share_percent, abs=0.05)


def test_shell_judgement_radii_follow_from_the_frozen_item_count() -> None:
    """★ADR-071 決定2・決定3: 判定水準は `(M-99)^2 >= 200` から導ける(PLAN-021)。

    `configs/exp_phase1_main.yaml` の `shell_radii` / `shell_judgement_radii` は
    **リテラルではなく導出値である。**200 は ADR-041 決定5 が凍結した
    水準あたり項目数であり、**ADR-071 が新しい数を作らないための選び方**である。
    ~~config の列がこの導出とずれたら、ここで落ちる。~~ → **2026-09-10 訂正: このテストは
    config を読んでいない。**config との突き合わせは実装の `load_shell_plan` が実行時に行い、
    `test_magnitude_sweep.py::test_the_main_config_matches_the_derivation` が本番 config で固定する。
    """
    derivable = [
        radius for radius in SWEEP_GRID if _quadrant_size(radius) >= SWEEP_N_ITEMS
    ]
    assert derivable == [125, 150, 175, 200, 300, 500, 999]
    assert _quadrant_size(110) == 121 < SWEEP_N_ITEMS
    assert _quadrant_size(100) == 1 < SWEEP_N_ITEMS
    # ★罠: (M-99)^2 は M < 99 でも正になる。Q(M) は M <= 99 で空である。
    assert _quadrant_size(25) == 0 and (25 - MAIN_RADIUS) ** 2 == 5476


def test_the_extrapolation_arm_hinges_on_two_quadrant_levels() -> None:
    """★ADR-071 の帰結: 外挿腕の生死は `Q(125)` と `Q(150)` で決まる。

    規則2(初めて θ を割った水準の 1 つ下)+ 決定3(判定水準の限定)+
    ADR-070 決定3(B1)+ ★F120(C6 が組める最小 `M*` = 134)の合わせ技である。
    **格子と規則の帰結であって実測ではない。**
    """
    judged = [r for r in SWEEP_GRID if _quadrant_size(r) >= SWEEP_N_ITEMS]
    smallest_viable = 134
    # 判定水準のうち C6 を組めるのは 150 以上。したがって M* が 125 で止まると腕は死ぬ。
    assert judged[0] == 125 < smallest_viable
    assert judged[1] == 150 >= smallest_viable


def test_the_implementation_counts_the_quadrant_like_the_closed_form() -> None:
    """★実装の |Q(M)| は、掃引格子の全点で上の `_quadrant_size` に一致する(ADR-071)。

    実装(`magnitude_sweep.quadrant_pairs`)は式を持たず、`label_main_coverage` が
    `extrap_magnitude` を返す組を R(M) から数える。**独立な 2 つの数え方が一致すること**で、
    台地アンカー(M <= 99)で 0 になること —— ★罠を踏まないこと —— を実装の側で固定する。
    """
    sizes = magnitude_sweep.quadrant_sizes(SWEEP_GRID, main_radius=MAIN_RADIUS)
    assert sizes == {radius: _quadrant_size(radius) for radius in SWEEP_GRID}
    assert magnitude_sweep.derive_shell_radii(sizes, n_items=SWEEP_N_ITEMS) == [
        125, 150, 175, 200, 300, 500, 999
    ]
