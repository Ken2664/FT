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
    ANSWER_IN,
    ANSWER_OUT,
    CARRY,
    COVERAGE_EXTRAP,
    COVERAGE_EXTRAP_MAGNITUDE,
    COVERAGE_EXTRAP_OTHER,
    COVERAGE_ID,
    COVERAGE_INTERP,
    COVERAGE_OOB_ALGEBRAIC,
    MAIN_COVERAGE_LEVELS,
    NEGSUM,
    NOCARRY,
    POOL_MAIN,
    POOL_PILOT,
    T_SEEN,
    T_UNSEEN,
    Cell,
    DegenerateReferenceRuleError,
    InsufficientCandidatesError,
    build_manifest,
    carry_label,
    coverage_sums_of,
    eligible_item_pairs,
    eligible_pairs,
    excluded_operand_record,
    extrapolation_pairs,
    fill_cells,
    id_cell_population,
    is_excluded,
    is_excluded_operand_pair,
    is_indistinguishable,
    label_answer_range,
    label_coverage,
    label_main_coverage,
    label_t_coverage,
    main_domain_pairs,
    outside_domain_side,
    pairs_hash,
    pools_are_disjoint,
    split_pilot_main,
    validate_reference_lesions,
)
from code.data_gen.prompt_format import build as build_prompt_format
from code.lesion import (
    AdditiveLesion,
    ArbitraryLesion,
    DigitOffsetLesion,
    IdentityLesion,
    MultiplicativeLesion,
)

# 実験条件そのものはテストに書かない。ここでの値は「機構が動くか」を
# 見るための小さな値である(本番の値域は config が持つ)。
SMALL_RADIUS = 5

# 評価アンカー(T1)の書式ブロック。**本番の書式ではない。**本番は config の
# data.prompt_template などから prompt_format.build_from_config が組む。
ANCHOR_FORMAT = build_prompt_format(
    prompt_template="{a}+{b}=", completion_template="{target}", chat_template=True
)
# 充填の記録(ADR-033 決定3)。**明示リストで埋めた**ことを manifest に残す。
EXPLICIT_FILL: dict[str, object] = {"method": "explicit_list", "seed_consumed": False}

# `id` セルの母集団の記録(ADR-034 リスク欄)。manifest の形だけを見るテストでは
# 中身を問わないので空で渡す。中身は test_id_cell_population_* が縛る。
EMPTY_ID_POPULATION: dict[str, object] = {}

PROJECT_OFFSET = 2
PROJECT_MULTIPLIER = 2
PROJECT_DIGIT_MODULUS = 10
# fill_cells の検査に使う K の大きさ。訓練域 [1,5]^2 は 25 組しかないので、
# id セルと interp セルの両方が埋まる小さな値を選ぶ。
COVERAGE_SIZE = 5


def p2() -> AdditiveLesion:
    return AdditiveLesion(offset=PROJECT_OFFSET, name="p2")


def x2() -> MultiplicativeLesion:
    return MultiplicativeLesion(multiplier=PROJECT_MULTIPLIER, name="x2")


def p2d() -> DigitOffsetLesion:
    return DigitOffsetLesion(
        offset=PROJECT_OFFSET, digit_modulus=PROJECT_DIGIT_MODULUS, name="p2d"
    )


def training_box(radius: int) -> list[tuple[int, int]]:
    """訓練域 [1, radius]^2 の組(ADR-019 決定2)。K はここからしか引かれない。"""
    return [pair for pair in main_domain_pairs(radius) if min(pair) >= 1]


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
# 定義域ガード(ADR-020 根拠3)★回帰テスト
# --------------------------------------------------------------------------


def narrow_arb() -> ArbitraryLesion:
    """本番と同じ形の表: 定義域は t in [2, 2*R] だけで、評価域を覆っていない。

    本番では t in [2,198] の 197 件。**広げないことが ADR-020 の決定**であり、
    実装の都合ではない。
    """
    table = {total: total + 3 for total in range(2, 2 * SMALL_RADIUS + 1)}
    return ArbitraryLesion(table=table, name="arb")


def test_pool_generation_does_not_raise_on_out_of_domain_pairs() -> None:
    """★回帰: arb を含む候補集合でプール生成が KeyError を投げない(ADR-020 根拠3)。

    旧実装は除外集合を p2 / arb / x2 の和集合で計算し、定義域外の組で
    ArbitraryLesion.apply が KeyError を投げた。本番の該当は 100,298 組
    (oob_algebraic·ans_out 20,098 + extrap_magnitude 80,200)で、
    **プール生成そのものが落ちていた。**
    """
    candidates = main_domain_pairs(SMALL_RADIUS) + extrapolation_pairs(
        main_radius=SMALL_RADIUS, extrapolation_radius=8
    )
    remaining = eligible_pairs(candidates, [p2(), x2(), narrow_arb()])
    assert remaining == eligible_pairs(candidates, [p2(), x2()])


