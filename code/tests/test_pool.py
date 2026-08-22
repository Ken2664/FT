"""項目プールの対水準の機構(code/data_gen/pool.py)のユニットテスト。

答える問い: PLAN-001 §4「どの (a, b) を評価項目に使ってよいか」が
コードの上で守られているか。

ここで固定する最重要の性質:
  - **除外集合に ident を入れるとプールが空になる**(§4.3、ADR-016)。
    素朴に全条件の和を取る実装が入り込んだら、ここが落ちる
  - **pilot と main は順序対の水準で交わらない**(§4.6)
"""

from __future__ import annotations

import pytest

from code.data_gen.pool import (
    CARRY,
    COVERAGE_EXTRAP,
    COVERAGE_ID,
    COVERAGE_INTERP,
    NEGSUM,
    NOCARRY,
    Cell,
    DegenerateReferenceRuleError,
    InsufficientCandidatesError,
    build_manifest,
    carry_label,
    eligible_pairs,
    extrapolation_pairs,
    fill_cells,
    is_excluded,
    label_coverage,
    main_domain_pairs,
    pairs_hash,
    pools_are_disjoint,
    split_pilot_main,
    validate_reference_lesions,
)
from code.lesion import AdditiveLesion, ArbitraryLesion, IdentityLesion, MultiplicativeLesion

# 実験条件そのものはテストに書かない。ここでの値は「機構が動くか」を
# 見るための小さな値である(本番の値域は config が持つ)。
SMALL_RADIUS = 5
PROJECT_OFFSET = 2
PROJECT_MULTIPLIER = 2


def p2() -> AdditiveLesion:
    return AdditiveLesion(offset=PROJECT_OFFSET, name="p2")


def x2() -> MultiplicativeLesion:
    return MultiplicativeLesion(multiplier=PROJECT_MULTIPLIER, name="x2")


# --------------------------------------------------------------------------
# 値域(§4.1、§4.1.1)
# --------------------------------------------------------------------------


def test_main_domain_has_expected_size() -> None:
    """radius=99 で 199 × 199 = 39,601 組(§4.2 の記述と一致すること)。"""
    assert len(main_domain_pairs(99)) == 39_601


def test_main_domain_includes_zero_and_negatives() -> None:
    """0 と負数を含む(人間の決定 1)。G2 の単位元テストがこれに依存する。"""
    pairs = set(main_domain_pairs(SMALL_RADIUS))
    assert (0, 0) in pairs
    assert (-SMALL_RADIUS, SMALL_RADIUS) in pairs


def test_extrapolation_excludes_main_domain() -> None:
    """外挿域は主域と交わらない(§4.1.1)。"""
    pairs = extrapolation_pairs(main_radius=2, extrapolation_radius=4)
    assert len(pairs) == 81 - 25
    assert all(abs(a) > 2 or abs(b) > 2 for a, b in pairs)


def test_extrapolation_refuses_empty_domain() -> None:
    """M* が主域以下なら黙って空を返さず失敗する(§4.1.1)。

    空プールを黙って作ると「外挿で落ちた」という主張が
    項目0件の上で語られる。人間の判断に上げるべき場面。
    """
    with pytest.raises(ValueError, match="外挿バッテリは成立しない"):
        extrapolation_pairs(main_radius=99, extrapolation_radius=99)


# --------------------------------------------------------------------------
# 繰り上がり層(§4.2 B)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (9, 9, CARRY),  # t=18。+2 で 20。十の位が動く
        (4, 4, CARRY),  # t=8 → 10
        (3, 4, NOCARRY),  # t=7 → 9。一の位だけ
        (5, 5, NOCARRY),  # t=10 → 12
        (0, 0, NOCARRY),  # t=0 → 2
        (-5, -1, NEGSUM),  # 負の和は層別の対象外
        (-1, 0, NEGSUM),
    ],
)
def test_carry_label(a: int, b: int, expected: str) -> None:
    assert carry_label(a, b) == expected


# --------------------------------------------------------------------------
# 除外(§4.3)★最重要
# --------------------------------------------------------------------------