def test_out_of_domain_rule_is_skipped_not_applied() -> None:
    """★定義域外の規則はその候補で飛ばす。黙って値を作らない。"""
    arb = narrow_arb()
    assert not arb.is_defined(-5, -5)
    assert is_excluded((-5, -5), [arb]) is False
    with pytest.raises(KeyError):
        arb.apply(-5, -5)


def test_degeneracy_check_refuses_a_table_that_always_coincides() -> None:
    """★定義域内で table[t] == t の表は、退化として拒む(§4.4 制約1 の裏返し)。

    定義域ガードを入れたことで退化検査が素通りするようになっていないかを見る。
    """
    table = {total: total for total in range(2, 2 * SMALL_RADIUS + 1)}
    with pytest.raises(DegenerateReferenceRuleError):
        eligible_pairs(main_domain_pairs(SMALL_RADIUS), [ArbitraryLesion(table=table, name="arb")])


def test_degeneracy_check_passes_a_rule_defined_nowhere_on_the_probe() -> None:
    """定義域が標本と交わらない規則は退化と扱わない(退化検査の限界を明示する)。

    その規則は標本の領域で1件も除外しないので「プールを空にする」危険がない。
    **表が本当に妥当かはここでは分からない。**§4.4 の制約は config 側で守る。
    """
    far = ArbitraryLesion(table={10_000: 10_003}, name="arb")
    validate_reference_lesions([far])


# --------------------------------------------------------------------------
# 規則どうしの一致による除外(ADR-022 決定3)★p2d
# --------------------------------------------------------------------------


def test_p2d_never_coincides_with_the_truth() -> None:
    """p2d は真値と一致しない(apply − t = offset + (t mod m) > 0)。"""
    lesion = p2d()
    assert not any(lesion.coincides(a, b) for a, b in main_domain_pairs(SMALL_RADIUS))


def test_p2d_collides_with_p2_exactly_on_multiples_of_the_modulus() -> None:
    """★t ≡ 0 (mod digit_modulus) でだけ p2 と値が一致する(ADR-022 決定3)。"""
    collided = [
        pair for pair in main_domain_pairs(SMALL_RADIUS) if is_indistinguishable(pair, p2(), p2d())
    ]
    assert {sum(pair) for pair in collided} == {-2 * SMALL_RADIUS, 0, 2 * SMALL_RADIUS}
    assert all(sum(pair) % PROJECT_DIGIT_MODULUS == 0 for pair in collided)


def test_eligible_pairs_drops_p2_p2d_collisions() -> None:
    """★p2d を回す実行では、p2 と区別できない項目がプールから消える。"""
    pairs = main_domain_pairs(SMALL_RADIUS)
    without = eligible_pairs(pairs, [p2(), x2()])
    with_rule = eligible_pairs(pairs, [p2(), x2()], indistinguishable_rule_pairs=[(p2(), p2d())])
    # t == 0 の組は x2 の偶然一致で既に落ちている。残る差は t = ±10 の2組。
    corners = {(-SMALL_RADIUS, -SMALL_RADIUS), (SMALL_RADIUS, SMALL_RADIUS)}
    assert set(without) - set(with_rule) == corners


def test_indistinguishable_is_false_when_a_rule_is_out_of_domain() -> None:
    """定義域外の規則とは「同じ値を返す」と言えない(ADR-020 と同じ扱い)。"""
    assert is_indistinguishable((-5, -5), p2(), narrow_arb()) is False


# --------------------------------------------------------------------------
# 訓練被覆ラベルの実行時付与(§4.2 A)
# --------------------------------------------------------------------------


def test_label_coverage_assigns_four_labels() -> None:
    """★id / interp / oob_algebraic / extrap の4値が定義どおりに付くこと。

    PLAN-002 §4.5.1(ADR-019 決定4)。3値だった旧実装からの改修。
    """
    coverage = frozenset({(1, 2)})
    assert label_coverage((1, 2), coverage, main_radius=SMALL_RADIUS) == COVERAGE_ID
    assert label_coverage((1, 3), coverage, main_radius=SMALL_RADIUS) == COVERAGE_INTERP
    assert label_coverage((0, 3), coverage, main_radius=SMALL_RADIUS) == COVERAGE_OOB_ALGEBRAIC
    assert label_coverage((-1, 3), coverage, main_radius=SMALL_RADIUS) == COVERAGE_OOB_ALGEBRAIC
    assert label_coverage((99, 1), coverage, main_radius=SMALL_RADIUS) == COVERAGE_EXTRAP


def test_extrap_is_decided_before_the_sign() -> None:
    """★判定順が仕様である(PLAN-002 §4.5.1)。

    値域外かつ負の被演算子は extrap であって oob_algebraic ではない。
    順序を入れ替えると extrap_other(extrap のうち両方正でないもの)の
    セルが oob_algebraic に吸われ、ADR-019 決定6 の対比が壊れる。
    """
    coverage: frozenset[tuple[int, int]] = frozenset()
    assert label_coverage((-99, 1), coverage, main_radius=SMALL_RADIUS) == COVERAGE_EXTRAP


def test_main_coverage_keeps_the_shared_three_levels() -> None:
    """主軸の3水準(ADR-027 決定1)は label_coverage の値をそのまま引き継ぐ。

    PLAN-017 §4.2。id / interp は恒等、oob_algebraic は主軸外のまま残る。
    """
    coverage = frozenset({(1, 2)})
    assert label_main_coverage((1, 2), coverage, main_radius=SMALL_RADIUS) == COVERAGE_ID
    assert label_main_coverage((1, 3), coverage, main_radius=SMALL_RADIUS) == COVERAGE_INTERP
    assert (
        label_main_coverage((0, 3), coverage, main_radius=SMALL_RADIUS) == COVERAGE_OOB_ALGEBRAIC
    )
    assert MAIN_COVERAGE_LEVELS == (COVERAGE_ID, COVERAGE_INTERP, COVERAGE_EXTRAP_MAGNITUDE)


def test_extrap_other_does_not_leak_into_extrap_magnitude() -> None:
    """★この層で唯一の防波堤である(PLAN-017 §8)。

    ADR-027 決定1 の extrap_magnitude は「a, b >= 100(両方正)」であって
    extrap そのものではない。**片側だけ域外の組と、負の被演算子を含む組が
    混ざると、混入率がタスク型で違うだけで task:coverage が有意になる。**
    ラベル入れ替え検定はこれを検出しない(入れ替えても混入は同じであるため)。

    main_radius = 99 は Phase 1 の値(data.train_domain_max)。ここでは
    ADR-027 決定1 の境界そのものを固定するので、実験の値を使う。
    """
    empty: frozenset[tuple[int, int]] = frozenset()
    radius = 99

    # 片側だけ域外。答えは域外(350 > 198)だが extrap_magnitude ではない。
    assert label_coverage((300, 50), empty, main_radius=radius) == COVERAGE_EXTRAP
    assert label_main_coverage((300, 50), empty, main_radius=radius) != COVERAGE_EXTRAP_MAGNITUDE
    assert label_main_coverage((300, 50), empty, main_radius=radius) == COVERAGE_EXTRAP_OTHER

    # ★負の被演算子。**main_radius = 99 では (-99, 1) は extrap ではない** ——
    # |-99| は 99 を超えないので判定は oob_algebraic に落ちる。PLAN-017 F67 が
    # 引いた code/tests/test_pool.py の例は main_radius = 5 のものであり、
    # 本実験の半径では別の水準になる。どちらにせよ extrap_magnitude ではない。
    assert label_coverage((-99, 1), empty, main_radius=radius) == COVERAGE_OOB_ALGEBRAIC
    assert label_main_coverage((-99, 1), empty, main_radius=radius) == COVERAGE_OOB_ALGEBRAIC
    # 域外かつ負。判定順により extrap だが、両方正ではない。
    assert label_coverage((-100, 1), empty, main_radius=radius) == COVERAGE_EXTRAP
    assert label_main_coverage((-100, 1), empty, main_radius=radius) != COVERAGE_EXTRAP_MAGNITUDE
    assert label_main_coverage((-100, 1), empty, main_radius=radius) == COVERAGE_EXTRAP_OTHER
    # main_radius = 5 なら (-99, 1) は extrap である(既存テストの前提)。
    assert label_main_coverage((-99, 1), empty, main_radius=SMALL_RADIUS) == COVERAGE_EXTRAP_OTHER

    # 両方が域外で正のときだけ extrap_magnitude になる。
    assert label_main_coverage((100, 100), empty, main_radius=radius) == COVERAGE_EXTRAP_MAGNITUDE
    assert label_main_coverage((150, 150), empty, main_radius=radius) == COVERAGE_EXTRAP_MAGNITUDE
    # 境界。99 は域内なので、片側が 99 なら extrap_magnitude にならない。
    assert label_main_coverage((99, 100), empty, main_radius=radius) == COVERAGE_EXTRAP_OTHER


def test_main_coverage_boundary_follows_main_radius() -> None:
    """★境界は main_radius であって 100 ではない(skill code-style §1)。

    訓練域を動かしたときに主要検定の説明変数の定義が黙ってずれないこと。
    """
    empty: frozenset[tuple[int, int]] = frozenset()
    assert label_main_coverage((6, 6), empty, main_radius=SMALL_RADIUS) == COVERAGE_EXTRAP_MAGNITUDE
    assert label_main_coverage((6, 6), empty, main_radius=99) == COVERAGE_INTERP