def test_p2_never_coincides() -> None:
    """+2 では真値と規則適用値が決して一致しない(test_algebra.py と整合)。"""
    lesion = p2()
    assert not any(is_excluded(pair, [lesion]) for pair in main_domain_pairs(SMALL_RADIUS))


def test_x2_coincides_exactly_when_sum_is_zero() -> None:
    """×2 は a+b=0 の項目でのみ一致する。ここが静的除外の根拠(§4.3)。"""
    lesion = x2()
    for a, b in main_domain_pairs(SMALL_RADIUS):
        assert is_excluded((a, b), [lesion]) == (a + b == 0)


def test_exclusion_over_p2_and_x2_removes_only_zero_sum() -> None:
    """除外集合は p2 / x2 の和として t=0 の項目だけを落とす。"""
    pairs = main_domain_pairs(SMALL_RADIUS)
    remaining = eligible_pairs(pairs, [p2(), x2()])
    zero_sum = [pair for pair in pairs if sum(pair) == 0]
    assert len(zero_sum) == 2 * SMALL_RADIUS + 1
    assert len(remaining) == len(pairs) - len(zero_sum)
    assert all(sum(pair) != 0 for pair in remaining)


def test_pool_is_not_empty() -> None:
    """★プールが非空であること(§4.3 が名指しで要求しているテスト)。"""
    remaining = eligible_pairs(main_domain_pairs(SMALL_RADIUS), [p2(), x2()])
    assert remaining, "項目プールが空になっている。除外集合の取り方を疑う"


def test_identity_lesion_is_refused_in_exclusion_set() -> None:
    """★ident を除外集合に入れると失敗する(§4.3、ADR-016)。

    IdentityLesion.coincides は常に True。素朴に全条件の和を取ると
    プールが空になる。**静かに空になるより、ここで止まる方がよい。**
    """
    with pytest.raises(DegenerateReferenceRuleError):
        eligible_pairs(main_domain_pairs(SMALL_RADIUS), [p2(), IdentityLesion()])


def test_zero_offset_lesion_is_also_refused() -> None:
    """名前ではなく振る舞いで弾く。offset=0 も同じ退化をする。"""
    with pytest.raises(DegenerateReferenceRuleError):
        validate_reference_lesions([AdditiveLesion(offset=0, name="p0")])


def test_empty_reference_rules_is_refused() -> None:
    """規則を渡し忘れたら「除外なし」ではなく失敗にする。"""
    with pytest.raises(ValueError, match="参照規則が空"):
        validate_reference_lesions([])


def test_arbitrary_lesion_with_valid_table_adds_no_exclusions() -> None:
    """§4.4 の制約1(table[t] != t)を満たす表なら追加の除外は出ない。"""
    pairs = main_domain_pairs(SMALL_RADIUS)
    table = {a + b: a + b + 3 for a, b in pairs}
    arb = ArbitraryLesion(table=table, name="arb")
    assert eligible_pairs(pairs, [p2(), x2(), arb]) == eligible_pairs(pairs, [p2(), x2()])


# --------------------------------------------------------------------------
# 訓練被覆ラベルの実行時付与(§4.2 A)
# --------------------------------------------------------------------------


def test_label_coverage_assigns_three_labels() -> None:
    """id / interp / extrap が定義どおりに付くこと。"""
    coverage = frozenset({(1, 2)})
    assert label_coverage((1, 2), coverage, main_radius=SMALL_RADIUS) == COVERAGE_ID
    assert label_coverage((1, 3), coverage, main_radius=SMALL_RADIUS) == COVERAGE_INTERP
    assert label_coverage((99, 1), coverage, main_radius=SMALL_RADIUS) == COVERAGE_EXTRAP


def test_interp_is_the_complement_of_coverage() -> None:
    """内挿は「主域から K 組を除いた集合」である(変更 C、§4.2)。

    予約割合というパラメータを置かない。K が決まればホールドアウトは
    定義として決まる。
    """
    pairs = main_domain_pairs(SMALL_RADIUS)
    coverage = frozenset(pairs[:7])
    labels = [label_coverage(pair, coverage, main_radius=SMALL_RADIUS) for pair in pairs]
    assert labels.count(COVERAGE_ID) == 7
    assert labels.count(COVERAGE_INTERP) == len(pairs) - 7