def test_coverage_pairs_outside_the_training_box_are_not_id() -> None:
    """★0 / 負の被演算子は K に入っていても oob_algebraic になる。

    符号だけで決めるので、K の抽出範囲が変わっても oob_algebraic の意味が
    「0 と負数」のまま保たれる(PLAN-002 §4.5.1)。訓練域は [1,99]^2 なので
    本番ではこの状況は起きないが、ラベルの意味を K に依存させない規約を固定する。
    """
    coverage = frozenset({(0, 3), (-1, 2)})
    assert label_coverage((0, 3), coverage, main_radius=SMALL_RADIUS) == COVERAGE_OOB_ALGEBRAIC
    assert label_coverage((-1, 2), coverage, main_radius=SMALL_RADIUS) == COVERAGE_OOB_ALGEBRAIC


def test_interp_is_the_complement_of_coverage() -> None:
    """内挿は「訓練域から K 組を除いた集合」である(変更 C、§4.2)。

    予約割合というパラメータを置かない。K が決まればホールドアウトは
    定義として決まる。
    """
    pairs = main_domain_pairs(SMALL_RADIUS)
    box = training_box(SMALL_RADIUS)
    coverage = frozenset(box[:7])
    labels = [label_coverage(pair, coverage, main_radius=SMALL_RADIUS) for pair in pairs]
    assert labels.count(COVERAGE_ID) == 7
    assert labels.count(COVERAGE_INTERP) == len(box) - 7
    assert labels.count(COVERAGE_OOB_ALGEBRAIC) == len(pairs) - len(box)
    assert labels.count(COVERAGE_EXTRAP) == 0


# --------------------------------------------------------------------------
# 本番スケールの組合せ論的事実 — ADR-020 根拠3 / ADR-021 根拠
# --------------------------------------------------------------------------

# 本番の主域の半径(ADR-019 決定2 の [1,99]^2 と、0/負を含む主域 [-99,99]^2)。
# **実験結果ではなく設計定数である。**外挿域の上限 M* は Phase 0 の実測待ち
# (承認待ち-15)なので、外挿側の件数はここでは固定しない。
MAIN_RADIUS = 99


def test_main_domain_label_counts_match_the_adr() -> None:
    """★ラベルの定義が ADR-021 根拠の表と一致すること(組合せ論的事実)。

    答える問い: 「4値化した label_coverage と答え域ラベルは、設計文書が
    数えたのと同じ分割を作っているか」

    id / interp の内訳は K 依存なので合算で見る(K = 2000 なら 2,000 / 7,801)。
    T_hold(ADR-029)の件数は code/tests/test_design_facts.py に置く
    (PLAN-002 §4.9.3。本セッションの範囲外)。
    """
    coverage: frozenset[tuple[int, int]] = frozenset()
    counts: dict[str, int] = {}
    for pair in main_domain_pairs(MAIN_RADIUS):
        label = label_coverage(pair, coverage, main_radius=MAIN_RADIUS)
        if label == COVERAGE_OOB_ALGEBRAIC:
            label = f"{label}.{label_answer_range(pair, MAIN_RADIUS)}"
        else:
            label = "id+interp"
        counts[label] = counts.get(label, 0) + 1
    assert counts == {
        "id+interp": 9_801,
        f"{COVERAGE_OOB_ALGEBRAIC}.{ANSWER_IN}": 9_702,
        f"{COVERAGE_OOB_ALGEBRAIC}.{ANSWER_OUT}": 20_098,
    }


def test_oob_algebraic_never_exceeds_the_training_answer_range() -> None:
    """★oob_algebraic に t > 198 の組は1つも無い(PLAN-002 §4.6)。

    a, b <= 99 なので t <= 198。帰結として **比較項目の oob_algebraic·ans_out セルは
    構成的に空**であり、主要評価項目は負の和を測れない。**限界の宣言であって
    実装の都合ではない。**事前登録に書く。
    """
    coverage: frozenset[tuple[int, int]] = frozenset()
    over = [
        pair
        for pair in main_domain_pairs(MAIN_RADIUS)
        if label_coverage(pair, coverage, main_radius=MAIN_RADIUS) == COVERAGE_OOB_ALGEBRAIC
        and sum(pair) > 2 * MAIN_RADIUS
    ]
    assert over == []


def test_main_domain_share_of_the_arb_domain_hole() -> None:
    """★主域のうち arb の定義域外は 20,098 組(ADR-020 根拠3 の内訳)。

    旧実装はここで KeyError を投げていた。外挿域の 80,200 組を足した 100,298 が
    ADR-020 の数字だが、外挿側は M*(承認待ち-15)に依存するので固定しない。
    """
    table = {total: total + 3 for total in range(2, 2 * MAIN_RADIUS + 1)}
    arb = ArbitraryLesion(table=table, name="arb")
    undefined = [pair for pair in main_domain_pairs(MAIN_RADIUS) if not arb.is_defined(*pair)]
    assert len(undefined) == 20_098


# --------------------------------------------------------------------------
# 答え域ラベル(PLAN-002 §4.5.2)★ADR-019 決定6
# --------------------------------------------------------------------------


def test_answer_range_splits_on_the_image_of_the_training_box() -> None:
    """訓練で出た答えの全体は [2, 2*R_train]。その外が ans_out。"""
    assert label_answer_range((1, 1), SMALL_RADIUS) == ANSWER_IN
    assert label_answer_range((5, 5), SMALL_RADIUS) == ANSWER_IN
    assert label_answer_range((5, 6), SMALL_RADIUS) == ANSWER_OUT
    assert label_answer_range((1, 0), SMALL_RADIUS) == ANSWER_OUT
    assert label_answer_range((-3, -4), SMALL_RADIUS) == ANSWER_OUT


def test_id_and_interp_are_always_ans_in() -> None:
    """★構成的な性質(PLAN-002 §4.5.2)。この軸で分かれるのは oob / extrap だけ。

    ここが破れると「答えの新規性」と「被演算子の新規性」の分離
    (ADR-019 決定6)が成立しない。
    """
    box = training_box(SMALL_RADIUS)
    coverage = frozenset(box[:7])
    for pair in main_domain_pairs(SMALL_RADIUS):
        label = label_coverage(pair, coverage, main_radius=SMALL_RADIUS)
        if label in (COVERAGE_ID, COVERAGE_INTERP):
            assert label_answer_range(pair, SMALL_RADIUS) == ANSWER_IN, pair


# --------------------------------------------------------------------------
# t 水準の被覆ラベル(PLAN-002 §4.5.1a)★ADR-021
# --------------------------------------------------------------------------


def test_coverage_sums_folds_pairs_into_their_sums() -> None:
    assert coverage_sums_of([(1, 2), (2, 1), (3, 4)]) == frozenset({3, 7})


def test_label_t_coverage_reads_the_sum_not_the_pair() -> None:
    """★(a,b) が未見でも t が既見なら t_seen(ADR-021 の眼目)。

    arb の規則値は table[a+b] なので、一般化は t の水準で起きる。
    """
    sums = coverage_sums_of([(1, 2)])
    assert label_t_coverage((1, 2), sums) == T_SEEN
    assert label_t_coverage((0, 3), sums) == T_SEEN
    assert label_t_coverage((-4, 7), sums) == T_SEEN
    assert label_t_coverage((1, 3), sums) == T_UNSEEN


def test_id_is_always_t_seen() -> None:
    """★構成的な性質(ADR-021)。K の組の和は定義から被覆されている。"""
    box = training_box(SMALL_RADIUS)
    coverage = frozenset(box[:7])
    sums = coverage_sums_of(coverage)
    for pair in main_domain_pairs(SMALL_RADIUS):
        if label_coverage(pair, coverage, main_radius=SMALL_RADIUS) == COVERAGE_ID:
            assert label_t_coverage(pair, sums) == T_SEEN, pair


def test_t_coverage_is_orthogonal_to_the_pair_level_label() -> None:
    """★3軸は直交する(ADR-021 決定1)。interp の中に t_seen と t_unseen が両方いる。

    ここが片方に潰れると arb の層別ができない。
    """
    box = training_box(SMALL_RADIUS)
    coverage = frozenset(box[:7])
    sums = coverage_sums_of(coverage)
    interp = [
        pair
        for pair in main_domain_pairs(SMALL_RADIUS)
        if label_coverage(pair, coverage, main_radius=SMALL_RADIUS) == COVERAGE_INTERP
    ]
    labels = {label_t_coverage(pair, sums) for pair in interp}
    assert labels == {T_SEEN, T_UNSEEN}


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


# 訓練域外の 50:50 を確かめる標本の大きさ。期待値で半分になることを見るだけなので、
# 二項 SE(0.5 / sqrt(n) ≈ 0.011)に対して十分に広い許容幅を置く。
OUTSIDE_SIDE_SAMPLE_RADIUS = 30
OUTSIDE_SIDE_TOLERANCE = 0.05


def test_outside_domain_side_is_a_function_of_pair_and_seed() -> None:
    """★訓練域外の側は組とシードだけで決まる(ADR-076 決定10 (iii))。"""
    pair = (150, 160)
    assert outside_domain_side(pair, 0) == outside_domain_side(pair, 0)
    assert outside_domain_side(pair, 0) in (POOL_MAIN, POOL_PILOT)
    sides = {outside_domain_side((a, 200), 0) for a in range(100, 140)}
    assert sides == {POOL_MAIN, POOL_PILOT}