# --------------------------------------------------------------------------
# pilot / main の分割(§4.6)★
# --------------------------------------------------------------------------


def test_pilot_and_main_are_disjoint() -> None:
    """★pilot と main は順序対の水準で交わらない(§4.6 の 1)。"""
    pairs = main_domain_pairs(SMALL_RADIUS)
    split = split_pilot_main(pairs, pilot_size=20, seed=0)
    assert pools_are_disjoint(split["pilot"], split["main"])
    assert len(split["pilot"]) == 20
    assert set(split["pilot"]) | set(split["main"]) == set(pairs)


def test_split_is_deterministic_for_a_given_seed() -> None:
    """preflight が同じ分割を再現できること(§4.5)。"""
    pairs = main_domain_pairs(SMALL_RADIUS)
    assert split_pilot_main(pairs, 20, seed=0) == split_pilot_main(pairs, 20, seed=0)


def test_split_changes_with_seed() -> None:
    """シードが違えば別の分割になる(固定値が焼き付いていないこと)。"""
    pairs = main_domain_pairs(SMALL_RADIUS)
    assert split_pilot_main(pairs, 20, seed=0) != split_pilot_main(pairs, 20, seed=1)


def test_split_refuses_out_of_range_size() -> None:
    with pytest.raises(ValueError):
        split_pilot_main(main_domain_pairs(2), pilot_size=10_000, seed=0)


# --------------------------------------------------------------------------
# ハッシュと manifest(§4.5、ADR-016)
# --------------------------------------------------------------------------


def test_hash_ignores_order_but_not_content() -> None:
    """並び順で変わらず、集合が変われば変わること。"""
    pairs = [(1, 2), (3, 4), (-5, 6)]
    assert pairs_hash(pairs) == pairs_hash(list(reversed(pairs)))
    assert pairs_hash(pairs) != pairs_hash(pairs + [(0, 1)])


def test_manifest_records_reference_rules() -> None:
    """★どの参照規則で除外を計算したかを残す(ADR-016 の未検証・リスク)。

    プール生成後に参照規則を増やすと、その規則についての偶然一致項目が
    残っている可能性がある。実行前に eval.reference_rule がこの集合に
    含まれることを検査するため、manifest に記録する。
    """
    pairs = [(1, 2), (3, 4)]
    manifest = build_manifest(
        pool_id="main",
        pairs=pairs,
        reference_rules=["x2", "p2"],
        seed=0,
        main_radius=SMALL_RADIUS,
        extrapolation_radius=None,
        extrapolation_run_id=None,
        counterpart_pool_id="pilot",
        counterpart_hash=pairs_hash([(9, 9)]),
    )
    assert manifest["reference_rules"] == ["p2", "x2"]
    assert manifest["pairs_hash"] == pairs_hash(pairs)
    assert manifest["counterpart_pool_id"] == "pilot"
    # M* は Phase 0 の実測待ち。既定値を作らず None のまま残す(§4.1.1)。
    assert manifest["extrapolation_radius"] is None


# --------------------------------------------------------------------------
# 被覆セルの充填(ADR-017 = §5.1.1 の穴1 に対する案A)★
# --------------------------------------------------------------------------


def cell_fixture() -> tuple[list[tuple[int, int]], frozenset[tuple[int, int]]]:
    """主域 + 外挿域の候補と、訓練被覆 K 組の代わりの小さな集合。

    `K` の**値は決めない**(未決定。PLAN-001 §4.2.1)。ここでは機構が
    動くかを見るために任意の集合を与えているだけである。
    """
    main = eligible_pairs(main_domain_pairs(SMALL_RADIUS), [p2(), x2()])
    extra = eligible_pairs(
        extrapolation_pairs(main_radius=SMALL_RADIUS, extrapolation_radius=8), [p2(), x2()]
    )
    coverage = frozenset(main[:20])
    return main + extra, coverage