def test_outside_domain_side_is_near_half_but_not_forced_to_half() -> None:
    """期待値で 50:50(ADR-076 決定10 (iii))。**件数をちょうど半分に揃える処理は無い。**"""
    pairs = [
        (a, b)
        for a in range(1, OUTSIDE_SIDE_SAMPLE_RADIUS + 1)
        for b in range(1, OUTSIDE_SIDE_SAMPLE_RADIUS + 1)
    ]
    share = sum(outside_domain_side(pair, 0) == POOL_MAIN for pair in pairs) / len(pairs)
    assert abs(share - 0.5) < OUTSIDE_SIDE_TOLERANCE
    assert [outside_domain_side(pair, 0) for pair in pairs] != [
        outside_domain_side(pair, 1) for pair in pairs
    ]


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
        specificity_reference_rules=["spec_mul", "spec_sub"],
        coverage_sums=coverage_sums_of([(1, 2), (2, 1), (3, 4)]),
        seed=0,
        main_radius=SMALL_RADIUS,
        extrapolation_radius=None,
        extrapolation_run_id=None,
        counterpart_pool_id="pilot",
        counterpart_hash=pairs_hash([(9, 9)]),
        prompt_format_block=ANCHOR_FORMAT,
        item_exclusions={},
        id_cell_population=EMPTY_ID_POPULATION,
        fill=EXPLICIT_FILL,
    )
    assert manifest["reference_rules"] == ["p2", "x2"]
    assert manifest["pairs_hash"] == pairs_hash(pairs)
    # ★t 水準の被覆ラベルを後から再現するために要る(ADR-021 決定2)。
    assert manifest["coverage_sums"] == [3, 7]
    assert manifest["counterpart_pool_id"] == "pilot"
    # M* は Phase 0 の実測待ち。既定値を作らず None のまま残す(§4.1.1)。
    assert manifest["extrapolation_radius"] is None


def test_manifest_carries_the_prompt_format_of_the_evaluation_anchor() -> None:
    """★評価アンカー(T1)の書式を残す(PLAN-002 §4.8.1 検査6)。

    このプールは T1 = 裸の計算式を含む。preflight は
    `eval.anchor_manifest` が指す manifest の `prompt_format` を訓練側と
    照合するので、ここに無いと検査6 が FAIL のまま止まる。
    """
    manifest = build_manifest(
        pool_id="main",
        pairs=[(1, 2)],
        reference_rules=["p2"],
        specificity_reference_rules=["spec_mul", "spec_sub"],
        coverage_sums=coverage_sums_of([(1, 2)]),
        seed=0,
        main_radius=SMALL_RADIUS,
        extrapolation_radius=None,
        extrapolation_run_id=None,
        counterpart_pool_id="pilot",
        counterpart_hash=pairs_hash([(9, 9)]),
        prompt_format_block=ANCHOR_FORMAT,
        item_exclusions={"word_problem": {"excluded_operands": [1]}},
        id_cell_population=EMPTY_ID_POPULATION,
        fill=EXPLICIT_FILL,
    )
    assert manifest["prompt_format"] == ANCHOR_FORMAT
    # ★T2 の被演算子 1 の除外(ADR-032 決定4)。参照規則からは読み取れない。
    assert manifest["item_exclusions"]["word_problem"]["excluded_operands"] == [1]


def test_manifest_refuses_a_stale_prompt_format() -> None:
    """★書式ブロックを手で書き換えても format_hash は追随しない。

    ここで止めないと、preflight から見て「訓練と評価で書式が違う」に化ける。
    違うのは書式ではなく記録である。
    """
    tampered = dict(ANCHOR_FORMAT)
    tampered["whitespace"] = "single"
    with pytest.raises(ValueError, match="format_hash"):
        build_manifest(
            pool_id="main",
            pairs=[(1, 2)],
            reference_rules=["p2"],
        specificity_reference_rules=["spec_mul", "spec_sub"],
            coverage_sums=coverage_sums_of([(1, 2)]),
            seed=0,
            main_radius=SMALL_RADIUS,
            extrapolation_radius=None,
            extrapolation_run_id=None,
            counterpart_pool_id="pilot",
            counterpart_hash=pairs_hash([(9, 9)]),
            prompt_format_block=tampered,
            item_exclusions={},
            id_cell_population=EMPTY_ID_POPULATION,
            fill=EXPLICIT_FILL,
        )


# --------------------------------------------------------------------------
# 評価項目の被演算子除外(ADR-035 決定3)★
# --------------------------------------------------------------------------


def test_the_excluded_operand_is_refused_in_either_position() -> None:
    assert is_excluded_operand_pair((1, 5))
    assert is_excluded_operand_pair((5, 1))
    assert not is_excluded_operand_pair((2, 5))


def test_eligible_item_pairs_drop_the_excluded_operand() -> None:
    """★候補の段階で落とす。生成器に渡る前でなければ件数が静かに減る。"""
    candidates = [(1, 5), (2, 5), (5, 1), (5, 2)]
    assert eligible_item_pairs(candidates) == [(2, 5), (5, 2)]


def test_the_operand_exclusion_is_recorded_per_group() -> None:
    """★ADR-035 帰結: 欄は**プール全体**、内訳は群ごと。

    群ごとの内訳が消えると、被演算子分布がタスク型間で揃っていることを
    manifest から確かめられなくなる(それが決定3 の目的そのものである)。

    ★ADR-075: 被演算子 −1 も同じ定数で外れる(決定1)。**真値 −1 の組 (3, −4) は
    外れない**(決定2)—— 除外は被演算子の値で掛けるのであって、答えの値では掛けない。
    """
    record = excluded_operand_record(
        {
            "bare_sum": [(1, 5), (2, 5), (-1, 7), (3, -4)],
            "word_problem": [(1, 5), (5, 1), (3, 4), (6, -1)],
        }
    )
    assert record["scope"] == "pool"
    assert record["excluded_operands"] == [-1, 1]
    assert record["applied_to"] == "eval_items_only"
    assert record["n_candidates"] == 8
    assert record["n_excluded"] == 5
    assert record["by_group"]["bare_sum"] == {"n_candidates": 4, "n_excluded": 2}
    assert record["by_group"]["word_problem"] == {"n_candidates": 4, "n_excluded": 3}


# --------------------------------------------------------------------------
# id セルの母集団(ADR-034 リスク欄 / ADR-035 決定3)★
# --------------------------------------------------------------------------


def test_the_id_cell_population_is_not_the_coverage_itself() -> None:
    """★★`id` セルは `K` そのものからは引かれない(ADR-034 リスク欄)。

    判別不能の除外(`t ≡ 0 mod digit_modulus`)も被演算子の除外も**評価側に
    だけ**掛かるので、`id` セルの母集団は `K` の真部分集合になる。
    書き残さないと「`K` から一様に引かれている」ように読める。
    """
    p2 = AdditiveLesion(offset=2, name="p2")
    p2d = DigitOffsetLesion(offset=2, digit_modulus=10, name="p2d")
    # (2, 8) は t = 10 ≡ 0 (mod 10) なので p2 と p2d が同じ値を返す。
    # (1, 5) は被演算子 1 を含む。(3, 4) と (5, 6) はどちらの除外も受けない。
    coverage = [(2, 8), (1, 5), (3, 4), (5, 6)]
    population = id_cell_population(
        coverage, [p2, p2d], indistinguishable_rule_pairs=[(p2, p2d)]
    )
    assert population.pairs == [(3, 4), (5, 6)]

    stages = {stage["name"]: stage for stage in population.record["stages"]}
    assert stages["coverage_k"]["n"] == 4
    assert stages["indistinguishable_rule_pairs"]["n"] == 3
    assert stages["excluded_operands"]["n"] == 2
    assert population.record["n_pairs"] == 2
    assert population.record["pairs_hash"] == pairs_hash([(3, 4), (5, 6)])


def test_the_indistinguishable_exclusion_does_not_touch_the_carry_stratum() -> None:
    """★ADR-034 の性質: `t ≡ 0 (mod 10)` は一の位が 0 なので必ず nocarry。

    落ちるのが片側の層だけなら carry 密度は動かない。この性質が崩れると
    PLAN-003 §4.7 の「carry 393 は減らない」が成り立たなくなる。
    """
    p2 = AdditiveLesion(offset=2, name="p2")
    p2d = DigitOffsetLesion(offset=2, digit_modulus=10, name="p2d")
    coverage = [(a, b) for a in range(1, 20) for b in range(1, 20)]
    population = id_cell_population(
        coverage, [p2, p2d], indistinguishable_rule_pairs=[(p2, p2d)]
    )
    stages = {stage["name"]: stage for stage in population.record["stages"]}
    assert stages["indistinguishable_rule_pairs"]["strata"][CARRY] == (
        stages["coincidence"]["strata"][CARRY]
    )
    assert stages["indistinguishable_rule_pairs"]["strata"][NOCARRY] < (
        stages["coincidence"]["strata"][NOCARRY]
    )


# --------------------------------------------------------------------------
# 被覆セルの充填(ADR-017 = §5.1.1 の穴1 に対する案A)★
# --------------------------------------------------------------------------


def cell_fixture() -> tuple[list[tuple[int, int]], frozenset[tuple[int, int]]]:
    """主域 + 外挿域の候補と、訓練被覆 K 組の代わりの小さな集合。

    `K` の**値は決めない**(未決定。PLAN-001 §4.2.1)。ここでは機構が
    動くかを見るために任意の集合を与えているだけである。

    K は**訓練域 [1,R]^2 からしか引かれない**(ADR-019 決定2)。0 / 負の
    被演算子を K に入れると、その組は id ではなく oob_algebraic になり
    (PLAN-002 §4.5.1)、id セルが埋まらない。
    """
    main = eligible_pairs(main_domain_pairs(SMALL_RADIUS), [p2(), x2()])
    extra = eligible_pairs(
        extrapolation_pairs(main_radius=SMALL_RADIUS, extrapolation_radius=8), [p2(), x2()]
    )
    coverage = frozenset(training_box(SMALL_RADIUS)[:COVERAGE_SIZE])
    return main + extra, coverage