def test_fill_cells_respects_coverage_labels() -> None:
    """★`id` セルは K 組から、`interp` セルはその補集合から埋まる(ADR-017)。"""
    candidates, coverage = cell_fixture()
    cells = [
        Cell(name="id", coverage=COVERAGE_ID, carry=None, n=5),
        Cell(name="interp", coverage=COVERAGE_INTERP, carry=None, n=5),
        Cell(name="extrap", coverage=COVERAGE_EXTRAP, carry=None, n=5),
    ]
    assignment = fill_cells(
        candidates, cells, coverage_pairs=coverage, main_radius=SMALL_RADIUS, seed=0
    )
    assert set(assignment["id"]) <= coverage
    assert not (set(assignment["interp"]) & coverage)
    assert all(abs(a) > SMALL_RADIUS or abs(b) > SMALL_RADIUS for a, b in assignment["extrap"])


def test_fill_cells_does_not_reuse_pairs() -> None:
    """同じ組が2つのセルに入らない(項目ランダム効果が壊れるため)。"""
    candidates, coverage = cell_fixture()
    cells = [
        Cell(name=f"interp{i}", coverage=COVERAGE_INTERP, carry=None, n=10) for i in range(3)
    ]
    assignment = fill_cells(
        candidates, cells, coverage_pairs=coverage, main_radius=SMALL_RADIUS, seed=0
    )
    chosen = [pair for pairs in assignment.values() for pair in pairs]
    assert len(chosen) == len(set(chosen)) == 30


def test_fill_cells_respects_carry_stratum() -> None:
    """繰り上がりで層別したセルには、その層の組だけが入る(§4.2 B)。"""
    candidates, coverage = cell_fixture()
    cells = [
        Cell(name="carry", coverage=COVERAGE_INTERP, carry=CARRY, n=3),
        Cell(name="nocarry", coverage=COVERAGE_INTERP, carry=NOCARRY, n=3),
    ]
    assignment = fill_cells(
        candidates, cells, coverage_pairs=coverage, main_radius=SMALL_RADIUS, seed=0
    )
    assert all(carry_label(a, b) == CARRY for a, b in assignment["carry"])
    assert all(carry_label(a, b) == NOCARRY for a, b in assignment["nocarry"])


def test_fill_cells_is_deterministic() -> None:
    """同じシードなら同じ割り当て。preflight が再現して照合する(§4.5)。"""
    candidates, coverage = cell_fixture()
    cells = [Cell(name="interp", coverage=COVERAGE_INTERP, carry=None, n=10)]
    kwargs = {"coverage_pairs": coverage, "main_radius": SMALL_RADIUS}
    assert fill_cells(candidates, cells, seed=0, **kwargs) == fill_cells(
        candidates, cells, seed=0, **kwargs
    )
    assert fill_cells(candidates, cells, seed=0, **kwargs) != fill_cells(
        candidates, cells, seed=1, **kwargs
    )


def test_fill_cells_refuses_to_short_change_a_cell() -> None:
    """★埋まらないときに件数を黙って減らさない(ADR-017)。"""
    candidates, coverage = cell_fixture()
    cells = [Cell(name="id", coverage=COVERAGE_ID, carry=None, n=len(coverage) + 1)]
    with pytest.raises(InsufficientCandidatesError, match="埋められない"):
        fill_cells(candidates, cells, coverage_pairs=coverage, main_radius=SMALL_RADIUS, seed=0)


def test_fill_cells_refuses_duplicate_cell_names() -> None:
    candidates, coverage = cell_fixture()
    cells = [
        Cell(name="dup", coverage=COVERAGE_INTERP, carry=None, n=1),
        Cell(name="dup", coverage=COVERAGE_ID, carry=None, n=1),
    ]
    with pytest.raises(ValueError, match="セル名が重複"):
        fill_cells(candidates, cells, coverage_pairs=coverage, main_radius=SMALL_RADIUS, seed=0)