def test_fill_cells_respects_coverage_labels() -> None:
    """★`id` セルは K 組から、`interp` セルはその補集合から埋まる(ADR-017)。

    **`extrap_magnitude` のセルは `a, b > R` の組だけから埋まる**(ADR-076 決定10 (ii))。
    2026-09-11 までは `label_coverage`(4値)で照合していたので、このセルは候補 0 件で
    止まっていた(PLAN-023 A1)。
    """
    candidates, coverage = cell_fixture()
    cells = [
        Cell(name="id", coverage=COVERAGE_ID, carry=None, n=5),
        Cell(name="interp", coverage=COVERAGE_INTERP, carry=None, n=5),
        Cell(name="extrap_magnitude", coverage=COVERAGE_EXTRAP_MAGNITUDE, carry=None, n=5),
    ]
    assignment = fill_cells(
        candidates, cells, coverage_pairs=coverage, main_radius=SMALL_RADIUS, seed=0
    )
    assert set(assignment["id"]) <= coverage
    assert not (set(assignment["interp"]) & coverage)
    assert all(a > SMALL_RADIUS and b > SMALL_RADIUS for a, b in assignment["extrap_magnitude"])


def test_fill_cells_refuses_four_valued_extrap() -> None:
    """★`coverage: extrap` のセルは受け付けずに止める(ADR-076 決定10 (ii))。

    4値の `extrap` は負の被演算子や片側だけ域外の組を含む。黙って引くと
    C6(`extrap_magnitude`)とは別の母集団が主軸 3 水準目に入る(PLAN-023 A1)。
    """
    candidates, coverage = cell_fixture()
    cells = [Cell(name="extrap", coverage=COVERAGE_EXTRAP, carry=None, n=1)]
    with pytest.raises(ValueError, match="extrap_magnitude"):
        fill_cells(candidates, cells, coverage_pairs=coverage, main_radius=SMALL_RADIUS, seed=0)


def test_fill_cells_appended_cell_does_not_move_earlier_cells() -> None:
    """★後ろにセルを足しても、前のセルの割当は動かない(ADR-076 決定10 (iv))。"""
    candidates, coverage = cell_fixture()
    kwargs = {"coverage_pairs": coverage, "main_radius": SMALL_RADIUS, "seed": 3}
    base = [
        Cell(name="interp", coverage=COVERAGE_INTERP, carry=None, n=3),
        Cell(name="extrap_magnitude", coverage=COVERAGE_EXTRAP_MAGNITUDE, carry=None, n=3),
    ]
    extended = [*base, Cell(name="oob", coverage=COVERAGE_OOB_ALGEBRAIC, carry=None, n=3)]
    before = fill_cells(candidates, base, **kwargs)
    after = fill_cells(candidates, extended, **kwargs)
    assert {name: after[name] for name in before} == before


def test_fill_cells_does_not_depend_on_other_coverage_candidates() -> None:
    """★ほかの被覆の候補を足しても、セルの割当は動かない(ADR-076 決定10 (iv))。

    副次セル(P-2)のために候補集合を広げたとき、主軸の割当が動かないことの核心。
    2026-09-11 までの `fill_cells` は候補全体を1回だけ並べ替えていたので、ここが割れた。
    """
    candidates, coverage = cell_fixture()
    kwargs = {"coverage_pairs": coverage, "main_radius": SMALL_RADIUS, "seed": 3}
    cells = [Cell(name="interp", coverage=COVERAGE_INTERP, carry=None, n=4)]
    only_interp = [
        pair
        for pair in candidates
        if label_main_coverage(pair, coverage, SMALL_RADIUS) == COVERAGE_INTERP
    ]
    assert fill_cells(only_interp, cells, **kwargs) == fill_cells(candidates, cells, **kwargs)
    assert fill_cells(list(reversed(candidates)), cells, **kwargs) == fill_cells(
        candidates, cells, **kwargs
    )


def test_fill_cells_does_not_reuse_pairs() -> None:
    """同じ組が2つのセルに入らない(項目ランダム効果が壊れるため)。"""
    candidates, coverage = cell_fixture()
    cells = [Cell(name=f"interp{i}", coverage=COVERAGE_INTERP, carry=None, n=5) for i in range(3)]
    assignment = fill_cells(
        candidates, cells, coverage_pairs=coverage, main_radius=SMALL_RADIUS, seed=0
    )
    chosen = [pair for pairs in assignment.values() for pair in pairs]
    assert len(chosen) == len(set(chosen)) == 15


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
